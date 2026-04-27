import React, { useEffect, useMemo, useState } from 'react';

import type {
  WorkspaceAnswerQualityFailure,
  WorkspaceAnswerValueDiagnostics,
  WorkspaceAnswerValueReview,
  WorkspaceAnswerValueSummary,
  WorkspaceDataCenterReadiness,
  WorkspaceValueValidationSession,
} from '../../../shared/types';
import {
  completeWorkspaceValueValidationQuestion,
  createWorkspaceValueValidationSession,
  finishWorkspaceValueValidationSession,
  getWorkspaceAnswerValueDiagnostics,
  getWorkspaceAnswerValueSummary,
  getWorkspaceDataCenterReadiness,
  listWorkspaceAnswerQualityFailures,
  listWorkspaceAnswerValueReviews,
  listWorkspaceValueValidationSessions,
  resolveWorkspaceAnswerQualityFailure,
} from '../../lib/api';

type SectionErrors = {
  diagnosticsError: string;
  summaryError: string;
  readinessError: string;
  sessionsError: string;
  failuresError: string;
  reviewsError: string;
};

const EMPTY_ERRORS: SectionErrors = {
  diagnosticsError: '',
  summaryError: '',
  readinessError: '',
  sessionsError: '',
  failuresError: '',
  reviewsError: '',
};

export function WorkspaceAnswerValuePanel({ clientId }: { clientId?: string | null }) {
  const [diagnostics, setDiagnostics] = useState<WorkspaceAnswerValueDiagnostics | null>(null);
  const [summary, setSummary] = useState<WorkspaceAnswerValueSummary | null>(null);
  const [readiness, setReadiness] = useState<WorkspaceDataCenterReadiness | null>(null);
  const [sessions, setSessions] = useState<WorkspaceValueValidationSession[]>([]);
  const [failures, setFailures] = useState<WorkspaceAnswerQualityFailure[]>([]);
  const [reviews, setReviews] = useState<WorkspaceAnswerValueReview[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [busyAction, setBusyAction] = useState<string>('');
  const [sectionErrors, setSectionErrors] = useState<SectionErrors>(EMPTY_ERRORS);
  const [selectedReviewId, setSelectedReviewId] = useState<string>('');

  const canLoad = Boolean(clientId && clientId.trim());

  const refresh = async () => {
    if (!canLoad || !clientId) return;
    setLoading(true);
    setError('');
    const [diagResult, summaryResult, readinessResult, sessionsResult, failuresResult, reviewsResult] = await Promise.allSettled([
      getWorkspaceAnswerValueDiagnostics(clientId, 50),
      getWorkspaceAnswerValueSummary(clientId),
      getWorkspaceDataCenterReadiness(clientId),
      listWorkspaceValueValidationSessions({ clientId, limit: 10 }),
      listWorkspaceAnswerQualityFailures({ clientId, limit: 20 }),
      listWorkspaceAnswerValueReviews({ clientId, limit: 20 }),
    ]);

    const nextErrors: SectionErrors = { ...EMPTY_ERRORS };

    if (diagResult.status === 'fulfilled') {
      setDiagnostics(diagResult.value);
    } else {
      nextErrors.diagnosticsError = diagResult.reason instanceof Error ? diagResult.reason.message : '读取 diagnostics 失败';
    }
    if (summaryResult.status === 'fulfilled') {
      setSummary(summaryResult.value);
    } else {
      nextErrors.summaryError = summaryResult.reason instanceof Error ? summaryResult.reason.message : '读取 summary 失败';
    }
    if (readinessResult.status === 'fulfilled') {
      setReadiness(readinessResult.value);
    } else {
      nextErrors.readinessError = readinessResult.reason instanceof Error ? readinessResult.reason.message : '读取 readiness 失败';
    }
    if (sessionsResult.status === 'fulfilled') {
      setSessions(sessionsResult.value);
    } else {
      nextErrors.sessionsError = sessionsResult.reason instanceof Error ? sessionsResult.reason.message : '读取 sessions 失败';
    }
    if (failuresResult.status === 'fulfilled') {
      setFailures(failuresResult.value);
    } else {
      nextErrors.failuresError = failuresResult.reason instanceof Error ? failuresResult.reason.message : '读取 failures 失败';
    }
    if (reviewsResult.status === 'fulfilled') {
      setReviews(reviewsResult.value);
    } else {
      nextErrors.reviewsError = reviewsResult.reason instanceof Error ? reviewsResult.reason.message : '读取 reviews 失败';
    }

    setSectionErrors(nextErrors);
    setLoading(false);
  };

  useEffect(() => {
    void refresh();
  }, [clientId]);

  useEffect(() => {
    const handler = () => {
      void refresh();
    };
    window.addEventListener('workspace-answer-value-refresh', handler);
    return () => window.removeEventListener('workspace-answer-value-refresh', handler);
  }, [clientId]);

  useEffect(() => {
    if (!reviews.length) {
      setSelectedReviewId('');
      return;
    }
    if (!selectedReviewId || !reviews.some((item) => item.id === selectedReviewId)) {
      setSelectedReviewId(reviews[0].id);
    }
  }, [reviews, selectedReviewId]);

  const topFallbackReason = useMemo(() => diagnostics?.topFailureReasons?.[0] ?? null, [diagnostics]);
  const activeSession = useMemo(
    () => sessions.find((item) => item.status === 'running') ?? sessions[0] ?? null,
    [sessions],
  );
  const nextQuestion = useMemo(() => {
    if (!activeSession) return null;
    const completed = new Set(activeSession.completedQuestionIds || []);
    return (activeSession.questionSet || []).find((item) => !completed.has(item.id)) ?? null;
  }, [activeSession]);
  const selectedReview = useMemo(
    () => reviews.find((item) => item.id === selectedReviewId) ?? null,
    [reviews, selectedReviewId],
  );
  const openFailures = useMemo(() => failures.filter((item) => item.status === 'open').slice(0, 10), [failures]);

  if (!canLoad || !clientId) return null;

  const runStartSession = async () => {
    setBusyAction('start-session');
    try {
      await createWorkspaceValueValidationSession(clientId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : '启动 10 问价值验证失败');
    } finally {
      setBusyAction('');
    }
  };

  const runCompleteNextQuestion = async () => {
    if (!activeSession || !nextQuestion || !selectedReview) {
      setError('需要先有运行中的验证 session，并明确选择本题对应回答。');
      return;
    }
    setBusyAction('complete-question');
    try {
      await completeWorkspaceValueValidationQuestion(activeSession.id, {
        questionId: nextQuestion.id,
        reviewId: selectedReview.id,
        messageId: selectedReview.messageId,
        usableAnswer: selectedReview.usableAnswer ?? null,
        retryBannerShown: selectedReview.shouldShowRetryBanner,
        manualBaselineMinutes: selectedReview.manualBaselineMinutes ?? null,
        dataCenterReviewMinutes: selectedReview.dataCenterReviewMinutes ?? null,
        reviewerNote: selectedReview.reviewerNote || '',
      });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : '完成当前验证题失败');
    } finally {
      setBusyAction('');
    }
  };

  const runFinishSession = async () => {
    if (!activeSession) return;
    setBusyAction('finish-session');
    try {
      await finishWorkspaceValueValidationSession(activeSession.id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : '完成验证 session 失败');
    } finally {
      setBusyAction('');
    }
  };

  const runResolveFailure = async (failureId: string) => {
    try {
      await resolveWorkspaceAnswerQualityFailure(failureId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : '标记 failure 失败');
    }
  };

  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-[12px] font-bold text-gray-800">Workspace Answer Value</p>
          <p className="text-[11px] text-gray-500">客户工作台可用回答、行动转化与 10 问价值验证</p>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={loading}
          className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1 text-[10px] font-semibold text-gray-700 hover:bg-gray-100 disabled:opacity-50"
        >
          {loading ? '刷新中…' : '刷新诊断'}
        </button>
      </div>

      <div className="grid grid-cols-2 gap-2 text-[11px] text-gray-700">
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1">
          usableAnswerRate: {(diagnostics?.usableAnswerRate ?? 0).toFixed(2)}
        </div>
        <div className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1">
          retryBannerRate: {(diagnostics?.retryBannerWouldShowRate ?? 0).toFixed(2)}
        </div>
        <div className="rounded-md border border-blue-200 bg-blue-50 px-2 py-1">
          kernelPrimaryUsedRate: {(diagnostics?.kernelPrimaryUsedRate ?? 0).toFixed(2)}
        </div>
        <div className="rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1">
          readyOrUsableRate: {(diagnostics?.readyOrUsableRate ?? 0).toFixed(2)}
        </div>
        <div className="rounded-md border border-rose-200 bg-rose-50 px-2 py-1">
          needsRetryRate: {(diagnostics?.needsRetryRate ?? 0).toFixed(2)}
        </div>
        <div className="rounded-md border border-violet-200 bg-violet-50 px-2 py-1">
          proposalCreatedFromAnswer: {summary?.proposalCreatedFromAnswerCount ?? 0}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
        <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-[11px] text-gray-600 space-y-1">
          <div>top fallback reason: {topFallbackReason ? `${topFallbackReason.key} (${topFallbackReason.count})` : 'n/a'}</div>
          <div>estimated time saved rate: {(summary?.estimatedTimeSavedRate ?? 0).toFixed(2)}</div>
          <div>
            reviews: +{summary?.positiveReviewCount ?? 0} / -{summary?.negativeReviewCount ?? 0}
            {summary?.lastReviewedAt ? ` · last ${summary.lastReviewedAt}` : ''}
          </div>
          <div>executionTicketCreatedFromAnswer: {summary?.executionTicketCreatedFromAnswerCount ?? 0}</div>
          {summary?.metricErrors?.length ? (
            <div className="text-rose-600">metric errors: {summary.metricErrors.join(' | ')}</div>
          ) : null}
        </div>
        <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-[11px] text-gray-600 space-y-1">
          <div className="font-semibold text-gray-700">数据中心准备度摘要</div>
          <div>文档总数: {readiness?.summary.totalDocuments ?? 0}</div>
          <div>解析失败: {readiness?.summary.failedDocuments ?? 0}</div>
          <div>vector: {readiness?.summary.vectorStatus ?? 'unknown'}</div>
          <div>上下文质量: {readiness?.summary.contextQuality ?? 'none'}</div>
        </div>
      </div>

      {(sectionErrors.diagnosticsError || sectionErrors.summaryError || sectionErrors.readinessError) ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-700 space-y-1">
          {sectionErrors.diagnosticsError ? <div>diagnostics: {sectionErrors.diagnosticsError}</div> : null}
          {sectionErrors.summaryError ? <div>summary: {sectionErrors.summaryError}</div> : null}
          {sectionErrors.readinessError ? <div>readiness: {sectionErrors.readinessError}</div> : null}
        </div>
      ) : null}

      <div className="rounded-xl border border-gray-200 bg-gray-50 px-3 py-3 space-y-2">
        <div className="flex items-center justify-between gap-2">
          <div>
            <p className="text-[11px] font-bold text-gray-700">10 问价值验证</p>
            <p className="text-[10px] text-gray-500">选真实客户，连续问 10 个高频问题并记录可用性与耗时</p>
          </div>
          <button
            type="button"
            onClick={() => void runStartSession()}
            disabled={busyAction === 'start-session'}
            className="rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 text-[10px] font-semibold text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
          >
            {busyAction === 'start-session' ? '启动中…' : '开始 10 问价值验证'}
          </button>
        </div>
        {activeSession ? (
          <div className="space-y-2 text-[11px] text-gray-700">
            <div>当前 session: {activeSession.id} · 进度 {activeSession.summary.completed}/{activeSession.questionSet.length} · verdict {activeSession.summary.verdict}</div>
            {nextQuestion ? <div>下一题: {nextQuestion.prompt}</div> : <div>当前 session 已完成所有问题。</div>}
            <div className="rounded-md border border-gray-200 bg-white px-3 py-2 space-y-2">
              <div className="font-semibold text-gray-700">选择本题对应回答</div>
              {selectedReview ? (
                <div className="text-[10px] text-gray-500">当前已选：{selectedReview.messageId} · {selectedReview.usableAnswer === false ? '不可用' : '可用/待确认'}</div>
              ) : (
                <div className="text-[10px] text-gray-500">当前没有可用 review，请先在回答卡上标记可用/不可用或记录耗时。</div>
              )}
              <div className="space-y-1 max-h-40 overflow-y-auto pr-1">
                {reviews.slice(0, 8).map((review) => (
                  <label key={review.id} className={`flex cursor-pointer items-start gap-2 rounded-md border px-2 py-2 ${selectedReviewId === review.id ? 'border-indigo-200 bg-indigo-50' : 'border-gray-200 bg-gray-50'}`}>
                    <input
                      type="radio"
                      name="workspace-value-review"
                      checked={selectedReviewId === review.id}
                      onChange={() => setSelectedReviewId(review.id)}
                    />
                    <div className="min-w-0">
                      <div className="text-[11px] font-semibold text-gray-700">{review.messageId}</div>
                      <div className="text-[10px] text-gray-500 line-clamp-2">{review.prompt || review.reviewerNote || '未记录问题'}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {nextQuestion ? (
                <button
                  type="button"
                  onClick={() => navigator.clipboard?.writeText(nextQuestion.prompt)}
                  className="rounded-md border border-gray-200 bg-white px-2 py-1 text-[10px] font-semibold text-gray-700 hover:bg-gray-100"
                >
                  复制下一问题
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => void runCompleteNextQuestion()}
                disabled={!nextQuestion || !selectedReview || busyAction === 'complete-question'}
                className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-[10px] font-semibold text-emerald-700 hover:bg-emerald-100 disabled:opacity-50"
              >
                {busyAction === 'complete-question' ? '提交中…' : '用选中复核完成当前题'}
              </button>
              <button
                type="button"
                onClick={() => void runFinishSession()}
                disabled={busyAction === 'finish-session'}
                className="rounded-md border border-violet-200 bg-violet-50 px-2 py-1 text-[10px] font-semibold text-violet-700 hover:bg-violet-100 disabled:opacity-50"
              >
                {busyAction === 'finish-session' ? '完成中…' : '生成价值验证报告'}
              </button>
            </div>
          </div>
        ) : (
          <div className="text-[11px] text-gray-500">当前没有运行中的验证 session。</div>
        )}
        {sectionErrors.sessionsError ? <div className="text-[11px] text-amber-700">sessions: {sectionErrors.sessionsError}</div> : null}
        {sectionErrors.reviewsError ? <div className="text-[11px] text-amber-700">reviews: {sectionErrors.reviewsError}</div> : null}
      </div>

      <div className="rounded-xl border border-gray-200 bg-gray-50 px-3 py-3 space-y-2">
        <p className="text-[11px] font-bold text-gray-700">最近不可用回答</p>
        {openFailures.length > 0 ? (
          <div className="space-y-2">
            {openFailures.map((failure) => (
              <div key={failure.id} className="rounded-md border border-gray-200 bg-white px-3 py-2 text-[11px] text-gray-700">
                <div className="flex items-center justify-between gap-2">
                  <div className="font-semibold">{failure.failureType}</div>
                  <button
                    type="button"
                    onClick={() => void runResolveFailure(failure.id)}
                    className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1 text-[10px] font-semibold text-gray-700 hover:bg-gray-100"
                  >
                    标记已处理
                  </button>
                </div>
                <div className="mt-1 text-gray-500">{failure.prompt || failure.messageId || '未记录原问题'}</div>
                <div className="mt-1 text-gray-500">severity: {failure.severity} · status: {failure.status}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-[11px] text-gray-500">当前没有 open failure。</div>
        )}
        {sectionErrors.failuresError ? <div className="text-[11px] text-amber-700">failures: {sectionErrors.failuresError}</div> : null}
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => navigator.clipboard?.writeText('cd backend && uv run python scripts/eval_customer_workspace_answer_value_p27.py --strict')}
          className="rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 text-[10px] font-semibold text-indigo-700 hover:bg-indigo-100"
        >
          复制 value eval 命令
        </button>
        <button
          type="button"
          onClick={() => navigator.clipboard?.writeText('cd backend && uv run python scripts/check_customer_workspace_value_runtime_alignment_p29.py --strict')}
          className="rounded-md border border-sky-200 bg-sky-50 px-2 py-1 text-[10px] font-semibold text-sky-700 hover:bg-sky-100"
        >
          复制 runtime alignment 命令
        </button>
      </div>
      {error ? (
        <div className="rounded-md border border-rose-200 bg-rose-50 px-2 py-2 text-[11px] text-rose-700">{error}</div>
      ) : null}
    </div>
  );
}
