import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getWorkspaceFallbackNotice,
  getWorkspaceRuntimeMismatchNotice,
} from './workspaceChatPresentation.js';

test('partial preserved fallback shows preserved notice', () => {
  const notice = getWorkspaceFallbackNotice({
    answerMode: 'grounded_fallback',
    failureReason: 'llm_partial_preserved_after_retry',
    partialGenerationPreserved: true,
  });

  assert.ok(notice);
  assert.equal(notice?.tone, 'blue');
  assert.match(notice?.title || '', /保留有效内容/);
});

test('compact retry failed maps to model failure notice', () => {
  const notice = getWorkspaceFallbackNotice({
    answerMode: 'system_failure',
    failureReason: 'llm_generation_failed',
    finalFailureStage: 'compact_retry_failed',
    fallbackTemplateUsed: false,
  });

  assert.ok(notice);
  assert.equal(notice?.tone, 'rose');
  assert.match(notice?.detail || '', /没有生成可交付文本/);
});

test('legacy template fallback is explicitly labeled', () => {
  const notice = getWorkspaceFallbackNotice({
    answerMode: 'grounded_fallback',
    fallbackTemplateUsed: true,
  });

  assert.ok(notice);
  assert.match(notice?.title || '', /legacy fallback/);
});

test('cooldown fallback uses cooldown-specific copy', () => {
  const notice = getWorkspaceFallbackNotice({
    answerMode: 'grounded_fallback',
    generationPolicy: {
      cooldownActive: true,
      reason: 'cooldown_active_probe_compact',
    },
  });

  assert.ok(notice);
  assert.match(notice?.detail || '', /重置 runtime 状态|模型连通性/);
});

test('source mismatch notice prefers source integrity warning', () => {
  const notice = getWorkspaceRuntimeMismatchNotice({
    sourceIntegrityMatch: false,
    sourceIntegrityWarning: '当前运行安装包与工作区源码不一致',
  });

  assert.equal(notice, '当前运行安装包与工作区源码不一致');
});

test('frontend backend build mismatch produces banner copy', () => {
  const notice = getWorkspaceRuntimeMismatchNotice({
    sourceIntegrityMatch: true,
    backendBuildVersion: '2026.04.21',
    frontendBuildVersion: '2026.04.20',
  });

  assert.match(notice || '', /buildVersion 不一致/);
});

test('missing workspace source comparison does not produce stale package banner', () => {
  const notice = getWorkspaceRuntimeMismatchNotice({
    sourceIntegrityMatch: null,
    backendBuildVersion: '2026.04.22',
    frontendBuildVersion: '2026.04.22',
  });

  assert.equal(notice, null);
});
