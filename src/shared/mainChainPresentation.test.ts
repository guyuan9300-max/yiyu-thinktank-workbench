import test from 'node:test';
import assert from 'node:assert/strict';

import type { ProposalRecord } from './types.js';
import {
  containsChatProcessLeakMarkers,
  getChatRouteDecisionFromDataCenter,
  formatStateSourceSummary,
  getChatRouteDecision,
  getChatRetrievalPresentation,
  getCockpitHeadlineTone,
  getProposalEffectType,
  getWorkspaceSignalTone,
  groupProposalRecords,
  shouldRenderChatExtendedAnalysis,
} from './mainChainPresentation.js';

test('workspace uses formal tone only for approved baseline', () => {
  const tone = getWorkspaceSignalTone({ hasOfficialBaseline: true, authorityLevel: 'approved' });

  assert.equal(tone.sectionLabel, '客户级正式基线');
  assert.equal(tone.authorityBadge, '正式判断');
  assert.equal(tone.notice, null);
  assert.equal(tone.formal, true);
});

test('workspace keeps candidate and fallback in non-formal tone', () => {
  const candidateTone = getWorkspaceSignalTone({ hasOfficialBaseline: false, authorityLevel: 'candidate' });
  const fallbackTone = getWorkspaceSignalTone({ hasOfficialBaseline: false, authorityLevel: 'fallback' });

  assert.equal(candidateTone.sectionLabel, '主链候选信号');
  assert.match(candidateTone.notice || '', /不代表正式结论/);
  assert.equal(candidateTone.formal, false);

  assert.equal(fallbackTone.authorityBadge, '回退判断');
  assert.match(fallbackTone.notice || '', /不代表正式结论/);
  assert.equal(fallbackTone.formal, false);
});

test('cockpit empty official layer disables formal headline', () => {
  const tone = getCockpitHeadlineTone({
    officialLayerStatus: 'empty',
    officialEmptyReason: '当前暂无已批准判断',
  });

  assert.equal(tone.title, '当前暂无已批准判断');
  assert.match(tone.subtitle, /风险雷达/);
  assert.equal(tone.allowFormalHeadline, false);
});

test('chat retrieval reason maps to stable user-facing explanation', () => {
  const stateFirst = getChatRetrievalPresentation({ reason: 'state_first_default' });
  const introEvidence = getChatRetrievalPresentation({ reason: 'intro_query_needs_evidence' });
  const identityGuard = getChatRetrievalPresentation({ reason: 'identity_query_needs_evidence' });
  const insufficient = getChatRetrievalPresentation({ reason: 'state_pool_insufficient' });

  assert.equal(stateFirst.label, '状态优先');
  assert.match(stateFirst.detail, /状态池/);
  assert.equal(introEvidence.label, '证据下钻');
  assert.match(introEvidence.detail, /机构介绍|原始证据/);
  assert.equal(identityGuard.label, '身份校验');
  assert.equal(insufficient.label, '状态不足');
});

test('new retrieval reasons map to evidence-first and registry copy', () => {
  const meeting = getChatRetrievalPresentation({ reason: 'meeting_summary_needs_evidence' });
  const nextActions = getChatRetrievalPresentation({ reason: 'next_actions_needs_evidence' });
  const registry = getChatRetrievalPresentation({ reason: 'official_registry_requested' });
  const hybrid = getChatRetrievalPresentation({ reason: 'default_hybrid_evidence' });

  assert.equal(meeting.label, '证据下钻');
  assert.match(meeting.detail, /会议|行动项/);
  assert.equal(nextActions.label, '证据下钻');
  assert.match(nextActions.detail, /任务|会议行动项/);
  assert.equal(registry.label, '状态优先');
  assert.match(registry.detail, /正式判断/);
  assert.equal(hybrid.label, '证据下钻');
});

test('route decision exposes intent, drilldown and source', () => {
  const evidenceRoute = getChatRouteDecision({
    answerIntent: 'meeting_summary',
    answerMode: 'grounded_answer',
    retrievalDeferred: false,
    reason: 'meeting_summary_needs_evidence',
  });
  const stateRoute = getChatRouteDecision({
    answerIntent: 'official_judgment_registry',
    answerMode: 'grounded_fallback',
    retrievalDeferred: true,
    reason: 'official_registry_requested',
    judgmentQueryMode: 'registry_only',
  });

  assert.equal(evidenceRoute.intentLabel, '会议纪要');
  assert.equal(evidenceRoute.drilldownLabel, '是');
  assert.equal(evidenceRoute.primarySource, '原始资料');

  assert.equal(stateRoute.intentLabel, '正式判断查询');
  assert.equal(stateRoute.drilldownLabel, '否');
  assert.equal(stateRoute.primarySource, '状态池');
  assert.match(stateRoute.noDrilldownReason || '', /正式判断/);
});

test('data center route decision is converted to route chips', () => {
  const route = getChatRouteDecisionFromDataCenter({
    routeDecision: {
      intent: 'meeting_summary',
      retrievalMode: 'hybrid',
      shouldUseRawEvidence: true,
      shouldUseStatePool: true,
      routeReason: 'meeting_summary_needs_evidence',
    },
  });

  assert.ok(route);
  assert.equal(route?.intentLabel, '会议纪要');
  assert.equal(route?.drilldownLabel, '是');
  assert.equal(route?.primarySource, '状态池 + 原始资料');
  assert.equal(route?.noDrilldownReason, null);
});

test('data center route decision keeps no-drilldown reason', () => {
  const route = getChatRouteDecisionFromDataCenter({
    routeDecision: {
      intent: 'official_judgment_registry',
      retrievalMode: 'state_only',
      shouldUseRawEvidence: false,
      shouldUseStatePool: true,
      routeReason: 'official_registry_requested',
    },
  });

  assert.ok(route);
  assert.equal(route?.intentLabel, '正式判断查询');
  assert.equal(route?.drilldownLabel, '否');
  assert.equal(route?.primarySource, '状态池');
  assert.equal(route?.noDrilldownReason, 'official_registry_requested');
});

test('judgment retrieval modes expose hybrid and registry specific copy', () => {
  const registryOnly = getChatRetrievalPresentation({ judgmentQueryMode: 'registry_only' });
  const hybrid = getChatRetrievalPresentation({
    judgmentQueryMode: 'hybrid',
    evidenceSupportMode: 'linked_state_evidence',
  });
  const evidenceBased = getChatRetrievalPresentation({ judgmentQueryMode: 'evidence_based_synthesis' });

  assert.equal(registryOnly.label, '状态优先');
  assert.match(registryOnly.detail, /已登记的正式判断/);
  assert.equal(hybrid.label, '状态优先');
  assert.match(hybrid.detail, /DNA 信号|待确认判断/);
  assert.equal(evidenceBased.label, '证据下钻');
  assert.match(evidenceBased.detail, /状态池与原始资料/);
});

test('state source summary renders stable summary chips', () => {
  assert.deepEqual(
    formatStateSourceSummary({
      judgments: 2,
      meetings: 1,
      tasks: 3,
      openQuestions: 1,
      conflicts: 0,
      documents: 2,
    }),
    ['2 条判断', '1 次会议', '3 条任务', '1 个未决问题', '2 份原文'],
  );
});

test('state cards only fallback suppresses extended analysis rendering', () => {
  const decision = shouldRenderChatExtendedAnalysis({
    content: '当前已保留结构化回答，延展长文未完整完成。',
    stateSections: {
      official: [],
      candidate: ['待确认判断 A'],
      draftFindings: [],
      evidenceSupport: ['会议纪要：当前仍需补证据'],
      actions: [],
      risks: [],
      unknowns: [],
    },
    fallbackPresentationMode: 'state_cards_only',
  });

  assert.equal(decision.shouldRender, false);
  assert.equal(decision.blockedByPresentationMode, true);
});

test('compact user answer hides leaked process draft content', () => {
  const decision = shouldRenderChatExtendedAnalysis({
    content: '先基于客户工作台里的最新状态信号和当前已命中的高信号原始证据，给出一版可继续推进讨论的判断稿。',
    stateSections: null,
    fallbackPresentationMode: 'compact_user_answer',
  });

  assert.equal(containsChatProcessLeakMarkers('当前最值得抓住的原始观察包括：'), true);
  assert.equal(decision.shouldRender, false);
  assert.equal(decision.blockedByLeakMarkers, true);
});

test('full answer keeps extended analysis visible when not duplicated', () => {
  const decision = shouldRenderChatExtendedAnalysis({
    content: '一、机构定位\n- 当前已经形成一版可展示的正式介绍。',
    stateSections: {
      official: ['当前已经形成正式判断。'],
      candidate: [],
      draftFindings: [],
      evidenceSupport: [],
      actions: [],
      risks: [],
      unknowns: [],
    },
    fallbackPresentationMode: 'full_answer',
  });

  assert.equal(decision.shouldRender, true);
  assert.equal(decision.blockedByPresentationMode, false);
  assert.equal(decision.blockedByLeakMarkers, false);
});

test('proposal grouping keeps review, execute, and history separated', () => {
  const baseProposal = {
    clientId: 'client-1',
    riskLevel: 'medium' as ProposalRecord['riskLevel'],
    title: 'proposal',
    summary: '',
    rationale: '',
    targetRefs: [],
    sourceRefs: [],
    boundaryNotes: [],
    payload: {},
    createdBy: 'tester',
    createdAt: '2026-04-18T10:00:00',
    updatedAt: '2026-04-18T10:00:00',
  } satisfies Omit<ProposalRecord, 'id' | 'kind' | 'status'>;
  const grouped = groupProposalRecords([
    { ...baseProposal, id: 'p1', kind: 'task_prep', status: 'pending_review' },
    { ...baseProposal, id: 'p2', kind: 'meeting_prep', status: 'approved' },
    { ...baseProposal, id: 'p3', kind: 'meeting_followup', status: 'executed' },
  ]);

  assert.deepEqual(grouped.pendingReview.map((item) => item.id), ['p1']);
  assert.deepEqual(grouped.approvedExecution.map((item) => item.id), ['p2']);
  assert.deepEqual(grouped.history.map((item) => item.id), ['p3']);
});

test('proposal effect type prefers execution result and falls back to kind/status', () => {
  const prepExecuted = getProposalEffectType({
    id: 'prep',
    clientId: 'client-1',
    kind: 'task_prep',
    status: 'executed',
    riskLevel: 'low',
    title: '任务准备',
    summary: '',
    rationale: '',
    targetRefs: [],
    sourceRefs: [],
    boundaryNotes: [],
    payload: {},
    createdBy: 'tester',
    createdAt: '2026-04-18T10:00:00',
    updatedAt: '2026-04-18T10:00:00',
  });
  const followupExecuted = getProposalEffectType({
    id: 'followup',
    clientId: 'client-1',
    kind: 'meeting_followup',
    status: 'executed',
    riskLevel: 'medium',
    title: '会后跟进',
    summary: '',
    rationale: '',
    targetRefs: [],
    sourceRefs: [],
    boundaryNotes: [],
    payload: {},
    createdBy: 'tester',
    createdAt: '2026-04-18T10:00:00',
    updatedAt: '2026-04-18T10:00:00',
    executionTicket: {
      id: 'exec-1',
      proposalId: 'followup',
      clientId: 'client-1',
      executionType: 'task_creation',
      status: 'executed',
      payload: {},
      result: {
        resultType: 'followup_task_created',
        summary: '已创建任务',
        createdTaskIds: ['task-1'],
        artifactRefs: [],
      },
      createdAt: '2026-04-18T10:01:00',
      updatedAt: '2026-04-18T10:01:00',
    },
  });

  assert.equal(prepExecuted, 'prep_artifact_ready');
  assert.equal(followupExecuted, 'followup_task_created');
});
