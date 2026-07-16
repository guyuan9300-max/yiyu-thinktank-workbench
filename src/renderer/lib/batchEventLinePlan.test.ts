import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  appendUnmatchedEventLineToDesc,
  buildBatchEventLinePlan,
  canSubmitBatchImport,
  buildBatchEventLineIdempotencyKey,
  resolveEventLineIdForSave,
  type BatchEventLineCandidate,
} from './batchEventLinePlan.ts';

const candidate = (
  eventLineName: string | null,
  eventLineId: string | null = null,
): BatchEventLineCandidate => ({ eventLineName, eventLineId });

test('已有同名事件线归入复用，不会进入新建', () => {
  const plan = buildBatchEventLinePlan(
    [candidate('715上线', 'eline_715')],
    new Set(),
    'ready',
  );

  assert.deepEqual(plan, [{
    key: 'id:eline_715',
    name: '715上线',
    eventLineId: 'eline_715',
    taskCount: 1,
    decision: 'reuse',
  }]);
});

test('未命中名称默认是未匹配，不是将新建', () => {
  const plan = buildBatchEventLinePlan(
    [candidate('第三方权益'), candidate('第三方权益')],
    new Set(),
    'ready',
  );

  assert.equal(plan.length, 1);
  assert.equal(plan[0].decision, 'unmatched');
  assert.equal(plan[0].taskCount, 2);
});

test('只有用户明确勾选的未匹配名称才进入将新建', () => {
  const plan = buildBatchEventLinePlan(
    [candidate('第三方权益'), candidate('长期建设')],
    new Set(['第三方权益']),
    'ready',
  );

  assert.deepEqual(plan.map((item) => [item.name, item.decision]), [
    ['第三方权益', 'create'],
    ['长期建设', 'unmatched'],
  ]);
});

test('括注不同的事件线分别展示，审批一期不会连带批准二期', () => {
  const plan = buildBatchEventLinePlan(
    [candidate('长期建设（一期）'), candidate('长期建设（二期）')],
    new Set(['长期建设（一期）']),
    'ready',
  );

  assert.equal(plan.length, 2);
  assert.deepEqual(plan.map((item) => [item.name, item.decision]), [
    ['长期建设（一期）', 'create'],
    ['长期建设（二期）', 'unmatched'],
  ]);
});

test('名册未加载或加载失败时归入未核对，禁止提交', () => {
  for (const state of ['loading', 'error'] as const) {
    const plan = buildBatchEventLinePlan(
      [candidate('715上线')],
      new Set(['715上线']),
      state,
    );

    assert.equal(plan[0].decision, 'unverified');
    assert.equal(canSubmitBatchImport(state, plan, true), false);
  }
});

test('有将新建项时必须再次明确确认', () => {
  const plan = buildBatchEventLinePlan(
    [candidate('第三方权益')],
    new Set(['第三方权益']),
    'ready',
  );

  assert.equal(canSubmitBatchImport('ready', plan, false), false);
  assert.equal(canSubmitBatchImport('ready', plan, true), true);
});

test('未批准的名称保持不关联，不调用新建接口', async () => {
  let calls = 0;
  const id = await resolveEventLineIdForSave({
    candidate: candidate('第三方权益'),
    directoryState: 'ready',
    approvedCreateNames: new Set(),
    creationConfirmed: false,
    cache: new Map(),
    createEventLine: async () => {
      calls += 1;
      return { id: 'eline_new' };
    },
  });

  assert.equal(id, null);
  assert.equal(calls, 0);
});

test('明确批准后同名只新建一次并复用缓存', async () => {
  let calls = 0;
  const cache = new Map<string, string>();
  const createEventLine = async () => {
    calls += 1;
    return { id: 'eline_new' };
  };
  const options = {
    candidate: candidate('第三方权益'),
    directoryState: 'ready' as const,
    approvedCreateNames: new Set(['第三方权益']),
    creationConfirmed: true,
    cache,
    createEventLine,
  };

  assert.equal(await resolveEventLineIdForSave(options), 'eline_new');
  assert.equal(await resolveEventLineIdForSave(options), 'eline_new');
  assert.equal(calls, 1);
});

test('已有事件线永远直接复用，不调用新建接口', async () => {
  let calls = 0;
  const id = await resolveEventLineIdForSave({
    candidate: candidate('715上线', 'eline_715'),
    directoryState: 'ready',
    approvedCreateNames: new Set(['715上线']),
    creationConfirmed: true,
    cache: new Map(),
    createEventLine: async () => {
      calls += 1;
      return { id: 'should_not_happen' };
    },
  });

  assert.equal(id, 'eline_715');
  assert.equal(calls, 0);
});

test('名册未核对完成时，即使候选残留旧 id 也禁止复用', async () => {
  let calls = 0;
  const id = await resolveEventLineIdForSave({
    candidate: candidate('715上线', 'eline_stale'),
    directoryState: 'error',
    approvedCreateNames: new Set(),
    creationConfirmed: false,
    cache: new Map(),
    createEventLine: async () => {
      calls += 1;
      return { id: 'eline_new' };
    },
  });

  assert.equal(id, null);
  assert.equal(calls, 0);
});

test('批量新建幂等键在同一会话同名稳定，不同名不会冲突', () => {
  const first = buildBatchEventLineIdempotencyKey('session-1', '长期建设（一期）');
  assert.equal(first, buildBatchEventLineIdempotencyKey('session-1', '长期建设（一期）'));
  assert.notEqual(first, buildBatchEventLineIdempotencyKey('session-1', '长期建设（二期）'));
  assert.notEqual(first, buildBatchEventLineIdempotencyKey('session-2', '长期建设（一期）'));
  assert.ok(first.length <= 255);
});

test('未关联事件线名称保留到任务背景', () => {
  const result = appendUnmatchedEventLineToDesc('原背景', '第三方权益');
  assert.match(result, /未关联事件线：第三方权益/);
  assert.match(result, /^原背景/);
});
