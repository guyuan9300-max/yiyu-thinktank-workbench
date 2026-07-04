import { test } from 'node:test';
import assert from 'node:assert/strict';
import { resolveBatchTask, appendUnmatchedToDesc, type BatchDirectories } from './batchTaskResolve';
import { parseBatchTasks } from '../../shared/batchTaskParse';

function make(raw: string, dirs: BatchDirectories) {
  return resolveBatchTask(parseBatchTasks(raw, 2026)[0], dirs);
}
const D = (
  members: Array<{ id: string; fullName: string }> = [],
  eventLines: Array<{ id: string; name: string }> = [],
  clients: Array<{ id: string; name: string }> = [],
): BatchDirectories => ({ clients, eventLines, members });

test('精确命中: 客户/事件线/负责人', () => {
  const rv = make(
    '标题：X\n日期：7/3\n负责人：顾源源\n事件线：715上线\n客户：汇丰\n背景：y',
    D([{ id: 'emp_1', fullName: '顾源源' }], [{ id: 'e_1', name: '715上线' }], [{ id: 'c_1', name: '汇丰' }]),
  );
  assert.equal(rv.clientId, 'c_1');
  assert.equal(rv.eventLineId, 'e_1');
  assert.equal(rv.ownerId, 'emp_1');
  assert.equal(rv.eventLineCreateName, null);
});

test('★不误配事件线: "715上线" vs 已有"上线" → 新建, 不挂错', () => {
  const rv = make('标题：X\n日期：7/3\n事件线：715上线\n背景：y', D([], [{ id: 'e_x', name: '上线' }]));
  assert.equal(rv.eventLineId, null);
  assert.equal(rv.eventLineCreateName, '715上线');
});

test('★不误指派人: 负责人"李伟" vs 名册"李伟明" → 落背景, 不指派错人', () => {
  const rv = make('标题：X\n日期：7/3\n负责人：李伟\n背景：y', D([{ id: 'emp_1', fullName: '李伟明' }]));
  assert.equal(rv.ownerId, null);
  assert.deepEqual(rv.unmatchedPeople, ['李伟']);
});

test('★不误配协作者: "佳维" vs "林佳维" → 落背景', () => {
  const rv = make('标题：X\n日期：7/3\n协作者：佳维\n背景：y', D([{ id: 'emp_2', fullName: '林佳维' }]));
  assert.deepEqual(rv.collaborators, []);
  assert.deepEqual(rv.unmatchedPeople, ['佳维']);
});

test('归一化: 括注/大小写/空格 不影响精确匹配', () => {
  const rv = make('标题：X\n日期：7/3\n负责人：庆华\n背景：y', D([{ id: 'emp_3', fullName: '庆华（AI）' }]));
  assert.equal(rv.ownerId, 'emp_3');
});

test('负责人不重复进协作者', () => {
  const rv = make(
    '标题：X\n日期：7/3\n负责人：顾源源\n协作者：顾源源、蚊子\n背景：y',
    D([{ id: 'emp_1', fullName: '顾源源' }, { id: 'emp_2', fullName: '蚊子' }]),
  );
  assert.equal(rv.ownerId, 'emp_1');
  assert.deepEqual(rv.collaborators, [{ id: 'emp_2', name: '蚊子' }]);
});

test('appendUnmatchedToDesc: 空时不动, 有时追加', () => {
  assert.equal(appendUnmatchedToDesc('背景', []), '背景');
  assert.ok(appendUnmatchedToDesc('背景', ['保罗']).includes('保罗'));
});
