# src/renderer/components/strategic_accompaniment/StrategicLearningListPanel.tsx

```tsx
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { BookOpen, RefreshCw, ShieldCheck, Sparkles } from 'lucide-react';
import { createHandbook, getGrowthWorkbench } from '../../lib/api';
import type { GrowthContextLink, GrowthGenericLesson, GrowthWorkbenchSnapshot, GrowthWorkbenchTask, Task } from '../../../shared/types';

type FlashLevel = 'success' | 'error' | 'info';

export type StrategicLearningTaskPayload = {
  title: string;
  desc: string;
  clientId?: string | null;
};

type StrategicLearningListPanelProps = {
  currentClientId?: string | null;
  currentClientName?: string | null;
  clients?: Array<{ id: string; name: string }>;
  tasks?: Task[];
  onTasksReload?: () => Promise<unknown> | void;
  onNavigate?: (tab: string) => void;
  onOpenContext?: (context: GrowthContextLink) => void;
  onCreateTaskFromLearning?: (payload: StrategicLearningTaskPayload) => Promise<void> | void;
  flash?: (level: FlashLevel, message: string) => void;
};

const CONFIDENCE_LABEL: Record<GrowthWorkbenchSnapshot['learningSummary']['confidence'], string> = {
  high: '高',
  medium: '中',
  low: '低',
};

function contextSubtitle(task: GrowthWorkbenchTask) {
  return task.projectStage || task.project || task.clientName || '当前任务';
}

function safeFlash(flash: StrategicLearningListPanelProps['flash'], level: FlashLevel, message: string) {
  if (flash) flash(level, message);
}

export function StrategicLearningListPanel({
  currentClientId,
  currentClientName,
  onTasksReload,
  onNavigate,
  onOpenContext,
  onCreateTaskFromLearning,
  flash,
}: StrategicLearningListPanelProps) {
  const [snapshot, setSnapshot] = useState<GrowthWorkbenchSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showReasoning, setShowReasoning] = useState(false);
  const [submittingLessonId, setSubmittingLessonId] = useState<string | null>(null);

  const loadSnapshot = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await getGrowthWorkbench({
        mode: 'strategic',
        clientId: currentClientId || undefined,
      });
      setSnapshot(next);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '学习清单加载失败');
      setSnapshot(null);
    } finally {
      setLoading(false);
    }
  }, [currentClientId]);

  useEffect(() => {
    void loadSnapshot();
  }, [loadSnapshot]);

  const openFirstContext = useCallback(
    (contexts: GrowthContextLink[]) => {
      if (!contexts.length) {
        safeFlash(flash, 'info', '当前卡片还没有可跳转的上下文。');
        return;
      }
      const target = contexts[0];
      onOpenContext?.(target);
      safeFlash(flash, 'success', `已定位到「${target.label}」`);
    },
    [flash, onOpenContext],
  );

  const convertToTask = useCallback(
    async (title: string, desc: string) => {
      if (!onCreateTaskFromLearning) {
        safeFlash(flash, 'error', '当前环境尚未接入任务创建动作。');
        return;
      }
      await onCreateTaskFromLearning({
        title: `练习：${title}`,
        desc,
        clientId: currentClientId || null,
      });
      safeFlash(flash, 'success', '已转为任务');
      await onTasksReload?.();
    },
    [currentClientId, flash, onCreateTaskFromLearning, onTasksReload],
  );

  const recordLessonExperience = useCallback(
    async (lesson: GrowthGenericLesson) => {
      if (!snapshot) return;
      setSubmittingLessonId(lesson.id);
      try {
        await createHandbook({
          title: lesson.title,
          summary: [lesson.judgment, `适用场景：${lesson.applicableScene}`, `复用提示：${lesson.reuseHint}`].filter(Boolean).join('\n'),
          tags: ['战略学习', '方法卡'],
          sourceType: 'strategic_learning_list',
          clientId: currentClientId || null,
          sourceObjectType: lesson.linkedContext?.objectType || 'growth_workbench',
          sourceObjectId: lesson.linkedContext?.objectId || null,
          sourceTitle: lesson.linkedContext?.label || lesson.title,
          contextSummary: snapshot.learningSummary.whyItMatters || snapshot.learningSummary.immediateMove,
          evidenceRefs: snapshot.reasoningTrace.evidenceRefs.slice(0, 4),
        });
        safeFlash(flash, 'success', '已记录到成长手册');
      } catch (_error) {
        onNavigate?.('growth_handbook');
        safeFlash(flash, 'info', '当前无法直接写入，已跳转成长手册继续记录。');
      } finally {
        setSubmittingLessonId(null);
      }
    },
    [currentClientId, flash, onNavigate, snapshot],
  );

  const saveAfterAction = useCallback(async () => {
    if (!snapshot) return;
    try {
      await createHandbook({
        title: snapshot.afterActionCapture.title || '战略学习沉淀',
        summary: [snapshot.afterActionCapture.summary, `沉淀类型：${snapshot.afterActionCapture.experienceType}`, `建议写回：${snapshot.afterActionCapture.recommendedWriteback}`]
          .filter(Boolean)
          .join('\n'),
        tags: ['战略学习', '复盘沉淀'],
        sourceType: 'strategic_learning_capture',
        clientId: currentClientId || null,
        contextSummary: snapshot.learningSummary.immediateMove,
      });
      safeFlash(flash, 'success', '已记录经验');
    } catch (_error) {
      onNavigate?.('growth_handbook');
      safeFlash(flash, 'info', '请在成长手册中记录这次练习经验。');
    }
  }, [currentClientId, flash, onNavigate, snapshot]);

  const sourceLabel = useMemo(() => {
    if (!snapshot) return '规则匹配';
    if (snapshot.sourceMode === 'task') return '真实任务 + 规则匹配';
    if (snapshot.sourceMode === 'growth_seed') return '成长信号 + 规则匹配';
    return '基础训练卡 + 规则匹配';
  }, [snapshot]);

  if (loading) {
    return (
      <div className="rounded-3xl border border-slate-200 bg-white px-6 py-12 text-center text-[13px] text-slate-500">
        <RefreshCw size={16} className="mx-auto mb-3 animate-spin text-slate-400" />
        正在生成战略学习清单...
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-3xl border border-red-200 bg-red-50 px-6 py-8">
        <div className="text-[14px] font-semibold text-red-600">学习清单加载失败</div>
        <div className="mt-1 text-[12px] text-red-500">{error}</div>
        <button
          type="button"
          className="mt-4 rounded-full border border-red-200 bg-white px-4 py-1.5 text-[12px] font-semibold text-red-600 hover:bg-red-50"
          onClick={() => void loadSnapshot()}
        >
          重新加载
        </button>
      </div>
    );
  }

  if (!snapshot) {
    return null;
  }

  return (
    <div className="grid gap-4">
      <section className="rounded-3xl border border-blue-100 bg-white px-5 py-5">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-[13px] font-semibold text-blue-600">
            <Sparkles size={16} />
            当前最值得练
          </div>
          <div className="rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-[11px] font-semibold text-blue-600">{sourceLabel}</div>
        </div>
        <h3 className="mt-3 text-[18px] font-bold text-slate-900">
          {snapshot.sourceMode === 'empty' ? '当前还没有真实任务，先从基础训练开始' : snapshot.learningSummary.headline}
        </h3>
        <p className="mt-2 text-[13px] leading-6 text-slate-600">{snapshot.learningSummary.whyItMatters}</p>
        <p className="mt-2 text-[13px] font-medium text-slate-700">马上做一步：{snapshot.learningSummary.immediateMove}</p>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-[12px] text-slate-500">
          <span>可信度：{CONFIDENCE_LABEL[snapshot.learningSummary.confidence]}</span>
          <span>·</span>
          <span>来源：{sourceLabel}</span>
          {snapshot.scopeClientName ? (
            <>
              <span>·</span>
              <span>客户：{snapshot.scopeClientName}</span>
            </>
          ) : currentClientName ? (
            <>
              <span>·</span>
              <span>客户：{currentClientName}</span>
            </>
          ) : null}
        </div>
        {snapshot.sourceMode === 'empty' && (
          <div className="mt-3 rounded-2xl border border-amber-100 bg-amber-50 px-4 py-3 text-[12px] text-amber-700">
            当前是基础训练模式，不是针对某个客户的个性化判断。
          </div>
        )}
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white px-5 py-5">
        <h3 className="flex items-center gap-2 text-[14px] font-semibold text-slate-800">
          <BookOpen size={16} className="text-slate-500" />
          当前任务里的学习点
        </h3>
        {!snapshot.tasks.length ? (
          <div className="mt-3 rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3 text-[12px] leading-6 text-slate-500">
            还没有进入学习清单的真实任务。你可以先从客户工作台创建任务，或把会议行动项转为任务。
          </div>
        ) : (
          <div className="mt-3 grid gap-3">
            {snapshot.tasks.map((task) => (
              <div key={task.id} className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
                <div className="text-[14px] font-semibold text-slate-800">{task.title}</div>
                <div className="mt-1 text-[12px] text-slate-500">阶段：{task.phase || '未识别'} · {contextSubtitle(task)}</div>
                <div className="mt-1 text-[12px] text-slate-600">风险/卡点：{task.currentBlocker || task.risks[0] || '暂无显式阻点'}</div>
                <div className="mt-1 text-[12px] text-slate-600">下一步建议：{task.nextAdvice || '先补齐对象和证据'}</div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="rounded-full border border-blue-200 bg-white px-3 py-1 text-[12px] font-semibold text-blue-600 hover:bg-blue-50"
                    onClick={() => openFirstContext(task.linkedContexts)}
                  >
                    打开练习
                  </button>
                  <button
                    type="button"
                    className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[12px] font-semibold text-slate-700 hover:bg-slate-100"
                    onClick={() => void convertToTask(task.title, [task.contextSummary, `阶段：${task.phase}`, `下一步：${task.nextAdvice}`].filter(Boolean).join('\n'))}
                  >
                    转为任务
                  </button>
                  <button
                    type="button"
                    className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[12px] font-semibold text-slate-700 hover:bg-slate-100"
                    onClick={() => openFirstContext(task.linkedContexts)}
                  >
                    查看上下文
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white px-5 py-5">
        <h3 className="text-[14px] font-semibold text-slate-800">可复用方法卡</h3>
        <div className="mt-3 grid gap-3">
          {snapshot.genericLessons.map((lesson) => (
            <div key={lesson.id} className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
              <div className="text-[14px] font-semibold text-slate-800">{lesson.title}</div>
              <div className="mt-1 text-[12px] text-slate-600">适用场景：{lesson.applicableScene || '当前战略陪伴任务'}</div>
              <div className="mt-1 text-[12px] text-slate-600">为什么有效：{lesson.whyItWorks || lesson.judgment}</div>
              <div className="mt-1 text-[12px] text-slate-600">如何复用：{lesson.reuseHint || '写回成长手册并转成模板任务'}</div>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  className="rounded-full border border-blue-200 bg-white px-3 py-1 text-[12px] font-semibold text-blue-600 hover:bg-blue-50"
                  onClick={() => safeFlash(flash, 'success', `已加入本周学习：${lesson.title}`)}
                >
                  加入本周学习
                </button>
                <button
                  type="button"
                  className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[12px] font-semibold text-slate-700 hover:bg-slate-100"
                  onClick={() =>
                    void convertToTask(
                      lesson.title,
                      [lesson.judgment, `适用场景：${lesson.applicableScene}`, `复用提示：${lesson.reuseHint}`].filter(Boolean).join('\n'),
                    )
                  }
                >
                  转为任务
                </button>
                <button
                  type="button"
                  disabled={submittingLessonId === lesson.id}
                  className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[12px] font-semibold text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
                  onClick={() => void recordLessonExperience(lesson)}
                >
                  {submittingLessonId === lesson.id ? '记录中...' : '记录为经验'}
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white px-5 py-5">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-[14px] font-semibold text-slate-800">当前仍缺什么</h3>
          <button
            type="button"
            className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[12px] font-semibold text-slate-700 hover:bg-slate-50"
            onClick={() => setShowReasoning((prev) => !prev)}
          >
            {showReasoning ? '收起依据' : '查看依据'}
          </button>
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
            <div className="text-[12px] font-semibold text-slate-700">本轮用到的输入</div>
            <ul className="mt-2 space-y-1 text-[12px] leading-5 text-slate-600">
              {snapshot.reasoningTrace.usedInputs.slice(0, 6).map((item) => (
                <li key={item.id}>- {item.label}{item.detail ? `：${item.detail}` : ''}</li>
              ))}
            </ul>
          </div>
          <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
            <div className="text-[12px] font-semibold text-slate-700">当前仍缺什么</div>
            <ul className="mt-2 space-y-1 text-[12px] leading-5 text-slate-600">
              {(snapshot.reasoningTrace.missingContext.length ? snapshot.reasoningTrace.missingContext : ['暂无显式缺口']).map((item) => (
                <li key={item}>- {item}</li>
              ))}
            </ul>
          </div>
        </div>
        {showReasoning && (
          <div className="mt-3 rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3 text-[12px] leading-6 text-slate-600">
            <div>规则模式：{snapshot.reasoningTrace.mode}</div>
            <div>证据引用：{snapshot.reasoningTrace.evidenceRefs.length ? snapshot.reasoningTrace.evidenceRefs.join('；') : '暂无'}</div>
            <div>AI 贡献：{snapshot.reasoningTrace.aiContribution.length ? snapshot.reasoningTrace.aiContribution.join('；') : '本轮为规则匹配，没有调用 AI 自由生成学习建议。'}</div>
          </div>
        )}
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white px-5 py-5">
        <div className="flex items-center gap-2 text-[14px] font-semibold text-slate-800">
          <ShieldCheck size={16} className="text-slate-500" />
          完成后沉淀成什么
        </div>
        <div className="mt-3 rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3 text-[12px] leading-6 text-slate-600">
          <div>建议沉淀：{snapshot.afterActionCapture.title || '本次学习动作复盘'}</div>
          <div>沉淀类型：{snapshot.afterActionCapture.experienceType || '方法卡'}</div>
          <div>建议写回：{snapshot.afterActionCapture.recommendedWriteback || '成长手册'}</div>
          {snapshot.actionsAfter.length ? (
            <div className="mt-2">后续动作：{snapshot.actionsAfter.slice(0, 3).map((item) => item.title).join('；')}</div>
          ) : null}
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-full border border-blue-200 bg-white px-3 py-1 text-[12px] font-semibold text-blue-600 hover:bg-blue-50"
            onClick={() => void saveAfterAction()}
          >
            记录经验
          </button>
          <button
            type="button"
            className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[12px] font-semibold text-slate-700 hover:bg-slate-100"
            onClick={() => onNavigate?.('growth_handbook')}
          >
            去成长手册
          </button>
          <button
            type="button"
            className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[12px] font-semibold text-slate-700 hover:bg-slate-100"
            onClick={() => safeFlash(flash, 'success', '已标记为可复用动作')}
          >
            标记已复用
          </button>
        </div>
      </section>
    </div>
  );
}

export default StrategicLearningListPanel;
```
