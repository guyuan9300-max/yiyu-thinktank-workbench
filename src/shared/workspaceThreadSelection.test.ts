import test from 'node:test';
import assert from 'node:assert/strict';

import {
  parseWorkspaceThreadPreference,
  pickWorkspaceCurrentThreadId,
} from './workspaceThreadSelection.js';

test('parseWorkspaceThreadPreference defaults to latest', () => {
  assert.equal(parseWorkspaceThreadPreference(null), 'latest');
  assert.equal(parseWorkspaceThreadPreference('unknown'), 'latest');
});

test('pickWorkspaceCurrentThreadId prefers active analysis run thread', () => {
  const threadId = pickWorkspaceCurrentThreadId({
    activeAnalysisRunThreadId: 'run-thread',
    selectedThreadId: 'selected-thread',
    preference: 'fresh',
  });
  assert.equal(threadId, 'run-thread');
});

test('pickWorkspaceCurrentThreadId keeps explicit selected thread', () => {
  const threadId = pickWorkspaceCurrentThreadId({
    selectedThreadId: 'selected-thread',
    threads: [{ id: 'selected-thread', clientId: 'c1', title: 'A', createdAt: '2026-04-22T10:00:00Z', updatedAt: '2026-04-22T10:00:00Z' }],
    preference: 'fresh',
  });
  assert.equal(threadId, 'selected-thread');
});

test('pickWorkspaceCurrentThreadId returns null for fresh preference without explicit thread', () => {
  const threadId = pickWorkspaceCurrentThreadId({
    threads: [{ id: 'old-thread', clientId: 'c1', title: 'Old', createdAt: '2026-04-21T10:00:00Z', updatedAt: '2026-04-21T10:00:00Z' }],
    preference: 'fresh',
  });
  assert.equal(threadId, null);
});

test('pickWorkspaceCurrentThreadId falls back to latest thread when preference is latest', () => {
  const threadId = pickWorkspaceCurrentThreadId({
    threads: [
      { id: 'older-thread', clientId: 'c1', title: 'Old', createdAt: '2026-04-21T10:00:00Z', updatedAt: '2026-04-21T10:00:00Z' },
      { id: 'latest-thread', clientId: 'c1', title: 'Latest', createdAt: '2026-04-22T11:00:00Z', updatedAt: '2026-04-22T11:00:00Z' },
    ],
    preference: 'latest',
  });
  assert.equal(threadId, 'latest-thread');
});

test('pickWorkspaceCurrentThreadId returns null while workspace client is still stale', () => {
  const threadId = pickWorkspaceCurrentThreadId({
    currentClientId: 'c2',
    workspaceClientId: 'c1',
    selectedThreadId: 'old-thread',
    threads: [{ id: 'old-thread', clientId: 'c1', title: 'Old', createdAt: '2026-04-21T10:00:00Z', updatedAt: '2026-04-21T10:00:00Z' }],
    preference: 'latest',
  });
  assert.equal(threadId, null);
});
