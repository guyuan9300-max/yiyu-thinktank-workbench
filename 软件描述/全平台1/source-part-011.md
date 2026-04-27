# 益语软件平台源码导出（第011卷）

- 导出时间: 2026-04-20 18:08:04
- 内容范围: 主仓库源码 + mobile 子仓库源码
- 说明: 每个条目为完整源码文件。

## `src/renderer/components/client_workspace/ClientProjectSetupPage.tsx`

- 编码: `utf-8`

~~~tsx
import React from 'react';
import { ArrowRight, CalendarClock, CheckCircle2, ClipboardList, FolderOpen, Sparkles, UploadCloud } from 'lucide-react';

import type { ClientDnaModule, KnowledgeJob, KnowledgeStatus, ProjectFlow, ProjectFlowPayload, ProjectModule, ProjectModulePayload } from '../../../shared/types';

type ClientDnaModuleMeta = {
  moduleKey: ClientDnaModule['moduleKey'];
  title: string;
  helper: string;
};

type ImportFeedback = {
  tone: 'info' | 'success' | 'error';
  text: string;
  detail?: string;
  timestamp: number;
};

type ClientProjectSetupPageProps = {
  clientName: string;
  modules: ClientDnaModule[];
  projectModules: ProjectModule[];
  projectFlows: ProjectFlow[];
  moduleMetas: ClientDnaModuleMeta[];
  sourceDocumentCount: number;
  isKnowledgeBuilding: boolean;
  knowledgeStatus?: KnowledgeStatus | null;
  latestKnowledgeJob?: KnowledgeJob | null;
  isImportSubmitting?: boolean;
  isTemplateFilling?: boolean;
  latestImportFeedback?: ImportFeedback | null;
  onImportFiles: () => void;
  onImportFolder: () => void;
  onGenerateCandidates: () => void;
  onCopyModulePrompt: (moduleKey: ClientDnaModule['moduleKey']) => void;
  onUploadModule: (moduleKey: ClientDnaModule['moduleKey']) => void;
  onCreateProjectModule: (payload: ProjectModulePayload) => void;
  onCreateProjectFlow: (payload: ProjectFlowPayload) => void;
  onOpenDnaPanel: () => void;
  onContinueWorkspace: () => void;
};

function formatModuleTime(value?: string | null) {
  if (!value) return '待开始';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function ClientProjectSetupPage({
  clientName,
  sourceDocumentCount,
  isKnowledgeBuilding,
  knowledgeStatus,
  latestKnowledgeJob,
  isImportSubmitting = false,
  isTemplateFilling = false,
  latestImportFeedback,
  onImportFiles,
  onImportFolder,
  onGenerateCandidates,
  onContinueWorkspace,
}: ClientProjectSetupPageProps) {
  const hasSourceDocuments = sourceDocumentCount > 0;
  const activeJobs = (knowledgeStatus?.pendingJobs || 0) + (knowledgeStatus?.runningJobs || 0);
  const scanStatusLabel = !hasSourceDocuments
    ? '等待导入资料'
    : isKnowledgeBuilding
      ? '正在建库与扫描'
      : '资料已入库';
  const scanStatusDescription = !hasSourceDocuments
    ? '先把过去已有的 Word、PDF、Markdown、PPT、纪要与方案导进来，系统才会开始理解这个客户。'
    : isKnowledgeBuilding
      ? '系统正在把原始资料转换为可引用的知识结构。你可以继续追加资料，不需要停下来等。'
      : '原始资料已经进入知识库。你现在可以进入客户工作台继续问答，也可以继续补充资料。';
  const latestJobProcessed = latestKnowledgeJob?.processedItems || 0;
  const latestJobTotal = latestKnowledgeJob?.totalItems || 0;
  const hasVisibleProgress = isImportSubmitting || isTemplateFilling || isKnowledgeBuilding || latestJobTotal > 0;
  const isIndeterminateProgress = hasVisibleProgress && latestJobTotal === 0 && (isImportSubmitting || isTemplateFilling || isKnowledgeBuilding);
  const progressRatio = latestJobTotal > 0
    ? Math.max(0, Math.min(1, latestJobProcessed / latestJobTotal))
    : hasVisibleProgress
      ? 0.12
      : hasSourceDocuments
        ? 1
        : 0;
  const progressPercent = hasVisibleProgress && progressRatio < 0.18
    ? 18
    : Math.round(progressRatio * 100);
  const progressLabel = isTemplateFilling
    ? '正在分析模板并自动填写'
    : isImportSubmitting
      ? '正在把资料加入入库队列'
      : isKnowledgeBuilding
        ? `正在处理资料 ${latestJobProcessed}/${latestJobTotal || '…'}`
        : hasSourceDocuments
          ? '资料已准备完成'
          : '等待导入资料';
  const progressHint = isTemplateFilling
    ? '系统会结合当前客户知识库自动填写模板，完成后直接打开生成文件。'
    : isImportSubmitting
      ? '资料已接收，正在开始扫描、归档和建库。你可以继续停留在这里观察进度。'
      : isKnowledgeBuilding
        ? '后台正在持续处理资料，进度会自动刷新。你也可以继续追加资料。'
      : hasSourceDocuments
        ? '已经可以进入客户工作台继续提问。'
        : '导入任意一批已有资料后，这里会开始显示动态进度。';
  const shouldShowLiveProgress = hasVisibleProgress;
  const latestImportToneClasses = latestImportFeedback?.tone === 'error'
    ? 'border-rose-200 bg-rose-50 text-rose-700'
    : latestImportFeedback?.tone === 'success'
      ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
      : 'border-gray-200 bg-gray-50 text-gray-600';

  return (
    <div className="space-y-6 xl:space-y-7">
      <section className="rounded-[28px] border border-[#DCE6FF] bg-[linear-gradient(135deg,rgba(255,255,255,1),rgba(238,244,255,0.92))] px-6 py-6 shadow-[0_20px_40px_rgba(91,123,254,0.08)] xl:px-7">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div className="max-w-[760px]">
            <div className="inline-flex items-center gap-2 rounded-full bg-white/85 px-3 py-1 text-[11px] font-bold text-[#5B7BFE] shadow-sm">
              <Sparkles size={13} />
              项目资料导入引导
            </div>
            <h3 className="mt-4 text-[24px] font-bold leading-tight text-gray-900">
              {clientName} 已创建成功，第一步先导入已有资料
            </h3>
            <p className="mt-3 max-w-[700px] text-[13px] leading-7 text-gray-600">
              这里不再要求你先写四张 Markdown 资料卡。先把过去已有的 Word、PDF、Markdown、PPT、纪要和方案导进来，系统会自动分析、归档、建库，再把这些资料变成客户工作台、任务、会议和学习系统可共用的项目上下文。
            </p>
          </div>
          <div className="rounded-[24px] border border-white/80 bg-white/90 px-5 py-4 shadow-[0_12px_30px_rgba(15,23,42,0.06)]">
            <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-gray-400">资料导入进度</p>
            <div className="mt-2 flex items-end gap-2">
              <span className="text-[28px] font-bold text-gray-900">{sourceDocumentCount}</span>
              <span className="pb-1 text-[12px] font-semibold text-[#5B7BFE]">份资料</span>
            </div>
            <p className="mt-2 text-[12px] leading-6 text-gray-500">
              {hasSourceDocuments ? '资料已经进入这位客户的知识库。' : '现在还没有导入原始资料。'}
            </p>
          </div>
        </div>

        <div className="mt-6 rounded-[26px] border border-[#DCE6FF] bg-white/92 px-5 py-5 shadow-[0_14px_30px_rgba(91,123,254,0.08)]">
          <div className="flex flex-col items-center text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-[22px] bg-[#F2F5FF] text-[#5B7BFE] shadow-sm">
              <FolderOpen size={24} />
            </div>
            <h4 className="mt-4 text-[22px] font-bold text-gray-900">把已有资料导进来，系统自动归档和建库</h4>
            <p className="mt-3 max-w-[760px] text-[13px] leading-7 text-gray-600">
              资料导入后，系统会自动完成文件归档、知识加工和后续候选上下文生成。DNA 只是后续补充项，不再是这一步的入口条件。
            </p>
          </div>

          <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2">
            <button
              type="button"
              onClick={onImportFiles}
              className="inline-flex items-center justify-center gap-2 rounded-2xl bg-[#5B7BFE] px-5 py-4 text-[14px] font-bold text-white shadow-[0_12px_24px_rgba(91,123,254,0.28)] transition-colors hover:bg-[#4A6BE6]"
            >
              <UploadCloud size={17} />
              导入文件
            </button>
            <button
              type="button"
              onClick={onImportFolder}
              className="inline-flex items-center justify-center gap-2 rounded-2xl border border-[#D8E5FF] bg-white px-5 py-4 text-[14px] font-bold text-[#4A63CF] transition-colors hover:border-[#5B7BFE] hover:text-[#3652c9]"
            >
              <FolderOpen size={17} />
              导入文件夹
            </button>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-3">
            <div className="rounded-2xl bg-[#F8FAFF] px-4 py-3 text-[12px] leading-6 text-gray-600">
              支持 Word、PDF、Markdown、PPT、纪要、方案等原始资料，导入后会自动分析类型并归档。
            </div>
            <div className="rounded-2xl bg-[#F8FAFF] px-4 py-3 text-[12px] leading-6 text-gray-600">
              系统会把资料加工成客户工作台可检索的知识结构，而不是先要求你手工补背景卡。
            </div>
            <div className="rounded-2xl bg-[#F8FAFF] px-4 py-3 text-[12px] leading-6 text-gray-600">
              资料入库后，你可以直接进入工作台继续提问，后续再补 DNA 或人工修正都来得及。
            </div>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            {hasSourceDocuments && (
              <button
                type="button"
                onClick={onGenerateCandidates}
                className="inline-flex items-center gap-2 rounded-2xl border border-[#D8E5FF] bg-white px-4 py-3 text-[13px] font-bold text-[#4A63CF] transition-colors hover:border-[#5B7BFE] hover:text-[#3652c9]"
              >
                <Sparkles size={15} />
                重新扫描资料
              </button>
            )}
            <button
              type="button"
              onClick={onContinueWorkspace}
              className="inline-flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-bold text-gray-600 transition-colors hover:border-[#5B7BFE] hover:text-[#5B7BFE]"
            >
              稍后进入工作台
              <ArrowRight size={15} />
            </button>
          </div>

          {latestImportFeedback && !shouldShowLiveProgress && (
            <div className={`mt-4 rounded-2xl border px-4 py-3 text-[12px] leading-6 ${latestImportToneClasses}`}>
              <p className="font-semibold">{latestImportFeedback.text}</p>
              {latestImportFeedback.detail && (
                <p className="mt-1 opacity-80">{latestImportFeedback.detail}</p>
              )}
            </div>
          )}
        </div>
      </section>

      <section className="rounded-[26px] border border-gray-200 bg-white px-6 py-6 shadow-sm xl:px-7">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-[#7C93F9]">资料扫描状态</p>
            <h4 className="mt-2 text-[20px] font-bold text-gray-900">{scanStatusLabel}</h4>
            <p className="mt-2 max-w-[760px] text-[12px] leading-7 text-gray-500">{scanStatusDescription}</p>
          </div>
          <div className="rounded-[22px] border border-blue-100 bg-blue-50/70 px-4 py-3 text-[12px] font-semibold text-[#4A63CF]">
            最近一次完成：{formatModuleTime(knowledgeStatus?.lastSuccessfulRunAt)}
          </div>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-4">
          <div className="rounded-[22px] border border-gray-100 bg-gray-50/80 px-4 py-4">
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">原始资料</p>
            <p className="mt-3 text-[24px] font-bold text-gray-900">{sourceDocumentCount}</p>
            <p className="mt-1 text-[12px] text-gray-500">已导入文档数</p>
          </div>
          <div className="rounded-[22px] border border-gray-100 bg-gray-50/80 px-4 py-4">
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">后台作业</p>
            <p className="mt-3 text-[24px] font-bold text-gray-900">{activeJobs}</p>
            <p className="mt-1 text-[12px] text-gray-500">排队 / 运行中的建库任务</p>
          </div>
          <div className="rounded-[22px] border border-gray-100 bg-gray-50/80 px-4 py-4">
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">知识状态</p>
            <p className="mt-3 text-[24px] font-bold text-gray-900">{isKnowledgeBuilding ? '处理中' : hasSourceDocuments ? '可用' : '未开始'}</p>
            <p className="mt-1 text-[12px] text-gray-500">是否已可用于正式问答</p>
          </div>
          <div className="rounded-[22px] border border-gray-100 bg-gray-50/80 px-4 py-4">
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">待处理项目</p>
            <p className="mt-3 text-[24px] font-bold text-gray-900">{knowledgeStatus?.reviewPendingDocuments || 0}</p>
            <p className="mt-1 text-[12px] text-gray-500">待人工复核或补充的资料</p>
          </div>
        </div>

        {shouldShowLiveProgress && (
          <div className="mt-5 rounded-[22px] border border-[#D8E5FF] bg-[#F8FAFF] px-4 py-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[13px] font-bold text-gray-900">{progressLabel}</p>
                <p className="mt-1 text-[12px] leading-6 text-gray-500">{progressHint}</p>
              </div>
              <div className="shrink-0 text-right">
                <p className="text-[20px] font-bold text-[#4A63CF]">{progressPercent}%</p>
                <p className="text-[11px] text-gray-400">估算进度</p>
              </div>
            </div>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-white shadow-inner">
              <div
                className={`h-full rounded-full bg-[linear-gradient(90deg,#5B7BFE,#7B93FF)] transition-[width] duration-500 ease-out ${isIndeterminateProgress ? 'animate-pulse' : ''}`}
                style={{ width: `${Math.max(0, Math.min(100, progressPercent))}%` }}
              />
            </div>
            {latestKnowledgeJob && (
              <p className="mt-3 text-[11px] text-gray-500">
                最近任务：{latestKnowledgeJob.jobType} · {latestKnowledgeJob.status} · {latestJobProcessed}/{latestJobTotal || '…'}
              </p>
            )}
          </div>
        )}

        {knowledgeStatus?.lastJobError && (
          <div className="mt-4 rounded-[22px] border border-rose-100 bg-rose-50 px-4 py-4 text-[12px] leading-6 text-rose-600">
            最近一次建库或扫描有报错：{knowledgeStatus.lastJobError}
          </div>
        )}
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        {[
          {
            icon: ClipboardList,
            title: '客户工作台',
            copy: '资料入库后，问答会优先基于这些原始资料做正式分析，不再先要求手工补卡。',
          },
          {
            icon: CalendarClock,
            title: '会议与任务',
            copy: '后续的会议纪要、任务理解和复盘会自动挂到这个客户的资料上下文里。',
          },
          {
            icon: CheckCircle2,
            title: '后续补充 DNA',
            copy: 'DNA 仍然可以补，但它属于后续强化理解，不再是进入工作台的前置门槛。',
          },
        ].map((item) => (
          <article key={item.title} className="rounded-[24px] border border-gray-200 bg-white p-5 shadow-sm">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#F2F5FF] text-[#5B7BFE]">
              <item.icon size={19} />
            </div>
            <h4 className="mt-4 text-[16px] font-bold text-gray-900">{item.title}</h4>
            <p className="mt-2 text-[12px] leading-6 text-gray-600">{item.copy}</p>
          </article>
        ))}
      </section>
    </div>
  );
}
~~~

## `src/renderer/components/collab/CollabDialogs.tsx`

- 编码: `utf-8`

~~~tsx
import React from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Database,
  Download,
  Eye,
  Layers3,
  RefreshCw,
  UploadCloud,
  X,
} from 'lucide-react';
import type { PullPreview, PushPreview } from '../../../shared/types';

type PreviewMode = 'push' | 'pull';

type CollabPreviewDialogProps = {
  open: boolean;
  mode: PreviewMode;
  preview: PushPreview | PullPreview | null;
  selectedPaths: string[];
  message: string;
  errorMessage?: string | null;
  busy: boolean;
  onClose: () => void;
  onTogglePath: (targetPath: string) => void;
  onToggleEffectPaths: (targetPaths: string[]) => void;
  onMessageChange: (nextValue: string) => void;
  onConfirm: () => void;
};

function ActionButton({
  primary,
  disabled,
  className = '',
  onClick,
  children,
}: {
  primary?: boolean;
  disabled?: boolean;
  className?: string;
  onClick?: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-2 rounded-2xl px-4 py-2.5 text-[13px] font-bold transition-all ${
        primary
          ? 'bg-[#5B7BFE] text-white shadow-[0_8px_24px_rgba(91,123,254,0.24)] hover:bg-[#4a6be6] disabled:cursor-not-allowed disabled:opacity-60'
          : 'border border-gray-200 bg-white text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60'
      } ${className}`}
    >
      {children}
    </button>
  );
}

function visibilityIcon(mode: 'visible' | 'mixed' | 'background') {
  if (mode === 'visible') return <Eye size={15} className="text-[#5B7BFE]" />;
  if (mode === 'mixed') return <Layers3 size={15} className="text-emerald-600" />;
  return <Database size={15} className="text-amber-600" />;
}

function visibilityText(mode: 'visible' | 'mixed' | 'background') {
  if (mode === 'visible') return '你能直接看到';
  if (mode === 'mixed') return '界面和行为都会受影响';
  return '主要影响后台/配置';
}

export function CollabPreviewDialog({
  open,
  mode,
  preview,
  selectedPaths,
  message,
  errorMessage,
  busy,
  onClose,
  onTogglePath,
  onToggleEffectPaths,
  onMessageChange,
  onConfirm,
}: CollabPreviewDialogProps) {
  if (!open || !preview) return null;
  const selectedSet = new Set(selectedPaths);
  const actionLabel = mode === 'push' ? '提交并推送我的修改' : '预览并同步最新版本';
  const noPushChanges = mode === 'push' && preview.executionBlockReason === '当前没有可提交的本地文件改动。';
  const alreadySynced = mode === 'pull' && preview.executionBlockReason === 'main 当前已经是最新。';
  const confirmLabel = noPushChanges
    ? '当前已同步到 main'
    : alreadySynced
      ? '当前已经是最新版本'
      : mode === 'push'
        ? '确认推到 main'
        : '确认从 main 同步';
  const confirmDisabled = busy || Boolean(preview.executionBlockReason);

  return (
    <div className="fixed inset-0 z-[80] overflow-y-auto bg-black/30 px-4 py-8 backdrop-blur-sm">
      <div className="mx-auto flex min-h-full items-center justify-center">
      <div className="flex max-h-[calc(100vh-4rem)] w-full max-w-6xl flex-col overflow-hidden rounded-[28px] border border-white/70 bg-white shadow-[0_24px_90px_rgba(15,23,42,0.16)]">
        <div className="flex items-start justify-between gap-4 border-b border-gray-100 px-6 py-5">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-[#5B7BFE]">协作同步</p>
            <h2 className="mt-2 text-[22px] font-bold text-gray-900">{actionLabel}</h2>
            <p className="mt-2 text-[13px] leading-6 text-gray-500">
              当前仓库：{preview.status.repoName || '未命名仓库'} · 分支 {preview.status.branch || '未知'}
            </p>
          </div>
          <button
            type="button"
            className="rounded-2xl border border-gray-200 bg-white p-2 text-gray-400 transition hover:text-gray-700"
            onClick={busy ? undefined : onClose}
            aria-label="关闭协作预览"
          >
            <X size={18} />
          </button>
        </div>

        <div className="min-h-0 overflow-y-auto px-6 py-6">
        <div className="grid gap-6 lg:grid-cols-[1.25fr_0.75fr]">
          <div className="space-y-4">
            {preview.notice && (
              <div className="rounded-2xl border border-blue-200 bg-blue-50 px-4 py-3 text-[12px] font-semibold leading-6 text-[#4256C5]">
                <div className="flex items-start gap-2">
                  <AlertCircle size={16} className="mt-0.5 shrink-0" />
                  <span>{preview.notice}</span>
                </div>
              </div>
            )}

            {preview.executionBlockReason && (
              <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-[12px] font-semibold leading-6 text-amber-800">
                <div className="flex items-start gap-2">
                  <AlertCircle size={16} className="mt-0.5 shrink-0" />
                  <span>{preview.executionBlockReason}</span>
                </div>
              </div>
            )}

            {errorMessage && (
              <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-[12px] font-semibold leading-6 text-rose-800">
                <div className="flex items-start gap-2">
                  <AlertCircle size={16} className="mt-0.5 shrink-0" />
                  <span>{errorMessage}</span>
                </div>
              </div>
            )}

            <div className="rounded-3xl border border-gray-100 bg-gray-50 px-4 py-4">
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">你会先看到这些变化</p>
              <p className="mt-2 text-[13px] leading-6 text-gray-600">
                先看软件会怎么变，再决定要不要执行。文件清单还在下面，但它现在只是辅助证据。
              </p>
              <div className="mt-4 grid gap-3">
                {preview.effects.map((effect) => {
                  const selectedCount = effect.relatedPaths.filter((targetPath) => selectedSet.has(targetPath)).length;
                  const allSelected = selectedCount > 0 && selectedCount === effect.relatedPaths.length;
                  const partiallySelected = selectedCount > 0 && selectedCount < effect.relatedPaths.length;
                  return (
                    <div
                      key={effect.id}
                      className={`rounded-[24px] border px-4 py-4 transition ${
                        allSelected
                          ? 'border-[#5B7BFE]/30 bg-white shadow-[0_12px_28px_rgba(91,123,254,0.10)]'
                          : partiallySelected
                            ? 'border-emerald-200 bg-emerald-50/40'
                            : 'border-gray-100 bg-white'
                      }`}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            {visibilityIcon(effect.visibility)}
                            <p className="text-[15px] font-bold text-gray-900">{effect.title}</p>
                            <span className="rounded-full bg-gray-50 px-2.5 py-1 text-[11px] font-semibold text-gray-500 ring-1 ring-gray-200">
                              {effect.scopeLabel}
                            </span>
                            <span className="rounded-full bg-gray-50 px-2.5 py-1 text-[11px] font-semibold text-gray-500 ring-1 ring-gray-200">
                              {visibilityText(effect.visibility)}
                            </span>
                          </div>
                          <p className="mt-2 text-[13px] leading-6 text-gray-600">{effect.summary}</p>
                        </div>
                        <ActionButton
                          className="whitespace-nowrap"
                          onClick={() => onToggleEffectPaths(effect.relatedPaths)}
                          disabled={busy}
                        >
                          {allSelected ? '取消这组变化' : partiallySelected ? '补齐这组变化' : '纳入这组变化'}
                        </ActionButton>
                      </div>

                      {(effect.beforeImageDataUrl || effect.afterImageDataUrl) && (
                        <div className="mt-4 grid gap-3 md:grid-cols-2">
                          <div className="rounded-2xl border border-gray-100 bg-gray-50 p-3">
                            <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-gray-400">
                              {effect.beforeLabel || '变更前'}
                            </p>
                            {effect.beforeImageDataUrl ? (
                              <img
                                src={effect.beforeImageDataUrl}
                                alt={effect.beforeLabel || '变更前'}
                                className="mt-3 h-24 w-24 rounded-2xl border border-gray-200 bg-white object-cover"
                              />
                            ) : (
                              <p className="mt-3 text-[12px] text-gray-400">当前还没有这张图或尚未设置。</p>
                            )}
                          </div>
                          <div className="rounded-2xl border border-gray-100 bg-gray-50 p-3">
                            <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-gray-400">
                              {effect.afterLabel || '变更后'}
                            </p>
                            {effect.afterImageDataUrl ? (
                              <img
                                src={effect.afterImageDataUrl}
                                alt={effect.afterLabel || '变更后'}
                                className="mt-3 h-24 w-24 rounded-2xl border border-gray-200 bg-white object-cover"
                              />
                            ) : (
                              <p className="mt-3 text-[12px] text-gray-400">这次不会带来新的图片效果。</p>
                            )}
                          </div>
                        </div>
                      )}

                      {effect.details.length > 0 && (
                        <div className="mt-4 space-y-2">
                          {effect.details.map((detail) => (
                            <div key={detail} className="flex items-start gap-2 text-[12px] leading-6 text-gray-600">
                              <span className="mt-[9px] h-1.5 w-1.5 rounded-full bg-[#5B7BFE]" />
                              <span>{detail}</span>
                            </div>
                          ))}
                        </div>
                      )}

                      <p className="mt-4 text-[12px] text-gray-400">
                        这组变化对应 {effect.relatedPaths.length} 个底层文件，目前已纳入 {selectedCount} 个。
                      </p>
                    </div>
                  );
                })}
                {preview.effects.length === 0 && (
                  <div className="rounded-2xl border border-dashed border-gray-200 bg-white px-4 py-4 text-[13px] leading-6 text-gray-500">
                    这次改动还没有被翻译成直观的软件效果，暂时只能通过下方文件清单确认。
                  </div>
                )}
              </div>
            </div>

            {'commitSummaries' in preview && preview.commitSummaries.length > 0 && (
              <div className="rounded-3xl border border-gray-100 bg-white px-4 py-4">
                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">main 最新动态</p>
                <div className="mt-3 space-y-2">
                  {preview.commitSummaries.map((summary) => (
                    <div key={summary} className="rounded-2xl border border-gray-100 bg-gray-50 px-3 py-2 text-[12px] text-gray-700">
                      {summary}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <details className="rounded-3xl border border-gray-100 bg-white open:shadow-sm">
              <summary className="cursor-pointer list-none px-4 py-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">涉及文件</p>
                    <p className="mt-1 text-[12px] text-gray-500">如果你想核对底层证据，再展开文件清单。</p>
                  </div>
                  <span className="rounded-full bg-[#5B7BFE]/10 px-3 py-1 text-[12px] font-bold text-[#5B7BFE]">
                    已选 {selectedPaths.length}
                  </span>
                </div>
              </summary>
              <div className="border-t border-gray-100 px-4 py-3">
                <div className="space-y-3">
                  {preview.files.map((file) => {
                    const isSelected = selectedSet.has(file.path);
                    const linkedEffects = preview.effects
                      .filter((effect) => effect.relatedPaths.includes(file.path))
                      .map((effect) => effect.title);
                    return (
                      <label
                        key={file.path}
                        className={`block rounded-2xl border px-4 py-3 transition ${
                          isSelected ? 'border-[#5B7BFE]/30 bg-[#5B7BFE]/[0.05]' : 'border-gray-100 bg-gray-50/80'
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            disabled={busy}
                            onChange={() => onTogglePath(file.path)}
                            className="mt-1 h-4 w-4 rounded border-gray-300 text-[#5B7BFE] focus:ring-[#5B7BFE]"
                          />
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="truncate text-[13px] font-bold text-gray-900">{file.path}</p>
                              <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-gray-500 ring-1 ring-gray-200">
                                {file.groupLabel}
                              </span>
                              <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-gray-500 ring-1 ring-gray-200">
                                {file.summary}
                              </span>
                            </div>
                            {linkedEffects.length > 0 && (
                              <p className="mt-2 text-[12px] text-gray-500">主要体现在：{linkedEffects.join('、')}</p>
                            )}
                            {file.previousPath && (
                              <p className="mt-2 text-[12px] text-gray-500">原路径：{file.previousPath}</p>
                            )}
                            {file.risk && (
                              <div className="mt-3 rounded-2xl border border-rose-100 bg-rose-50 px-3 py-3">
                                <div className="flex items-start gap-2 text-[12px] font-semibold text-rose-700">
                                  <AlertCircle size={15} className="mt-0.5 shrink-0" />
                                  <span>{file.risk.message}</span>
                                </div>
                                {isSelected && (
                                  <p className="mt-3 text-[12px] font-semibold text-rose-800">
                                    当前如果继续执行，这个文件会按当前按钮方向整体取版本。
                                  </p>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>
            </details>
          </div>

          <div className="space-y-4">
            <div className="rounded-3xl border border-gray-100 bg-gray-50 px-4 py-4">
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">本次主要修改</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {preview.groups.map((group) => (
                  <span
                    key={group.key}
                    className="rounded-full border border-gray-200 bg-white px-3 py-1.5 text-[12px] font-bold text-gray-700"
                  >
                    {group.label} · {group.fileCount}
                  </span>
                ))}
                {preview.groups.length === 0 && (
                  <span className="text-[12px] text-gray-400">当前没有可操作的文件。</span>
                )}
              </div>
            </div>

            <div className="rounded-3xl border border-gray-100 bg-gray-50 px-4 py-4">
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">提交说明</p>
              <textarea
                value={message}
                onChange={(event) => onMessageChange(event.target.value)}
                disabled={busy}
                rows={4}
                className="mt-3 w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-semibold text-gray-700 outline-none transition focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/20"
                placeholder={preview.suggestedMessage}
              />
              <p className="mt-2 text-[12px] text-gray-400">默认会先填好建议说明，你也可以手动修改。</p>
            </div>

            <div className="rounded-3xl border border-gray-100 bg-white px-4 py-4">
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">执行前提醒</p>
              <div className="mt-3 space-y-3 text-[12px] leading-6 text-gray-600">
                <div className="flex items-start gap-2">
                  <CheckCircle2 size={15} className="mt-1 shrink-0 text-emerald-500" />
                  <span>现在先看“软件会怎么变”，文件清单被降成了第二层辅助信息。</span>
                </div>
                <div className="flex items-start gap-2">
                  <CheckCircle2 size={15} className="mt-1 shrink-0 text-emerald-500" />
                  <span>{mode === 'push' ? '确认后会直接提交并推送到 main。' : '确认后会把你勾选的 main 变化同步到本地 main。'}</span>
                </div>
                <div className="flex items-start gap-2">
                  <AlertCircle size={15} className="mt-1 shrink-0 text-amber-500" />
                  <span>高风险覆盖文件默认不会主动勾选；只有你主动勾选它，才会按当前按钮方向整体取版本。</span>
                </div>
                {mode === 'pull' && (
                  <div className="flex items-start gap-2">
                    <AlertCircle size={15} className="mt-1 shrink-0 text-amber-500" />
                    <span>同步完成后，你还可以决定是否顺手自动更新当前安装版。</span>
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-3xl border border-gray-100 bg-white px-4 py-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">确认执行</p>
                  <p className="mt-1 text-[12px] text-gray-500">
                    {selectedPaths.length === 0
                      ? mode === 'push'
                        ? '当前没有勾选要推送的文件；继续后会保留这些未勾选改动，只处理 main 同步状态。'
                        : '当前没有勾选要同步的文件；继续后会保留这些未勾选变化不动。'
                      : `当前已纳入 ${selectedPaths.length} 个文件。`}
                  </p>
                </div>
                {mode === 'push' ? <UploadCloud size={18} className="text-[#5B7BFE]" /> : <Download size={18} className="text-[#5B7BFE]" />}
              </div>
              <div className="mt-4 flex flex-wrap justify-end gap-3">
                <ActionButton onClick={busy ? undefined : onClose}>取消</ActionButton>
                <ActionButton primary disabled={confirmDisabled} onClick={onConfirm}>
                  {busy ? <RefreshCw size={14} className="animate-spin" /> : mode === 'push' ? <UploadCloud size={14} /> : <Download size={14} />}
                  {confirmLabel}
                </ActionButton>
              </div>
            </div>
          </div>
        </div>
        </div>
      </div>
      </div>
    </div>
  );
}
~~~

## `src/renderer/components/collab/CollabSyncCard.tsx`

- 编码: `utf-8`

~~~tsx
import React from 'react';
import { Download, FolderOpen, RefreshCw, UploadCloud } from 'lucide-react';
import type { CollabRepoStatus } from '../../../shared/types';

type CollabSyncCardProps = {
  collapsed: boolean;
  status: CollabRepoStatus | null;
  loading: boolean;
  busyAction: 'push' | 'pull' | 'rebuild' | null;
  onRevealRepo: () => void;
  onPreviewPush: () => void;
  onPreviewPull: () => void;
};

function actionLabel(status: CollabRepoStatus | null) {
  if (!status?.isConfigured) return '点击任一主按钮后，会先帮你绑定源码目录。';
  if (!status.isValid) return '当前目录无效，点击主按钮时会提示你重新选择。';
  return status.statusText;
}

export function CollabSyncCard({
  collapsed,
  status,
  loading,
  busyAction,
  onRevealRepo,
  onPreviewPush,
  onPreviewPull,
}: CollabSyncCardProps) {
  const actionDisabled = loading || busyAction !== null;

  if (collapsed) {
    return (
      <div className="px-3 pb-4 hidden md:block">
        <div className="rounded-2xl border border-gray-200 bg-gray-50 p-2 flex flex-col items-center gap-2">
          <button
            type="button"
            className="w-10 h-10 rounded-2xl border border-gray-200 bg-white text-gray-600 hover:text-gray-900 hover:bg-gray-50 disabled:opacity-50"
            onClick={onPreviewPush}
            disabled={actionDisabled}
            title="提交并推送我的修改"
          >
            {busyAction === 'push' ? <RefreshCw size={16} className="mx-auto animate-spin" /> : <UploadCloud size={16} className="mx-auto" />}
          </button>
          <button
            type="button"
            className="w-10 h-10 rounded-2xl border border-gray-200 bg-white text-gray-600 hover:text-gray-900 hover:bg-gray-50 disabled:opacity-50"
            onClick={onPreviewPull}
            disabled={actionDisabled}
            title="预览并同步最新版本"
          >
            {busyAction === 'pull' ? <RefreshCw size={16} className="mx-auto animate-spin" /> : <Download size={16} className="mx-auto" />}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="px-4 pb-4 hidden md:block">
      <div className="bg-white rounded-2xl border border-gray-100 p-4 shadow-sm space-y-3">
        <div>
          <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">协作同步</p>
          <p className="mt-1 text-[13px] font-bold text-gray-800">
            {status?.repoName || '尚未绑定源码目录'}
          </p>
          <p className="mt-1 text-[11px] text-gray-500 leading-5">{actionLabel(status)}</p>
        </div>

        {status?.isConfigured && status?.isValid && (
          <div className="rounded-2xl border border-gray-100 bg-gray-50 px-3 py-3 text-[11px] text-gray-600">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-white px-2.5 py-1 font-bold text-gray-700 border border-gray-200">
                {status.branch || '未知分支'}
              </span>
              <span>本地 {status.localChangeCount} 项改动</span>
              <span>远端领先 {status.behindCount}</span>
            </div>
            {status.repoPath && (
              <button
                type="button"
                className="mt-2 inline-flex items-center gap-1 text-[#5B7BFE] font-bold hover:text-[#4a6be6]"
                onClick={onRevealRepo}
              >
                <FolderOpen size={12} />
                在 Finder 中显示源码目录
              </button>
            )}
          </div>
        )}

        {!status?.isConfigured && status?.suggestedRepoPath && (
          <div className="rounded-2xl border border-blue-100 bg-blue-50/70 px-3 py-3 text-[11px] text-[#4256C5] leading-5">
            <p className="font-bold">已检测到推荐源码目录</p>
            <p className="mt-1 break-all">{status.suggestedRepoPath}</p>
            <p className="mt-2 text-[11px] text-[#5B7BFE]">直接点下面任一主按钮，就会围绕这个仓库继续。</p>
          </div>
        )}

        <div className="grid grid-cols-1 gap-2">
          <button
            type="button"
            className="inline-flex items-center justify-center gap-2 rounded-2xl bg-[#5B7BFE] px-4 py-3 text-[12px] font-bold text-white shadow-sm hover:bg-[#4a6be6] disabled:opacity-60 disabled:cursor-not-allowed"
            onClick={onPreviewPush}
            disabled={actionDisabled}
          >
            {busyAction === 'push' ? <RefreshCw size={14} className="animate-spin" /> : <UploadCloud size={14} />}
            提交并推送我的修改
          </button>
          <button
            type="button"
            className="inline-flex items-center justify-center gap-2 rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[12px] font-bold text-gray-700 shadow-sm hover:bg-gray-50 disabled:opacity-60 disabled:cursor-not-allowed"
            onClick={onPreviewPull}
            disabled={actionDisabled}
          >
            {busyAction === 'pull' ? <RefreshCw size={14} className="animate-spin" /> : <Download size={14} />}
            预览并同步最新版本
          </button>
        </div>
      </div>
    </div>
  );
}
~~~

## `src/renderer/components/growth/GrowthContext.tsx`

- 编码: `utf-8`

~~~tsx
import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

import { getGrowthOverview } from '../../lib/api';
import type { GrowthOverview } from '../../../shared/types';

const GROWTH_REFRESH_EVENT = 'yiyu:growth-refresh';

type GrowthContextValue = {
  growthOverview: GrowthOverview | null;
  isGrowthLoading: boolean;
  refreshGrowthOverview: () => Promise<GrowthOverview | null>;
};

const GrowthContext = createContext<GrowthContextValue | null>(null);

export function notifyGrowthRefresh() {
  window.dispatchEvent(new CustomEvent(GROWTH_REFRESH_EVENT));
}

export function GrowthProvider({ children }: { children: React.ReactNode }) {
  const [growthOverview, setGrowthOverview] = useState<GrowthOverview | null>(null);
  const [isGrowthLoading, setIsGrowthLoading] = useState(false);
  const mountedRef = useRef(true);

  const refreshGrowthOverview = useCallback(async () => {
    setIsGrowthLoading(true);
    try {
      const nextOverview = await getGrowthOverview();
      if (mountedRef.current) {
        setGrowthOverview(nextOverview);
      }
      return nextOverview;
    } catch (error) {
      console.error('Failed to refresh growth overview', error);
      return null;
    } finally {
      if (mountedRef.current) {
        setIsGrowthLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void refreshGrowthOverview();
    const handleRefresh = () => {
      void refreshGrowthOverview();
    };
    window.addEventListener(GROWTH_REFRESH_EVENT, handleRefresh);
    return () => {
      mountedRef.current = false;
      window.removeEventListener(GROWTH_REFRESH_EVENT, handleRefresh);
    };
  }, [refreshGrowthOverview]);

  const value = useMemo<GrowthContextValue>(
    () => ({
      growthOverview,
      isGrowthLoading,
      refreshGrowthOverview,
    }),
    [growthOverview, isGrowthLoading, refreshGrowthOverview],
  );

  return <GrowthContext.Provider value={value}>{children}</GrowthContext.Provider>;
}

export function useGrowthOverviewState() {
  return useContext(GrowthContext);
}
~~~

## `src/renderer/components/handbook/GrowthAssetLibraryDrawer.tsx`

- 编码: `utf-8`

~~~tsx
import React, { useEffect, useMemo, useState } from 'react';
import { ArrowRight, BookOpen, CopyPlus, FileClock, Search, Sparkles, X } from 'lucide-react';

import { getHandbookEntry, markHandbookEntryReused } from '../../lib/api';
import type { GrowthContextLink, HandbookEntry, HandbookEntryDetail, XpLedgerEntry } from '../../../shared/types';

type FlashLevel = 'success' | 'error';

type GrowthAssetLibraryDrawerProps = {
  open: boolean;
  entries: HandbookEntry[];
  recentEntries: XpLedgerEntry[];
  flash: (level: FlashLevel, message: string) => void;
  onClose: () => void;
  onRefresh: () => Promise<void>;
  onOpenComposer: () => void;
  onNavigate?: (tab: string) => void;
  onOpenContext?: (context: GrowthContextLink) => void;
};

function cx(...classNames: Array<string | false | null | undefined>) {
  return classNames.filter(Boolean).join(' ');
}

function formatDateLabel(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(date);
}

function sourceLabel(sourceType: string) {
  if (sourceType === 'manual') return '手动沉淀';
  if (sourceType === 'meeting') return '会议结论';
  if (sourceType === 'topic_candidate') return '情报候选';
  if (sourceType === 'task') return '任务复盘';
  if (sourceType === 'analysis') return '分析学习';
  return sourceType || '未分类';
}

function typeLabel(sourceType: string) {
  if (sourceType === 'meeting') return '结论';
  if (sourceType === 'topic_candidate') return '判断';
  if (sourceType === 'analysis') return '方法';
  if (sourceType === 'task') return '复盘';
  return '经验';
}

function isMethodLike(entry: HandbookEntry) {
  const normalized = `${entry.title} ${entry.summary} ${entry.tags.join(' ')}`.toLowerCase();
  return ['模板', '方法', '清单', '复用', '机制'].some((keyword) => normalized.includes(keyword));
}

export function GrowthAssetLibraryDrawer({
  open,
  entries,
  recentEntries,
  flash,
  onClose,
  onRefresh,
  onOpenComposer,
  onNavigate,
  onOpenContext,
}: GrowthAssetLibraryDrawerProps) {
  const [query, setQuery] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [markingId, setMarkingId] = useState<string | null>(null);
  const [entryDetail, setEntryDetail] = useState<HandbookEntryDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const sortedEntries = useMemo(
    () => [...entries].sort((left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime()),
    [entries],
  );
  const filteredEntries = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return sortedEntries;
    return sortedEntries.filter((entry) => [entry.title, entry.summary, entry.tags.join(' '), sourceLabel(entry.sourceType)].join(' ').toLowerCase().includes(normalized));
  }, [query, sortedEntries]);

  useEffect(() => {
    if (!open) return;
    if (!filteredEntries.length) {
      setSelectedId(null);
      return;
    }
    if (!selectedId || !filteredEntries.some((entry) => entry.id === selectedId)) {
      setSelectedId(filteredEntries[0].id);
    }
  }, [filteredEntries, open, selectedId]);

  const selectedEntry = filteredEntries.find((entry) => entry.id === selectedId) || null;
  const selectedEntryDetail = entryDetail && selectedEntry && entryDetail.id === selectedEntry.id ? entryDetail : null;
  const selectedRelatedEntries = selectedEntryDetail?.relatedLedgerEntries || recentEntries.filter((entry) => entry.handbookEntryId === selectedEntry?.id).slice(0, 4);

  useEffect(() => {
    if (!open || !selectedId) {
      setEntryDetail(null);
      return;
    }
    let cancelled = false;
    const load = async () => {
      setDetailLoading(true);
      try {
        const detail = await getHandbookEntry(selectedId);
        if (!cancelled) {
          setEntryDetail(detail);
        }
      } catch (error) {
        if (!cancelled) {
          setEntryDetail(null);
          flash('error', error instanceof Error ? error.message : '成长资产详情加载失败');
        }
      } finally {
        if (!cancelled) {
          setDetailLoading(false);
        }
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [flash, open, selectedId]);

  const handleMarkReused = async () => {
    const targetEntry = selectedEntryDetail || selectedEntry;
    if (!targetEntry) return;
    setMarkingId(targetEntry.id);
    try {
      const reuseContext = preferredUsageContext;
      const result = await markHandbookEntryReused(targetEntry.id, {
        note: `从经验资产库标记复用：${targetEntry.title}`,
        sourceType: reuseContext?.objectType || targetEntry.sourceObjectType || 'handbook_manual_reuse',
        sourceId: reuseContext?.objectId || targetEntry.sourceObjectId || targetEntry.eventLineId || targetEntry.clientId || targetEntry.id,
        sourceLabel: reuseContext?.label || targetEntry.sourceTitle || targetEntry.title,
        contextSummary: reuseContext?.subtitle || targetEntry.contextSummary || targetEntry.summary,
        linkedContexts: reuseContext ? [reuseContext] : targetEntry.linkedContexts,
      });
      await onRefresh();
      flash('success', result.duplicate ? '本周已经记录过这条复用，未重复加分' : `已记录方法复用，新增 ${result.gainedXp} XP`);
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '记录复用失败');
    } finally {
      setMarkingId(null);
    }
  };

  const preferredUsageContext = useMemo(() => {
    const contexts = selectedEntryDetail?.linkedContexts || selectedEntry?.linkedContexts || [];
    return (
      contexts.find((context) => context.objectType === 'task')
      || contexts.find((context) => context.objectType === 'event_line')
      || contexts.find((context) => context.objectType === 'client')
      || contexts[0]
      || null
    );
  }, [selectedEntry, selectedEntryDetail]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-slate-900/30 backdrop-blur-sm">
      <div className="flex h-full w-full max-w-[1120px] flex-col bg-white shadow-2xl animate-in slide-in-from-right duration-300">
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">经验资产</div>
            <h2 className="mt-1 text-[22px] font-semibold tracking-tight text-slate-900">成长手册资产库</h2>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onOpenComposer}
              className="inline-flex items-center gap-2 rounded-full bg-[#335CFF] px-4 py-2 text-[13px] font-medium text-white shadow-sm transition-colors hover:bg-[#2C50E0]"
            >
              <Sparkles className="h-4 w-4" />
              新增沉淀
            </button>
            <button type="button" onClick={onClose} className="rounded-full p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700">
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[360px_minmax(0,1fr)]">
          <div className="border-r border-slate-100 bg-slate-50/55 p-5">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索标题、摘要或标签"
                className="w-full rounded-2xl border border-slate-200 bg-white py-3 pl-10 pr-4 text-[13px] font-medium text-slate-700 placeholder:text-slate-400 focus:border-[#C9D7FF] focus:outline-none"
              />
            </div>

            <div className="mt-4 space-y-2 overflow-y-auto pb-4">
              {filteredEntries.length ? (
                filteredEntries.map((entry) => (
                  <button
                    key={entry.id}
                    type="button"
                    onClick={() => setSelectedId(entry.id)}
                    className={cx(
                      'w-full rounded-[22px] border p-4 text-left transition',
                      selectedId === entry.id ? 'border-[#C9D7FF] bg-white shadow-sm' : 'border-transparent bg-transparent hover:border-slate-200 hover:bg-white/90',
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-[14px] font-semibold text-slate-900">{entry.title}</div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-500">{typeLabel(entry.sourceType)}</span>
                          <span className="rounded-full bg-[#EDF2FF] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[#335CFE]">{sourceLabel(entry.sourceType)}</span>
                        </div>
                      </div>
                      <div className="text-[11px] font-medium text-slate-400">{formatDateLabel(entry.createdAt)}</div>
                    </div>
                    <p className="mt-3 line-clamp-2 text-[12px] leading-6 text-slate-500">{entry.summary}</p>
                  </button>
                ))
              ) : (
                <div className="rounded-[22px] border border-dashed border-slate-200 bg-white px-4 py-8 text-center text-[13px] font-medium text-slate-400">
                  当前筛选条件下没有经验资产
                </div>
              )}
            </div>
          </div>

          <div className="min-h-0 overflow-y-auto p-6">
            {selectedEntry ? (
              <div className="space-y-8">
                <div className="flex flex-col gap-4 border-b border-slate-100 pb-6 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] text-slate-500">
                        {typeLabel(selectedEntry.sourceType)}
                      </span>
                      <span className="rounded-full bg-[#EBF0FF] px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] text-[#335CFE]">
                        {sourceLabel(selectedEntry.sourceType)}
                      </span>
                      {isMethodLike(selectedEntry) ? (
                        <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] text-emerald-700">可复用方法</span>
                      ) : null}
                    </div>
                    <h3 className="mt-3 text-[28px] font-semibold tracking-tight text-slate-900">{selectedEntry.title}</h3>
                    <p className="mt-3 max-w-3xl text-[14px] leading-7 text-slate-600">{selectedEntry.summary}</p>
                  </div>
                  <div className="flex shrink-0 flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        onClose();
                        if (preferredUsageContext && onOpenContext) {
                          onOpenContext(preferredUsageContext);
                          return;
                        }
                        onNavigate?.('tasks');
                      }}
                      className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-4 py-2 text-[13px] font-medium text-slate-700 transition hover:bg-slate-50"
                    >
                      去任务页使用
                      <ArrowRight className="h-3.5 w-3.5" />
                    </button>
                    {isMethodLike(selectedEntryDetail || selectedEntry) ? (
                      <button
                        type="button"
                        onClick={() => void handleMarkReused()}
                        disabled={markingId === selectedEntry.id}
                        className="inline-flex items-center gap-2 rounded-full bg-[#335CFF] px-4 py-2 text-[13px] font-medium text-white shadow-sm transition hover:bg-[#2C50E0] disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        <CopyPlus className="h-4 w-4" />
                        {markingId === selectedEntry.id ? '记录中...' : '标记本次已复用'}
                      </button>
                    ) : null}
                  </div>
                </div>

                <section className="grid gap-4 lg:grid-cols-3">
                  <div className="rounded-[24px] border border-slate-100 bg-slate-50/70 p-4">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">沉淀来源</div>
                    <div className="mt-3 text-[13px] font-semibold text-slate-800">{sourceLabel(selectedEntry.sourceType)}</div>
                    <div className="mt-2 text-[12px] leading-6 text-slate-500">
                      {selectedEntryDetail?.sourceTitle || selectedEntryDetail?.contextSummary || '系统会根据来源类型，把这条经验归入会议、复盘、情报或分析资产。'}
                    </div>
                  </div>
                  <div className="rounded-[24px] border border-slate-100 bg-slate-50/70 p-4">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">标签与能力</div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {selectedEntry.tags.length ? (
                        selectedEntry.tags.map((tag) => (
                          <span key={tag} className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600">
                            {tag}
                          </span>
                        ))
                      ) : (
                        <span className="text-[12px] text-slate-400">暂无标签</span>
                      )}
                      {selectedEntryDetail?.abilityKeys?.map((abilityKey) => (
                        <span key={abilityKey} className="rounded-full border border-[#D9E3FF] bg-[#F6F8FF] px-2.5 py-1 text-[11px] font-medium text-[#335CFE]">
                          {abilityKey}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-[24px] border border-slate-100 bg-slate-50/70 p-4">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">复用状态</div>
                    <div className="mt-3 text-[13px] font-semibold text-slate-800">{selectedEntryDetail?.reuseCount ?? 0} 次复用</div>
                    <div className="mt-2 text-[12px] leading-6 text-slate-500">
                      {selectedEntryDetail?.lastReusedAt ? `最近复用：${formatDateLabel(selectedEntryDetail.lastReusedAt)}` : '还没有真实复用记录，后续在任务里使用后会累积证据。'}
                    </div>
                  </div>
                </section>

                <section>
                  <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                    <BookOpen className="h-3.5 w-3.5" />
                    首次来源与适用场景
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {(selectedEntryDetail?.originContexts || selectedEntryDetail?.linkedContexts || selectedEntry.linkedContexts || []).length ? (
                      (selectedEntryDetail?.originContexts || selectedEntryDetail?.linkedContexts || selectedEntry.linkedContexts || []).map((context) => (
                        <button
                          key={`${context.objectType}:${context.objectId}`}
                          type="button"
                          onClick={() => {
                            onClose();
                            if (onOpenContext) {
                              onOpenContext(context);
                              return;
                            }
                            onNavigate?.(context.tab === 'growth' ? 'growth_handbook' : context.tab);
                          }}
                          className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[12px] font-medium text-slate-600 transition hover:border-[#C9D7FF] hover:text-[#335CFE]"
                        >
                          {context.label}
                          {context.subtitle ? <span className="ml-1 text-slate-400">· {context.subtitle}</span> : null}
                        </button>
                      ))
                    ) : (
                      <div className="rounded-[20px] border border-dashed border-slate-200 bg-slate-50 px-4 py-4 text-[12px] font-medium text-slate-400">
                        当前还没有可展示的来源对象回链
                      </div>
                    )}
                  </div>
                </section>

                <section>
                  <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                    <CopyPlus className="h-3.5 w-3.5" />
                    最近复用场景
                  </div>
                  <div className="mt-3 space-y-3">
                    {selectedEntryDetail?.reuseHistory?.length ? (
                      selectedEntryDetail.reuseHistory.map((item) => (
                        <div key={item.id} className="rounded-[20px] border border-slate-100 bg-slate-50/70 p-4">
                          <div className="flex items-start justify-between gap-4">
                            <div>
                              <div className="text-[13px] font-semibold text-slate-900">{item.sourceLabel}</div>
                              <div className="mt-1 text-[12px] leading-6 text-slate-500">
                                {item.contextSummary || item.note || '这条方法已经在真实工作里被继续使用。'}
                              </div>
                            </div>
                            <div className="text-right">
                              <div className="text-[14px] font-semibold text-[#335CFE]">+{item.gainedXp} XP</div>
                              <div className="text-[11px] text-slate-400">{formatDateLabel(item.createdAt)}</div>
                            </div>
                          </div>
                          {item.linkedContexts.length ? (
                            <div className="mt-3 flex flex-wrap gap-2">
                              {item.linkedContexts.map((context) => (
                                <button
                                  key={`${item.id}-${context.objectType}-${context.objectId}`}
                                  type="button"
                                  onClick={() => {
                                    onClose();
                                    onOpenContext?.(context);
                                  }}
                                  className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600 transition hover:border-[#C9D7FF] hover:text-[#335CFE]"
                                >
                                  {context.label}
                                </button>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      ))
                    ) : (
                      <div className="rounded-[20px] border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-[12px] font-medium text-slate-400">
                        还没有真实复用场景。后续从任务、会议或事件线里再次使用时，这里会自动累计证据。
                      </div>
                    )}
                  </div>
                </section>

                <section>
                  <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                    <BookOpen className="h-3.5 w-3.5" />
                    适用边界
                  </div>
                  <div className="mt-3 rounded-[24px] border border-slate-100 bg-white p-5 shadow-sm">
                    <p className="text-[13px] leading-7 text-slate-600">
                      {selectedEntryDetail?.contextSummary || `适用于「${selectedEntry.tags.slice(0, 2).join(' / ') || '当前工作场景'}」这类需要明确边界、沉淀方法或减少返工的场景。`}
                      {' '}如果只是一次性结果记录，而没有复用价值，就不应该把它当成方法资产。
                    </p>
                    {selectedEntryDetail?.evidenceRefs?.length ? (
                      <div className="mt-4 flex flex-wrap gap-2">
                        {selectedEntryDetail.evidenceRefs.map((ref) => (
                          <span key={ref} className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-medium text-slate-500">
                            {ref}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </section>

                <section>
                  <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                    <FileClock className="h-3.5 w-3.5" />
                    对应成长账本
                  </div>
                  <div className="mt-3 space-y-3">
                    {detailLoading ? (
                      <div className="rounded-[20px] border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-[12px] font-medium text-slate-400">
                        正在加载对应 XP 账本...
                      </div>
                    ) : null}
                    {selectedRelatedEntries.length ? (
                      selectedRelatedEntries.map((entry) => (
                        <div key={entry.id} className="rounded-[20px] border border-slate-100 bg-slate-50/70 p-4">
                          <div className="flex items-center justify-between gap-4">
                            <div>
                              <div className="text-[13px] font-semibold text-slate-900">{entry.sourceTitle || entry.reason}</div>
                              <div className="mt-1 text-[12px] leading-5 text-slate-500">
                                {entry.abilityLabel} · 基础 +{entry.baseXp} / 溢价 +{entry.premiumXp}
                              </div>
                              {entry.contextSummary ? <div className="mt-1 text-[11px] leading-5 text-slate-400">{entry.contextSummary}</div> : null}
                            </div>
                            <div className="text-right">
                              <div className="text-[14px] font-semibold text-[#335CFE]">+{entry.totalXp} XP</div>
                              <div className="text-[11px] text-slate-400">{formatDateLabel(entry.createdAt)}</div>
                            </div>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="rounded-[20px] border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-[12px] font-medium text-slate-400">
                        这条资产的回流账本还不多。你可以在真实任务里复用它，系统就会继续给它累计证据。
                      </div>
                    )}
                  </div>
                </section>
              </div>
            ) : (
              <div className="flex h-full items-center justify-center rounded-[24px] border border-dashed border-slate-200 bg-slate-50 text-[13px] font-medium text-slate-400">
                选择一条经验资产后，可以查看详情、来源和复用动作。
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default GrowthAssetLibraryDrawer;
~~~

## `src/renderer/components/handbook/GrowthBadgeWall.tsx`

- 编码: `utf-8`

~~~tsx
import React, { useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  BookOpen,
  Briefcase,
  CalendarClock,
  CircleDashed,
  FileStack,
  Flag,
  Gauge,
  HandHelping,
  Handshake,
  Layers3,
  Lightbulb,
  Radar,
  Search,
  ShieldCheck,
  Sparkles,
  Target,
  Users,
  Wrench,
  X,
  type LucideIcon,
} from 'lucide-react';

import { getGrowthBadges } from '../../lib/api';
import { useGrowthOverviewState } from '../growth/GrowthContext';
import type { BadgeBoard, BadgeProgress, BadgeState, GrowthContextLink } from '../../../shared/types';

type FlashLevel = 'success' | 'error';

type GrowthBadgeWallProps = {
  flash: (level: FlashLevel, message: string) => void;
  onNavigate?: (tab: string) => void;
  onOpenContext?: (context: GrowthContextLink) => void;
};

type BadgeFilter = 'all' | 'lit' | 'progress' | 'locked';
type BadgeConnectivityFilter = 'all' | 'connected' | 'unsupported';

const STATE_LABELS: Record<BadgeState, string> = {
  locked: '未点亮',
  progress: '进行中',
  ready: '即将点亮',
  lit: '已点亮',
  mastered: '已精进',
};

const MOTIF_ICON_MAP: Record<string, LucideIcon> = {
  meeting_ring: Users,
  report_arrow: ArrowRight,
  chat_bolt: Sparkles,
  linked_rings: Users,
  handoff: HandHelping,
  radar_ping: Radar,
  search_chat: Search,
  stack_docs: Layers3,
  path_nodes: Target,
  handshake_seal: Handshake,
  blueprint_flag: Flag,
  grid_blocks: Layers3,
  summit_flag: Flag,
  shield_ping: ShieldCheck,
  seal_box: Briefcase,
  calendar_lines: CalendarClock,
  dashboard_gauge: Gauge,
  manual_stack: BookOpen,
  stamp_flow: CircleDashed,
  loop_note: ArrowRight,
  invoice_shield: ShieldCheck,
  wallet_gate: Briefcase,
  scroll_seal: FileStack,
  bill_return: ArrowRight,
  cart_checklist: Briefcase,
  mentor_orbit: Users,
  idea_burst: Lightbulb,
  cards_spark: Sparkles,
  path_flag: Flag,
  wrench_up: Wrench,
};

function cx(...classNames: Array<string | false | null | undefined>) {
  return classNames.filter(Boolean).join(' ');
}

function formatDateLabel(value?: string | null) {
  if (!value) return '未记录';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric' }).format(date);
}

function badgePalette(state: BadgeState) {
  if (state === 'lit' || state === 'mastered') {
    return {
      ring: '#335CFE',
      glow: '0 16px 40px rgba(51, 92, 254, 0.18)',
      center: 'linear-gradient(180deg, rgba(83,121,255,0.98) 0%, rgba(44,78,233,0.98) 100%)',
      outer: 'linear-gradient(180deg, rgba(246,249,255,0.98) 0%, rgba(225,233,255,0.98) 100%)',
      icon: 'text-white',
      border: 'rgba(113, 144, 255, 0.26)',
      chip: 'bg-[#335CFE]/10 text-[#335CFE]',
    };
  }
  if (state === 'ready') {
    return {
      ring: '#5B7BFE',
      glow: '0 12px 30px rgba(91, 123, 254, 0.16)',
      center: 'linear-gradient(180deg, rgba(239,244,255,1) 0%, rgba(221,231,255,1) 100%)',
      outer: 'linear-gradient(180deg, rgba(255,255,255,1) 0%, rgba(240,244,255,1) 100%)',
      icon: 'text-[#335CFE]',
      border: 'rgba(113, 144, 255, 0.22)',
      chip: 'bg-[#5B7BFE]/10 text-[#335CFE]',
    };
  }
  if (state === 'progress') {
    return {
      ring: '#8FA4FF',
      glow: '0 8px 20px rgba(143, 164, 255, 0.08)',
      center: 'linear-gradient(180deg, rgba(255,255,255,1) 0%, rgba(243,246,253,1) 100%)',
      outer: 'linear-gradient(180deg, rgba(255,255,255,1) 0%, rgba(246,248,252,1) 100%)',
      icon: 'text-[#5B7BFE]',
      border: 'rgba(203, 213, 225, 0.8)',
      chip: 'bg-slate-100 text-slate-600',
    };
  }
  return {
    ring: '#D5DCE8',
    glow: 'none',
    center: 'linear-gradient(180deg, rgba(255,255,255,1) 0%, rgba(245,247,250,1) 100%)',
    outer: 'linear-gradient(180deg, rgba(255,255,255,1) 0%, rgba(246,248,251,1) 100%)',
    icon: 'text-slate-400',
    border: 'rgba(226, 232, 240, 0.9)',
    chip: 'bg-slate-100 text-slate-500',
  };
}

function BadgeToken({ badge, size = 'md' }: { badge: BadgeProgress; size?: 'md' | 'lg' }) {
  const palette = badgePalette(badge.state);
  const Icon = MOTIF_ICON_MAP[badge.iconMotif] || Sparkles;
  const diameter = size === 'lg' ? 116 : 84;
  const radius = size === 'lg' ? 44 : 31;
  const stroke = size === 'lg' ? 5 : 4;
  const circumference = 2 * Math.PI * radius;
  const dashoffset = circumference - (circumference * badge.progressPercent) / 100;

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: diameter, height: diameter, filter: `drop-shadow(${palette.glow})` }}
    >
      <div
        className="absolute inset-0 rounded-full border backdrop-blur-[2px]"
        style={{ background: palette.outer, borderColor: palette.border }}
      />
      <svg className="absolute inset-0 -rotate-90" viewBox={`0 0 ${diameter} ${diameter}`}>
        <circle cx={diameter / 2} cy={diameter / 2} r={radius} fill="none" stroke="rgba(226,232,240,0.66)" strokeWidth={stroke} />
        <circle
          cx={diameter / 2}
          cy={diameter / 2}
          r={radius}
          fill="none"
          stroke={palette.ring}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashoffset}
        />
      </svg>
      <div
        className="relative flex items-center justify-center rounded-full border"
        style={{
          width: size === 'lg' ? 76 : 56,
          height: size === 'lg' ? 76 : 56,
          background: palette.center,
          borderColor: palette.border,
        }}
      >
        <Icon className={cx(size === 'lg' ? 'h-8 w-8' : 'h-6 w-6', palette.icon)} strokeWidth={1.9} />
      </div>
      {badge.state === 'ready' ? <div className="absolute right-2 top-1.5 h-2.5 w-2.5 rounded-full bg-[#335CFE] shadow-[0_0_0_4px_rgba(51,92,254,0.12)]" /> : null}
      {badge.state === 'mastered' ? <div className="absolute bottom-0 rounded-full bg-[#111827] px-2 py-0.5 text-[10px] font-semibold tracking-[0.18em] text-white">V2</div> : null}
    </div>
  );
}

function stateMatchesFilter(state: BadgeState, filter: BadgeFilter) {
  if (filter === 'all') return true;
  if (filter === 'lit') return state === 'lit' || state === 'mastered';
  if (filter === 'progress') return state === 'progress' || state === 'ready';
  return state === 'locked';
}

function badgeNeedsModuleConnection(badge: BadgeProgress) {
  return badge.missingSignals.some((signal) => signal.includes('当前模块未接通'));
}

export function GrowthBadgeWall({ flash, onNavigate, onOpenContext }: GrowthBadgeWallProps) {
  const growthState = useGrowthOverviewState();
  const [board, setBoard] = useState<BadgeBoard | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<BadgeFilter>('all');
  const [connectivityFilter, setConnectivityFilter] = useState<BadgeConnectivityFilter>('connected');
  const [categoryId, setCategoryId] = useState<string>('all');
  const [selectedBadgeId, setSelectedBadgeId] = useState<string | null>(null);

  const loadBadges = async () => {
    setIsLoading(true);
    try {
      const response = await getGrowthBadges();
      setBoard(response);
      if (growthState) {
        void growthState.refreshGrowthOverview();
      }
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '成长勋章加载失败');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadBadges();
  }, []);

  const allBadges = useMemo(() => board?.categories.flatMap((category) => category.badges) || [], [board]);
  const filteredCategories = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return (board?.categories || [])
      .map((category) => ({
        ...category,
        badges: category.badges.filter((badge) => {
          if (categoryId !== 'all' && category.id !== categoryId) return false;
          if (!stateMatchesFilter(badge.state, filter)) return false;
          if (connectivityFilter === 'connected' && badgeNeedsModuleConnection(badge)) return false;
          if (connectivityFilter === 'unsupported' && !badgeNeedsModuleConnection(badge)) return false;
          if (!normalizedQuery) return true;
          return [badge.name, badge.description, badge.categoryLabel, badge.whyItMatters]
            .join(' ')
            .toLowerCase()
            .includes(normalizedQuery);
        }),
      }))
      .filter((category) => category.badges.length > 0);
  }, [board, categoryId, connectivityFilter, filter, query]);

  useEffect(() => {
    if (!filteredCategories.length) {
      setSelectedBadgeId(null);
      return;
    }
    const stillExists = filteredCategories.some((category) => category.badges.some((badge) => badge.id === selectedBadgeId));
    if (!selectedBadgeId || !stillExists) {
      setSelectedBadgeId(filteredCategories[0].badges[0]?.id || null);
    }
  }, [filteredCategories, selectedBadgeId]);

  const selectedBadge = useMemo(
    () => filteredCategories.flatMap((category) => category.badges).find((badge) => badge.id === selectedBadgeId) || null,
    [filteredCategories, selectedBadgeId],
  );

  const upcomingNames = useMemo(() => {
    const ids = new Set(board?.overview.upcomingBadgeIds || []);
    return allBadges.filter((badge) => ids.has(badge.id)).map((badge) => badge.name);
  }, [allBadges, board]);
  const unsupportedBadgeCount = useMemo(() => allBadges.filter((badge) => badgeNeedsModuleConnection(badge)).length, [allBadges]);
  const connectedBadgeCount = useMemo(() => allBadges.length - unsupportedBadgeCount, [allBadges.length, unsupportedBadgeCount]);

  const handleAction = (tab: string, label: string) => {
    if (onNavigate) {
      onNavigate(tab);
      return;
    }
    flash('success', `${label} 已准备好，后续可继续接更深的页面跳转`);
  };

  const handleContextAction = (context: GrowthContextLink) => {
    if (onOpenContext) {
      onOpenContext(context);
      return;
    }
    handleAction(context.tab === 'growth' ? 'growth_handbook' : context.tab, context.label);
  };

  return (
    <div className="animate-in space-y-6 fade-in duration-300">
      <div className="rounded-[28px] border border-[#DDE6FF] bg-[radial-gradient(circle_at_top_left,_rgba(51,92,254,0.08),_transparent_34%),linear-gradient(180deg,#FFFFFF_0%,#FAFBFF_100%)] p-6 shadow-[0_24px_70px_rgba(15,23,42,0.04)]">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-3">
            <div className="inline-flex items-center rounded-full border border-[#D6E1FF] bg-white px-3 py-1 text-[12px] font-medium text-[#335CFE] shadow-sm">
              <Sparkles className="mr-1.5 h-3.5 w-3.5" /> 成长勋章会根据真实业务行为自动点亮
            </div>
            <div>
              <h2 className="text-[28px] font-semibold tracking-tight text-slate-900">成长勋章</h2>
              <p className="mt-2 max-w-3xl text-[14px] leading-7 text-slate-500">
                系统会从会议、任务、复盘、知识沉淀和成长练习里自动识别你的工作行为。每一枚勋章都能解释为什么没亮、离点亮还差什么，以及由哪些真实证据触发。
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {[
              { label: '已点亮', value: board?.overview.litBadges ?? 0 },
              { label: '本月新增', value: board?.overview.monthlyNewBadges ?? 0 },
              { label: '勋章 XP', value: board?.overview.totalXp ?? 0 },
              { label: '即将点亮', value: board?.overview.readyBadges ?? 0 },
            ].map((item) => (
              <div key={item.label} className="min-w-[118px] rounded-[22px] border border-white/80 bg-white/88 p-4 shadow-[0_18px_40px_rgba(148,163,184,0.08)] backdrop-blur">
                <div className="text-[12px] font-medium text-slate-400">{item.label}</div>
                <div className="mt-3 text-[30px] font-semibold tracking-tight text-slate-900">{item.value}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-2 text-[12px] text-slate-500">
          <span className="rounded-full border border-slate-200 bg-white px-3 py-1 font-medium text-slate-500">
            部分勋章依赖 CRM / 审批 / 财务等模块事件，未接通前会保持灰色但不会误算
          </span>
          <button
            type="button"
            onClick={() => setConnectivityFilter('connected')}
            className={cx(
              'rounded-full border px-3 py-1 font-medium transition-colors',
              connectivityFilter === 'connected' ? 'border-[#D9E3FF] bg-white text-[#4B63D9]' : 'border-slate-200 bg-white text-slate-500 hover:border-slate-300',
            )}
          >
            已接通 {connectedBadgeCount}
          </button>
          <button
            type="button"
            onClick={() => setConnectivityFilter('unsupported')}
            className={cx(
              'rounded-full border px-3 py-1 font-medium transition-colors',
              connectivityFilter === 'unsupported' ? 'border-amber-200 bg-amber-50 text-amber-700' : 'border-slate-200 bg-white text-slate-500 hover:border-slate-300',
            )}
          >
            待接通 {unsupportedBadgeCount}
          </button>
          {upcomingNames.length ? (
            upcomingNames.map((name) => (
              <span key={name} className="rounded-full border border-[#D9E3FF] bg-white px-3 py-1 font-medium text-[#4B63D9]">
                即将点亮：{name}
              </span>
            ))
          ) : (
            <span className="rounded-full border border-slate-200 bg-white px-3 py-1 font-medium text-slate-500">继续沉淀真实业务行为，系统会自动更新勋章进度</span>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-5">
          <div className="rounded-[24px] border border-gray-100 bg-white p-4 shadow-sm">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="搜索勋章、说明或下一步动作..."
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50/70 py-3 pl-10 pr-4 text-[13px] font-medium text-slate-700 placeholder:text-slate-400 focus:border-[#C9D7FF] focus:bg-white focus:outline-none"
                />
              </div>
              <div className="flex flex-wrap gap-2">
                {[
                  ['all', '全部'],
                  ['lit', '已点亮'],
                  ['progress', '进行中'],
                  ['locked', '未点亮'],
                ].map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setFilter(value as BadgeFilter)}
                    className={cx(
                      'rounded-2xl px-3.5 py-2 text-[12px] font-medium transition-colors',
                      filter === value ? 'bg-[#335CFE] text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200/80',
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {[
                ['connected', '已接通'],
                ['unsupported', '待接通'],
                ['all', '全部'],
              ].map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setConnectivityFilter(value as BadgeConnectivityFilter)}
                  className={cx(
                    'rounded-full px-3 py-1.5 text-[12px] font-medium transition-colors',
                    connectivityFilter === value ? 'bg-[#EBF0FF] text-[#335CFE]' : 'bg-slate-50 text-slate-500 hover:bg-slate-100',
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setCategoryId('all')}
                className={cx(
                  'rounded-full px-3 py-1.5 text-[12px] font-medium transition-colors',
                  categoryId === 'all' ? 'bg-[#EBF0FF] text-[#335CFE]' : 'bg-slate-50 text-slate-500 hover:bg-slate-100',
                )}
              >
                全部分组
              </button>
              {(board?.categories || []).map((category) => (
                <button
                  key={category.id}
                  type="button"
                  onClick={() => setCategoryId(category.id)}
                  className={cx(
                    'rounded-full px-3 py-1.5 text-[12px] font-medium transition-colors',
                    categoryId === category.id ? 'bg-[#EBF0FF] text-[#335CFE]' : 'bg-slate-50 text-slate-500 hover:bg-slate-100',
                  )}
                >
                  {category.label}
                </button>
              ))}
            </div>
          </div>

          {isLoading ? (
            <div className="rounded-[24px] border border-dashed border-slate-200 bg-white p-10 text-center text-[13px] font-medium text-slate-400">成长勋章加载中...</div>
          ) : null}

          {!isLoading && !filteredCategories.length ? (
            <div className="rounded-[24px] border border-dashed border-slate-200 bg-white p-10 text-center text-[13px] font-medium text-slate-400">
              当前筛选条件下没有匹配的勋章
            </div>
          ) : null}

          {filteredCategories.map((category) => (
            <section key={category.id} className="space-y-3">
              <div className="flex items-center justify-between px-1">
                <div>
                  <h3 className="text-[17px] font-semibold text-slate-900">{category.label}</h3>
                  <p className="mt-1 text-[12px] text-slate-400">
                    {category.litCount} / {category.totalCount} 已点亮 · 映射能力：{category.abilityLabel}
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                {category.badges.map((badge) => (
                  <button
                    key={badge.id}
                    type="button"
                    onClick={() => setSelectedBadgeId(badge.id)}
                    className={cx(
                      'group rounded-[26px] border bg-white p-5 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-[0_18px_48px_rgba(15,23,42,0.08)]',
                      selectedBadgeId === badge.id ? 'border-[#C9D7FF] shadow-[0_20px_50px_rgba(51,92,254,0.08)]' : 'border-slate-100',
                    )}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <BadgeToken badge={badge} />
                      <div className={cx('rounded-full px-2.5 py-1 text-[11px] font-semibold', badgePalette(badge.state).chip)}>{STATE_LABELS[badge.state]}</div>
                    </div>
                    <div className="mt-5">
                      <div className="flex items-center justify-between">
                        <h4 className="text-[16px] font-semibold tracking-tight text-slate-900">{badge.name}</h4>
                        <span className="text-[12px] font-semibold text-[#335CFE]">+{badge.xp} XP</span>
                      </div>
                      <p className="mt-2 min-h-[40px] text-[13px] leading-6 text-slate-500">{badge.description}</p>
                    </div>
                    <div className="mt-4">
                      <div className="flex items-center justify-between text-[11px] font-medium text-slate-400">
                        <span>{badge.progressText}</span>
                        <span>{badge.progressPercent}%</span>
                      </div>
                      <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
                        <div className="h-full rounded-full bg-[#335CFE] transition-all" style={{ width: `${badge.progressPercent}%` }} />
                      </div>
                      <p className="mt-3 line-clamp-2 text-[12px] leading-5 text-slate-500">{badge.nextActionText}</p>
                      {badgeNeedsModuleConnection(badge) ? (
                        <div className="mt-3 rounded-full border border-amber-100 bg-amber-50 px-2.5 py-1 text-[10px] font-medium text-amber-700">
                          当前依赖模块未接通
                        </div>
                      ) : null}
                      {badge.missingSignals.length ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {badge.missingSignals.slice(0, 2).map((signal) => (
                            <span key={`${badge.id}-${signal}`} className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-medium text-slate-500">
                              {signal}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  </button>
                ))}
              </div>
            </section>
          ))}
        </div>

        <aside className="rounded-[28px] border border-slate-100 bg-white shadow-sm">
          {selectedBadge ? (
            <div className="flex h-full flex-col">
              <div className="flex items-start justify-between border-b border-slate-100 p-6">
                <div className="flex items-center gap-4">
                  <BadgeToken badge={selectedBadge} size="lg" />
                  <div>
                    <div className={cx('inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold', badgePalette(selectedBadge.state).chip)}>
                      {STATE_LABELS[selectedBadge.state]}
                    </div>
                    <h3 className="mt-3 text-[24px] font-semibold tracking-tight text-slate-900">{selectedBadge.name}</h3>
                    <p className="mt-1 text-[13px] text-slate-500">{selectedBadge.categoryLabel} · +{selectedBadge.xp} XP</p>
                  </div>
                </div>
                <button type="button" onClick={() => setSelectedBadgeId(null)} className="rounded-full p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700">
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="space-y-6 overflow-y-auto p-6">
                <section>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">这个勋章代表什么</div>
                  <p className="mt-3 text-[14px] leading-7 text-slate-600">{selectedBadge.whyItMatters}</p>
                </section>

                <section>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">你现在的进度</div>
                  <div className="mt-3 rounded-[22px] border border-slate-100 bg-slate-50/80 p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-[13px] font-semibold text-slate-900">{selectedBadge.progressText}</div>
                        <div className="mt-1 text-[12px] text-slate-500">当前进度 {selectedBadge.progressPercent}%</div>
                      </div>
                      <div className="text-[22px] font-semibold tracking-tight text-[#335CFE]">{selectedBadge.progressPercent}%</div>
                    </div>
                    <div className="mt-3 h-2 overflow-hidden rounded-full bg-white">
                      <div className="h-full rounded-full bg-[#335CFE]" style={{ width: `${selectedBadge.progressPercent}%` }} />
                    </div>
                  </div>
                </section>

                <section>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">离点亮还差什么</div>
                  <p className="mt-3 rounded-[22px] border border-[#DDE6FF] bg-[#F6F8FF] p-4 text-[13px] font-medium leading-6 text-[#335CFE]">{selectedBadge.nextActionText}</p>
                  {badgeNeedsModuleConnection(selectedBadge) ? (
                    <div className="mt-3 rounded-[18px] border border-amber-100 bg-amber-50 p-4 text-[12px] leading-6 text-amber-700">
                      这枚勋章依赖的模块事件还没接通。当前灰色不代表你没有做到，而是系统还没法稳定识别。
                    </div>
                  ) : null}
                  {selectedBadge.missingSignals.length ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {selectedBadge.missingSignals.map((signal) => (
                        <span key={`${selectedBadge.id}-missing-${signal}`} className="rounded-full border border-orange-100 bg-orange-50 px-2.5 py-1 text-[11px] font-medium text-orange-700">
                          {signal}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </section>

                <section>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">马上去做</div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {selectedBadge.actionLinks.map((action) => (
                      <button
                        key={`${selectedBadge.id}-${action.label}`}
                        type="button"
                        onClick={() => handleAction(action.tab, action.label)}
                        className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-2 text-[12px] font-medium text-slate-700 transition-colors hover:bg-slate-50"
                      >
                        {action.label}
                        <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                      </button>
                    ))}
                  </div>
                </section>

                <section>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">系统怎么识别</div>
                  <p className="mt-3 text-[13px] leading-6 text-slate-500">{selectedBadge.systemHowText}</p>
                </section>

                <section>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">主要触发场景</div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {selectedBadge.linkedContexts.length ? (
                      selectedBadge.linkedContexts.map((context) => (
                        <button
                          key={`${selectedBadge.id}-${context.objectType}-${context.objectId}`}
                          type="button"
                          onClick={() => handleContextAction(context)}
                          className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[12px] font-medium text-slate-600 transition hover:bg-slate-50"
                        >
                          {context.label}
                        </button>
                      ))
                    ) : (
                      <div className="rounded-[18px] border border-dashed border-slate-200 px-4 py-4 text-[12px] font-medium text-slate-400">
                        当前还没有足够上下文，说明这枚勋章依赖的业务事件源尚未完整接通。
                      </div>
                    )}
                  </div>
                </section>

                <section>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">最近触发的证据</div>
                  <div className="mt-3 space-y-3">
                    {selectedBadge.evidence.length ? (
                      selectedBadge.evidence.map((evidence) => (
                        <div key={evidence.id} className="rounded-[18px] border border-slate-100 bg-slate-50/70 p-4">
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <div className="text-[13px] font-semibold text-slate-900">{evidence.title}</div>
                              <div className="mt-1 text-[12px] leading-5 text-slate-500">{evidence.subtitle}</div>
                            </div>
                            <div className="shrink-0 text-[11px] font-medium text-slate-400">{formatDateLabel(evidence.occurredAt)}</div>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="rounded-[18px] border border-dashed border-slate-200 p-4 text-[12px] font-medium text-slate-400">
                        系统暂时还没有识别到足够的业务证据。你不需要手动领取，只要继续在真实工作流里完成对应动作即可。
                      </div>
                    )}
                  </div>
                </section>

                <section>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">对应经验记录</div>
                  <div className="mt-3 rounded-[22px] border border-slate-100 bg-white p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]">
                    {selectedBadge.unlockedAt ? (
                      <>
                        <div className="text-[13px] font-semibold text-slate-900">
                          你已于 {formatDateLabel(selectedBadge.unlockedAt)} 点亮【{selectedBadge.name}】
                        </div>
                        <div className="mt-2 text-[12px] leading-6 text-slate-500">系统已自动增加 +{selectedBadge.xp} XP，并同步写入成长总览与近期经验流。</div>
                        {selectedBadge.historical ? <div className="mt-3 inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-500">历史达成</div> : null}
                      </>
                    ) : (
                      <div className="text-[12px] leading-6 text-slate-500">点亮后会自动写入经验记录，不需要手动领取。</div>
                    )}
                  </div>
                </section>
              </div>
            </div>
          ) : (
            <div className="flex h-full min-h-[480px] items-center justify-center px-8 text-center text-[13px] font-medium leading-6 text-slate-400">
              从左侧勋章墙选择一枚勋章，系统会解释它代表什么、当前进度、下一步动作以及对应证据。
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
~~~

## `src/renderer/components/handbook/GrowthCenterView.tsx`

- 编码: `utf-8`

~~~tsx
import React, { useEffect, useState, useMemo, useCallback } from 'react';
import {
  ArrowRight,
  BookOpen,
  BrainCircuit,
  ChevronDown,
  ChevronUp,
  Crown,
  Eye,
  Heart,
  Layers3,
  Lightbulb,
  Lock,
  PenTool,
  Rocket,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Swords,
  Target,
  Trophy,
  Users,
  X,
  type LucideIcon,
  Flag,
  Briefcase,
  CalendarClock,
  Gauge,
  FileStack,
  CircleDashed,
  Handshake,
  HandHelping,
  Radar,
  Wrench,
  Star,
} from 'lucide-react';

import {
  getGrowthOverview,
  getHandbook,
  getGrowthBadges,
  getGrowthLedger,
  getGrowthWorkbench,
  updateGrowthPendingCapture,
  createHandbook,
  markHandbookEntryReused,
} from '../../lib/api';
import { useGrowthOverviewState } from '../growth/GrowthContext';
import type {
  GrowthAbilityKey,
  GrowthAbilityScore,
  GrowthAbilityGap,
  GrowthOverview,
  XpLedgerEntry,
  HandbookEntry,
  BadgeBoard,
  BadgeProgress,
  BadgeState,
  BadgeCategory,
  BadgeBoardOverview,
  GrowthPendingCapture,
  GrowthSourceCoverage,
  GrowthProjectHighlight,
} from '../../../shared/types';

/* ══════════════════════════════════════════════════════════════════════
   CSS — injected once, matches growth-center-preview.html exactly
   ──────────────────────────────────────────────────────────────────── */
const GROWTH_CSS = `
.gc-root { height: 100%; display: flex; flex-direction: column; overflow: hidden; background: #F9FAFB; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'PingFang SC', 'Hiragino Sans GB', sans-serif; color: #374151; -webkit-font-smoothing: antialiased; }

/* Header */
.gc-header { background: #fff; border-bottom: 1px solid #F3F4F6; padding: 20px 24px 0; flex-shrink: 0; }
.gc-header-top { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 16px; }
.gc-page-title { font-size: 18px; font-weight: 600; color: #0f172a; letter-spacing: -0.3px; }
.gc-page-subtitle { font-size: 11px; color: #94a3b8; font-weight: 500; margin-top: 3px; }
.gc-xp-area { display: flex; align-items: center; gap: 12px; }
.gc-rank-chip { display: flex; align-items: center; gap: 8px; background: #EEF3FF; border: 1px solid #D6E1FF; border-radius: 999px; padding: 6px 14px; font-size: 12px; font-weight: 600; color: #334155; }
.gc-xp-num { font-size: 14px; font-weight: 600; color: #1e293b; letter-spacing: -0.3px; text-align: right; }
.gc-xp-label { font-size: 11px; color: #94a3b8; font-weight: 400; }
.gc-xp-week { font-size: 11px; font-weight: 600; color: #10b981; text-align: right; }

/* Tab pills */
.gc-tab-bar { display: inline-flex; gap: 4px; background: #f1f5f9; border-radius: 16px; padding: 4px; }
.gc-tab-btn { background: none; border: none; cursor: pointer; padding: 6px 16px; font-size: 13px; font-weight: 500; border-radius: 16px; color: #64748b; transition: all 0.2s; }
.gc-tab-btn:hover { color: #334155; }
.gc-tab-btn.active { background: #fff; color: #5B7BFE; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }

/* Content */
.gc-content { flex: 1; overflow-y: auto; padding: 20px 24px; }
.gc-content-inner { max-width: 860px; margin: 0 auto; }

/* Cards */
.gc-card { background: #fff; border: 1px solid #f3f4f6; border-radius: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
.gc-card-inner { background: #fff; border: 1px solid #f3f4f6; border-radius: 22px; }
.gc-section-header { display: flex; align-items: flex-end; justify-content: space-between; padding: 0 4px; margin-bottom: 12px; }
.gc-section-title { font-size: 16px; font-weight: 600; color: #1e293b; }
.gc-section-hint { font-size: 11px; font-weight: 500; letter-spacing: 0.3px; color: #94a3b8; }

/* Icon token */
.gc-icon-token { display: flex; align-items: center; justify-content: center; border-radius: 999px; flex-shrink: 0; }
.gc-icon-token.sm { width: 20px; height: 20px; }
.gc-icon-token.md { width: 28px; height: 28px; }
.gc-icon-token.lg { width: 40px; height: 40px; }
.gc-icon-token.xl { width: 56px; height: 56px; }
.gc-icon-token.brand { background: #EEF3FF; }
.gc-icon-token.brand-border { background: #EEF3FF; border: 1px solid #D6E1FF; }
.gc-icon-token.gray { background: #f1f5f9; }

/* Insight cards */
.gc-insight-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.gc-insight-card { padding: 20px; }
.gc-insight-quote { font-size: 13px; color: #1e293b; line-height: 1.9; }
.gc-insight-meta { display: flex; align-items: center; justify-content: space-between; margin-top: 12px; }
.gc-insight-author { display: flex; align-items: center; gap: 8px; }
.gc-author-name { font-size: 11px; font-weight: 500; color: #64748b; }
.gc-source-tag { background: #f8fafc; border: 1px solid #f1f5f9; border-radius: 999px; padding: 2px 8px; font-size: 10px; color: #94a3b8; font-weight: 500; letter-spacing: 0.2px; }
.gc-like-btn { display: flex; align-items: center; gap: 4px; background: none; border: none; cursor: pointer; font-size: 11px; color: #D1D5DB; transition: color 0.2s; }
.gc-like-btn:hover { color: #5B7BFE; }
.gc-like-btn.liked { color: #5B7BFE; }

/* AI section */
.gc-ai-section { border-radius: 24px; background: radial-gradient(circle at top left, rgba(51,92,254,0.06), transparent 40%), linear-gradient(180deg, #fff 0%, #fafbff 100%); border: 1px solid #DDE6FF; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); margin-top: 24px; }
.gc-ai-chip { display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; border: 1px solid #D6E1FF; background: #fff; padding: 4px 12px; font-size: 12px; font-weight: 500; color: #335CFE; box-shadow: 0 1px 2px rgba(0,0,0,0.04); margin-bottom: 16px; }
.gc-pending-actions { display: flex; gap: 8px; margin-top: 12px; }
.gc-btn-brand { display: inline-flex; align-items: center; gap: 6px; background: #335CFE; color: #fff; border: none; border-radius: 999px; padding: 8px 16px; font-size: 12px; font-weight: 500; cursor: pointer; transition: background 0.2s; }
.gc-btn-brand:hover:not(:disabled) { background: #2C50E0; }
.gc-btn-brand:disabled { opacity: 0.6; cursor: not-allowed; }
@keyframes gc-toast-in { from { opacity: 0; transform: translateX(-50%) translateY(-8px); } to { opacity: 1; transform: translateX(-50%) translateY(0); } }
.gc-btn-ghost { background: none; border: 1px solid #e2e8f0; color: #64748b; border-radius: 999px; padding: 8px 16px; font-size: 12px; font-weight: 500; cursor: pointer; transition: background 0.2s; }
.gc-btn-ghost:hover { background: #f8fafc; }

/* Stats grid */
.gc-stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.gc-stat-card { border-radius: 22px; border: 1px solid #f3f4f6; background: #fff; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
.gc-stat-label { font-size: 12px; font-weight: 500; color: #94a3b8; }
.gc-stat-value { font-size: 24px; font-weight: 600; color: #0f172a; margin-top: 8px; letter-spacing: -0.5px; }

/* Template cards */
.gc-template-list { display: flex; flex-direction: column; gap: 8px; }
.gc-template-header { width: 100%; padding: 16px 20px; text-align: left; display: flex; align-items: center; gap: 16px; background: none; border: none; cursor: pointer; transition: background 0.2s; }
.gc-template-header:hover { background: rgba(248,250,252,0.5); }
.gc-template-info { flex: 1; min-width: 0; }
.gc-template-top { display: flex; align-items: center; justify-content: space-between; }
.gc-template-name { font-size: 13px; font-weight: 600; color: #1e293b; }
.gc-template-calls { font-size: 12px; font-weight: 600; color: #335CFE; flex-shrink: 0; margin-left: 12px; }
.gc-template-bottom { display: flex; align-items: center; gap: 12px; margin-top: 8px; }
.gc-template-meta { font-size: 11px; font-weight: 500; color: #94a3b8; }
.gc-progress-track { flex: 1; height: 3px; background: #f1f5f9; border-radius: 999px; overflow: hidden; }
.gc-progress-fill { height: 100%; border-radius: 999px; }
.gc-template-detail { padding: 0 20px 16px; }
.gc-template-detail-inner { background: #f8fafc; border-radius: 18px; padding: 16px; }
.gc-step-row { display: flex; align-items: center; gap: 12px; padding: 6px 0; }
.gc-step-num { font-size: 11px; font-weight: 600; color: #cbd5e1; width: 20px; text-align: right; }
.gc-step-text { font-size: 12px; font-weight: 500; color: #64748b; }
.gc-chevron { color: #cbd5e1; font-size: 12px; flex-shrink: 0; }

/* XP Overview hero */
.gc-xp-hero { border-radius: 28px; border: 1px solid #DDE6FF; background: radial-gradient(circle at top left, rgba(51,92,254,0.08), transparent 34%), linear-gradient(180deg, #fff 0%, #fafbff 100%); padding: 24px; box-shadow: 0 24px 70px rgba(15,23,42,0.04); }
.gc-xp-hero-top { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
.gc-xp-hero-rank { font-size: 16px; font-weight: 600; color: #0f172a; letter-spacing: -0.3px; }
.gc-xp-hero-num { font-size: 24px; font-weight: 600; color: #0f172a; letter-spacing: -0.5px; }
.gc-xp-hero-badge { display: inline-flex; align-items: center; gap: 4px; background: #ecfdf5; border-radius: 999px; padding: 4px 10px; font-size: 11px; font-weight: 600; color: #059669; }
.gc-xp-breakdown { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 20px; }
.gc-xp-break-card { border-radius: 22px; border: 1px solid rgba(255,255,255,0.8); background: rgba(255,255,255,0.88); padding: 16px; box-shadow: 0 18px 40px rgba(148,163,184,0.08); backdrop-filter: blur(8px); }
.gc-xp-break-top { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.gc-xp-break-label { font-size: 10px; font-weight: 500; color: #94a3b8; }
.gc-xp-break-val { font-size: 20px; font-weight: 600; color: #0f172a; letter-spacing: -0.3px; }

/* Badge grid */
.gc-badge-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 4px; }
.gc-badge-cell { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 12px 4px; cursor: pointer; transition: transform 0.2s; background: none; border: none; }
.gc-badge-cell:hover { transform: scale(1.03); }
.gc-badge-name { font-size: 11px; font-weight: 500; text-align: center; line-height: 1.3; max-width: 80px; }
.gc-badge-name.lit { color: #334155; }
.gc-badge-name.prog { color: #64748b; }
.gc-badge-name.lock { color: #cbd5e1; }
.gc-badge-sub { font-size: 10px; font-weight: 600; }

/* Leaderboard */
.gc-rank-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; padding: 0 4px; }
.gc-rank-header-left { display: flex; align-items: center; gap: 8px; }
.gc-rank-toggle { display: flex; background: #f1f5f9; border-radius: 999px; padding: 2px; }
.gc-rank-toggle-btn { padding: 6px 12px; font-size: 11px; font-weight: 500; border: none; cursor: pointer; border-radius: 999px; background: none; color: #94a3b8; transition: all 0.2s; }
.gc-rank-toggle-btn.active { background: #fff; color: #334155; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
.gc-rank-list { padding: 12px; display: flex; flex-direction: column; gap: 4px; }
.gc-rank-row { display: flex; align-items: center; gap: 12px; padding: 12px 16px; border-radius: 16px; }
.gc-rank-row.top3 { background: rgba(248,250,252,0.7); }
.gc-rank-num { font-size: 14px; font-weight: 600; width: 24px; text-align: center; flex-shrink: 0; }
.gc-rank-name-text { font-size: 13px; font-weight: 500; color: #334155; width: 64px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.gc-rank-xp { font-size: 12px; font-weight: 600; color: #64748b; width: 64px; text-align: right; flex-shrink: 0; }
.gc-rank-bar { flex: 1; height: 3px; background: #f1f5f9; border-radius: 999px; overflow: hidden; margin-left: 8px; }
.gc-rank-bar-fill { height: 100%; border-radius: 999px; }

/* MVP */
.gc-mvp { margin-top: 12px; border-radius: 22px; background: rgba(254,243,199,0.6); border: 1px solid #fde68a; padding: 16px 20px; }
.gc-mvp-top { display: flex; align-items: center; gap: 8px; }
.gc-mvp-title { font-size: 12px; font-weight: 600; color: #92400e; }
.gc-mvp-desc { font-size: 11px; color: rgba(146,64,14,0.7); margin-top: 4px; margin-left: 24px; }

.gc-space-y > * + * { margin-top: 24px; }

/* Ability growth tab */
.gc-radar-card { display: flex; flex-direction: column; align-items: center; gap: 48px; padding: 32px; }
@media (min-width: 768px) { .gc-radar-card { flex-direction: row; } }
.gc-radar-legend { display: flex; align-items: center; gap: 16px; font-size: 11px; font-weight: 500; color: #94a3b8; margin-top: 4px; }
.gc-radar-legend-dot { width: 8px; height: 8px; border-radius: 999px; margin-right: 6px; display: inline-block; }
.gc-ability-list { flex: 1; display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.gc-ability-row-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.gc-ability-row-left { display: flex; align-items: center; gap: 8px; }
.gc-ability-icon-box { display: flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 8px; }
.gc-ability-name { font-size: 13px; font-weight: 600; color: #1e293b; }
.gc-ability-stage { border-radius: 6px; border: 1px solid #f1f5f9; background: #f8fafc; padding: 1px 6px; font-size: 9px; font-weight: 500; letter-spacing: 1px; color: #94a3b8; text-transform: uppercase; }
.gc-ability-xp { font-size: 12px; font-weight: 600; color: #335CFE; }
.gc-ability-delta { font-size: 10px; font-weight: 500; color: #10b981; margin-left: 6px; }
.gc-ability-bar { height: 6px; background: #f8fafc; border-radius: 999px; overflow: hidden; }
.gc-ability-bar-fill { height: 100%; background: #5B7BFE; border-radius: 999px; }
.gc-ability-evidence { font-size: 10px; font-weight: 500; color: #94a3b8; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* Timeline */
.gc-timeline-entry { display: flex; gap: 16px; }
.gc-timeline-line { display: flex; flex-direction: column; align-items: center; flex-shrink: 0; }
.gc-timeline-dot { display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 999px; flex-shrink: 0; }
.gc-timeline-tail { width: 1px; flex: 1; background: #f1f5f9; margin: 4px 0; }
.gc-timeline-content { flex: 1; padding-bottom: 20px; }
.gc-timeline-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.gc-timeline-title { font-size: 13px; font-weight: 500; color: #1e293b; line-height: 1.4; }
.gc-timeline-tags { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 6px; }
.gc-timeline-tag { border-radius: 999px; padding: 2px 8px; font-size: 10px; font-weight: 500; letter-spacing: 0.2px; }
.gc-timeline-tag.special { background: #fff7ed; color: #ea580c; }
.gc-timeline-tag.normal { background: #f1f5f9; color: #64748b; }
.gc-timeline-xp { font-size: 13px; font-weight: 600; letter-spacing: -0.3px; flex-shrink: 0; }
.gc-timeline-time { font-size: 10px; font-weight: 500; color: #94a3b8; margin-top: 2px; text-align: right; }

/* Gap card */
.gc-gap-card { padding: 20px; }
.gc-gap-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.gc-no-gap { border-radius: 24px; background: rgba(236,253,245,0.4); border: 1px solid #a7f3d0; padding: 16px 20px; }

/* Loading */
.gc-loading { display: flex; align-items: center; justify-content: center; padding: 80px 0; }
.gc-loading-icon { width: 40px; height: 40px; border-radius: 999px; background: #EEF3FF; display: flex; align-items: center; justify-content: center; animation: gc-pulse 1.5s ease-in-out infinite; margin-bottom: 12px; }
@keyframes gc-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
.gc-loading-text { font-size: 13px; font-weight: 500; color: #94a3b8; }

/* Empty state */
.gc-empty { border-radius: 24px; border: 1px dashed #e2e8f0; background: #fff; padding: 40px 20px; text-align: center; }
.gc-empty-title { font-size: 14px; font-weight: 600; color: #475569; margin-bottom: 4px; }
.gc-empty-desc { font-size: 13px; color: #94a3b8; max-width: 400px; margin: 0 auto; line-height: 1.6; }

/* Badge modal */
.gc-modal-overlay { position: fixed; inset: 0; z-index: 50; display: flex; align-items: center; justify-content: center; background: rgba(15,23,42,0.2); backdrop-filter: blur(4px); }
.gc-modal { border-radius: 28px; border: 1px solid rgba(255,255,255,0.7); background: #fff; box-shadow: 0 24px 80px rgba(15,23,42,0.18); padding: 24px; width: 420px; max-width: 90vw; max-height: 80vh; overflow-y: auto; }
`;

/* Inject CSS once */
let cssInjected = false;
function injectGrowthCSS() {
  if (cssInjected) return;
  const style = document.createElement('style');
  style.setAttribute('data-growth-center', 'true');
  style.textContent = GROWTH_CSS;
  document.head.appendChild(style);
  cssInjected = true;
}

/* ══════════════════════════════════════════════════════════════════════
   Icon motif map — for badge rendering from API data
   ──────────────────────────────────────────────────────────────────── */
const MOTIF_ICON_MAP: Record<string, LucideIcon> = {
  meeting_ring: Users,
  report_arrow: ArrowRight,
  chat_bolt: Sparkles,
  linked_rings: Users,
  handoff: HandHelping,
  radar_ping: Radar,
  search_chat: Search,
  stack_docs: Layers3,
  path_nodes: Target,
  handshake_seal: Handshake,
  blueprint_flag: Flag,
  grid_blocks: Layers3,
  summit_flag: Flag,
  shield_ping: ShieldCheck,
  seal_box: Briefcase,
  calendar_lines: CalendarClock,
  dashboard_gauge: Gauge,
  manual_stack: BookOpen,
  stamp_flow: CircleDashed,
  loop_note: ArrowRight,
  invoice_shield: ShieldCheck,
  wallet_gate: Briefcase,
  scroll_seal: FileStack,
  bill_return: ArrowRight,
  cart_checklist: Briefcase,
  mentor_orbit: Users,
  idea_burst: Lightbulb,
  cards_spark: Sparkles,
  path_flag: Flag,
  wrench_up: Wrench,
};

/* ══════════════════════════════════════════════════════════════════════
   Ability visual config
   ──────────────────────────────────────────────────────────────────── */
const ABILITY_VISUALS: Record<string, { icon: LucideIcon; color: string; bg: string }> = {
  exec:    { icon: Rocket,      color: '#5B7BFE', bg: 'rgba(91,123,254,0.1)' },
  collab:  { icon: Users,       color: '#5B7BFE', bg: 'rgba(91,123,254,0.1)' },
  analyze: { icon: BrainCircuit, color: '#64748b', bg: '#f1f5f9' },
  insight: { icon: Eye,         color: '#10b981', bg: 'rgba(16,185,129,0.08)' },
  risk:    { icon: ShieldAlert,  color: '#f97316', bg: 'rgba(249,115,22,0.08)' },
  write:   { icon: PenTool,     color: '#5B7BFE', bg: 'rgba(91,123,254,0.1)' },
};

/* ══════════════════════════════════════════════════════════════════════
   Utility functions
   ──────────────────────────────────────────────────────────────────── */
function formatRelativeMoment(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const diffMs = Date.now() - date.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  if (diffHours < 1) return '刚刚';
  if (diffHours < 24) return `${diffHours}小时前`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays === 1) return '昨天';
  if (diffDays < 7) return `${diffDays}天前`;
  if (diffDays < 14) return '1周前';
  return date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' });
}

function weekLabelFromDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const oneJan = new Date(date.getFullYear(), 0, 1);
  const weekNum = Math.ceil(((date.getTime() - oneJan.getTime()) / 86400000 + oneJan.getDay() + 1) / 7);
  return `第${weekNum}周`;
}

const SOURCE_TYPE_CN: Record<string, string> = {
  review_insight: '复盘提炼',
  meeting: '会议沉淀',
  task_context_candidate: '任务经验',
  task_attachment_candidate: '附件提炼',
  review_insight_pending: '复盘提炼',
  manual: '手动录入',
};

function sourceTypeCN(raw: string): string {
  return SOURCE_TYPE_CN[raw] || raw.replace(/_/g, ' ');
}

function pickQuoteText(entry: HandbookEntry): string {
  const title = entry.title || '';
  const summary = entry.summary || '';
  if (title.length > 0 && title.length <= 80) return title;
  if (summary.length > 120) return summary.slice(0, 117) + '…';
  return summary || title.slice(0, 117) + (title.length > 117 ? '…' : '');
}

function xpTypeLabel(xpType: string): string {
  if (xpType === 'codification') return '经验沉淀';
  if (xpType === 'reuse') return '方法复用';
  if (xpType === 'improvement') return '成长改进';
  return '复盘反思';
}

/* ══════════════════════════════════════════════════════════════════════
   Badge palette + BadgeToken — SVG ring with icon center
   ──────────────────────────────────────────────────────────────────── */
const STATE_LABELS: Record<BadgeState, string> = {
  locked: '未解锁',
  progress: '进行中',
  ready: '待点亮',
  lit: '已点亮',
  mastered: '已精通',
};

function badgePalette(state: BadgeState) {
  if (state === 'lit' || state === 'mastered') {
    return {
      ring: '#335CFE', glow: 'drop-shadow(0 16px 40px rgba(51,92,254,0.18))',
      outer: 'linear-gradient(180deg,rgba(246,249,255,0.98),rgba(225,233,255,0.98))',
      center: 'linear-gradient(180deg,rgba(83,121,255,0.98),rgba(44,78,233,0.98))',
      iconColor: '#fff', border: 'rgba(113,144,255,0.26)',
    };
  }
  if (state === 'ready') {
    return {
      ring: '#5B7BFE', glow: 'drop-shadow(0 12px 30px rgba(91,123,254,0.16))',
      outer: 'linear-gradient(180deg,#fff,rgba(240,244,255,1))',
      center: 'linear-gradient(180deg,rgba(239,244,255,1),rgba(221,231,255,1))',
      iconColor: '#335CFE', border: 'rgba(113,144,255,0.22)',
    };
  }
  if (state === 'progress') {
    return {
      ring: '#8FA4FF', glow: 'drop-shadow(0 8px 20px rgba(143,164,255,0.08))',
      outer: 'linear-gradient(180deg,#fff,rgba(243,246,253,1))',
      center: 'linear-gradient(180deg,#fff,rgba(243,246,253,1))',
      iconColor: '#5B7BFE', border: 'rgba(203,213,225,0.8)',
    };
  }
  return {
    ring: '#D5DCE8', glow: 'none',
    outer: 'linear-gradient(180deg,#fff,rgba(245,247,250,1))',
    center: 'linear-gradient(180deg,#fff,rgba(245,247,250,1))',
    iconColor: '#94a3b8', border: 'rgba(226,232,240,0.9)',
  };
}

function BadgeToken({ badge, size = 'md' }: { badge: BadgeProgress; size?: 'md' | 'lg' }) {
  const pal = badgePalette(badge.state);
  const Icon = MOTIF_ICON_MAP[badge.iconMotif] || Sparkles;
  const d = size === 'lg' ? 116 : 84;
  const r = size === 'lg' ? 44 : 31;
  const sw = size === 'lg' ? 5 : 4;
  const circ = 2 * Math.PI * r;
  const off = circ - (circ * badge.progressPercent) / 100;
  const innerSize = size === 'lg' ? 76 : 56;
  const iconSize = size === 'lg' ? 32 : 24;

  return (
    <div style={{ position: 'relative', width: d, height: d, filter: pal.glow }}>
      <div style={{ position: 'absolute', inset: 0, borderRadius: 999, border: `1px solid ${pal.border}`, background: pal.outer }} />
      <svg style={{ position: 'absolute', inset: 0, transform: 'rotate(-90deg)' }} viewBox={`0 0 ${d} ${d}`}>
        <circle cx={d / 2} cy={d / 2} r={r} fill="none" stroke="rgba(226,232,240,0.66)" strokeWidth={sw} />
        <circle cx={d / 2} cy={d / 2} r={r} fill="none" stroke={pal.ring} strokeWidth={sw}
          strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={off}
          style={{ transition: 'stroke-dashoffset 0.7s ease' }} />
      </svg>
      <div style={{
        position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
        width: innerSize, height: innerSize, borderRadius: 999,
        border: `1px solid ${pal.border}`, background: pal.center,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon width={iconSize} height={iconSize} color={pal.iconColor} strokeWidth={1.9} />
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   Badge Modal
   ──────────────────────────────────────────────────────────────────── */
function BadgeModal({ badge, onClose }: { badge: BadgeProgress; onClose: () => void }) {
  const pal = badgePalette(badge.state);
  return (
    <div className="gc-modal-overlay" onClick={onClose}>
      <div className="gc-modal" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <BadgeToken badge={badge} size="lg" />
            <div>
              <div style={{ fontSize: 16, fontWeight: 600, color: '#0f172a', letterSpacing: -0.3 }}>{badge.name}</div>
              <div style={{ fontSize: 12, fontWeight: 500, color: '#94a3b8', marginTop: 2 }}>{badge.categoryLabel} · +{badge.xp} XP</div>
              <span style={{
                display: 'inline-block', marginTop: 4, borderRadius: 999, padding: '2px 8px',
                fontSize: 10, fontWeight: 600,
                background: pal.iconColor === '#fff' ? 'rgba(51,92,254,0.1)' : '#f1f5f9',
                color: pal.iconColor === '#fff' ? '#335CFE' : '#475569',
              }}>{STATE_LABELS[badge.state]}</span>
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 6, borderRadius: 999, color: '#94a3b8' }}>
            <X size={16} />
          </button>
        </div>

        <p style={{ fontSize: 13, lineHeight: 1.8, color: '#475569' }}>{badge.whyItMatters || badge.description}</p>

        {/* Progress bar */}
        <div style={{ marginTop: 16, borderRadius: 18, background: '#f8fafc', padding: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#334155' }}>{badge.progressText}</span>
            <span style={{ fontSize: 14, fontWeight: 600, color: '#335CFE' }}>{badge.progressPercent}%</span>
          </div>
          <div style={{ height: 8, borderRadius: 999, background: '#fff', overflow: 'hidden' }}>
            <div style={{ height: '100%', borderRadius: 999, background: '#335CFE', width: `${badge.progressPercent}%`, transition: 'width 0.5s' }} />
          </div>
          {badge.nextActionText && (
            <p style={{ marginTop: 12, fontSize: 11, lineHeight: 1.6, color: '#64748b' }}>{badge.nextActionText}</p>
          )}
        </div>

        {badge.unlockedAt && (
          <p style={{ marginTop: 12, fontSize: 11, fontWeight: 500, color: '#94a3b8' }}>获得时间：{formatRelativeMoment(badge.unlockedAt)}</p>
        )}

        {badge.missingSignals.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <p style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1.5, color: '#94a3b8', marginBottom: 8 }}>离点亮还差</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {badge.missingSignals.map((signal) => (
                <span key={signal} style={{ borderRadius: 999, border: '1px solid #e2e8f0', background: '#f8fafc', padding: '4px 10px', fontSize: 10, fontWeight: 500, color: '#64748b' }}>
                  {signal}
                </span>
              ))}
            </div>
          </div>
        )}

        {badge.evidence.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <p style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1.5, color: '#94a3b8', marginBottom: 8 }}>达成证据</p>
            {badge.evidence.slice(0, 3).map((ev, i) => (
              <div key={i} style={{ borderRadius: 14, background: '#f8fafc', padding: '8px 12px', marginBottom: 8 }}>
                <p style={{ fontSize: 12, fontWeight: 500, color: '#334155' }}>{ev.title}</p>
                <p style={{ fontSize: 10, color: '#94a3b8', marginTop: 2 }}>{ev.subtitle} · {formatRelativeMoment(ev.occurredAt)}</p>
              </div>
            ))}
          </div>
        )}

        <button onClick={onClose} style={{
          marginTop: 20, width: '100%', borderRadius: 999, border: '1px solid #e2e8f0',
          background: '#fff', fontSize: 13, fontWeight: 500, color: '#475569', padding: '10px 0',
          cursor: 'pointer', transition: 'background 0.2s',
        }}>关闭</button>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   Hexagonal Radar Chart — matches preview exactly
   ──────────────────────────────────────────────────────────────────── */
function AbilityRadar({ abilities, gaps }: { abilities: GrowthAbilityScore[]; gaps?: GrowthAbilityGap[] }) {
  const size = 320;
  const cx = 160, cy = 160, R = 110;
  const n = abilities.length;
  if (n < 3) return null;

  const angles = abilities.map((_, i) => (Math.PI * 2 * i / n) - Math.PI / 2);
  const hexPt = (angle: number, r: number): [number, number] => [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
  const hexPoly = (r: number) => angles.map(a => hexPt(a, r).join(',')).join(' ');

  const gapMap = new Map((gaps || []).map(g => [g.abilityKey, g.requiredScore]));
  const hasRequired = gapMap.size > 0;

  const prevPts = abilities.map((ab, i) => hexPt(angles[i], R * ab.previousScore / 100).join(',')).join(' ');
  const curPts = abilities.map((ab, i) => hexPt(angles[i], R * ab.currentScore / 100).join(',')).join(' ');
  const reqPts = hasRequired
    ? abilities.map((ab, i) => hexPt(angles[i], R * (gapMap.get(ab.abilityKey) ?? ab.currentScore) / 100).join(',')).join(' ')
    : '';

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ overflow: 'visible' }}>
      {/* Grid */}
      {[0.2, 0.4, 0.6, 0.8, 1.0].map(s => (
        <polygon key={s} points={hexPoly(R * s)} fill="none" stroke="#f1f5f9" strokeWidth="1" />
      ))}
      {/* Axis lines */}
      {angles.map((a, i) => {
        const [ex, ey] = hexPt(a, R);
        return <line key={i} x1={cx} y1={cy} x2={ex} y2={ey} stroke="#f1f5f9" strokeWidth="1" />;
      })}
      {/* Previous (gray dashed) */}
      <polygon points={prevPts} fill="rgba(203,213,225,0.12)" stroke="#cbd5e1" strokeWidth="1.5" strokeDasharray="4 3" />
      {/* Required (amber dashed) */}
      {hasRequired && (
        <polygon points={reqPts} fill="none" stroke="#f59e0b" strokeWidth="1.2" strokeDasharray="3 3" />
      )}
      {/* Current (blue filled) */}
      <polygon points={curPts} fill="rgba(91,123,254,0.15)" stroke="#5B7BFE" strokeWidth="2" />
      {/* Current dots */}
      {abilities.map((ab, i) => {
        const [dx, dy] = hexPt(angles[i], R * ab.currentScore / 100);
        return <circle key={ab.abilityKey} cx={dx} cy={dy} r={4} fill="#5B7BFE" stroke="#fff" strokeWidth={2} />;
      })}
      {/* Labels */}
      {abilities.map((ab, i) => {
        const [lx, ly] = hexPt(angles[i], R + 32);
        const anchor = lx < cx - 10 ? 'end' : lx > cx + 10 ? 'start' : 'middle';
        return (
          <g key={`lbl-${ab.abilityKey}`}>
            <text x={lx} y={ly - 2} textAnchor={anchor} dominantBaseline="central" fontSize="12" fontWeight="500" fill="#64748b">{ab.label}</text>
            <text x={lx} y={ly + 14} textAnchor={anchor} dominantBaseline="central" fontSize="11" fontWeight="600" fill="#5B7BFE">{ab.currentScore}</text>
          </g>
        );
      })}
    </svg>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   Tab 1: Experience Wall
   ══════════════════════════════════════════════════════════════════ */
function ExperienceWallTab({ overview }: { overview: GrowthOverview | null }) {
  const [entries, setEntries] = useState<HandbookEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'month' | 'quarter'>('all');
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());
  const [pushingIds, setPushingIds] = useState<Set<string>>(new Set());
  const [toastMsg, setToastMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const showToast = useCallback((text: string, type: 'success' | 'error') => {
    setToastMsg({ text, type });
    setTimeout(() => setToastMsg(null), 2500);
  }, []);

  const reloadEntries = useCallback(() => {
    getHandbook()
      .then((res) => setEntries(res.entries || []))
      .catch(() => setEntries([]));
  }, []);

  useEffect(() => {
    setIsLoading(true);
    getHandbook()
      .then((res) => setEntries(res.entries || []))
      .catch(() => setEntries([]))
      .finally(() => setIsLoading(false));
  }, []);

  const pendingCaptures = useMemo(
    () => (overview?.pendingCaptures || []).filter((c) => c.status === 'open' && !dismissedIds.has(c.id)),
    [overview, dismissedIds],
  );

  const handlePushToWall = useCallback(async (capture: GrowthPendingCapture) => {
    if (pushingIds.has(capture.id)) return;
    setPushingIds((prev) => new Set([...prev, capture.id]));
    try {
      // Create handbook entry from the quote
      await createHandbook({
        title: capture.title,
        summary: capture.title,
        tags: ['经验金句', 'AI提炼'],
        sourceType: 'review_insight',
      });
      // Mark capture as promoted
      await updateGrowthPendingCapture(capture.id, { status: 'promoted' });
      setDismissedIds((prev) => new Set([...prev, capture.id]));
      reloadEntries();
      showToast('已成功推上经验墙', 'success');
    } catch (err) {
      console.error('[GrowthCenter] 推上经验墙失败:', err);
      showToast(err instanceof Error ? err.message : '推送失败，请重试', 'error');
    } finally {
      setPushingIds((prev) => {
        const next = new Set(prev);
        next.delete(capture.id);
        return next;
      });
    }
  }, [reloadEntries, pushingIds, showToast]);

  const handleSkip = useCallback(async (capture: GrowthPendingCapture) => {
    try {
      await updateGrowthPendingCapture(capture.id, { status: 'dismissed', reason: '用户跳过' });
      setDismissedIds((prev) => new Set([...prev, capture.id]));
    } catch (err) {
      console.error('[GrowthCenter] 跳过失败:', err);
    }
  }, []);

  const sortedEntries = useMemo(() => {
    let filtered = [...entries];
    const now = new Date();
    if (filter === 'month') {
      const cutoff = new Date(now.getFullYear(), now.getMonth(), 1);
      filtered = filtered.filter((e) => new Date(e.createdAt) >= cutoff);
    } else if (filter === 'quarter') {
      const quarterStart = new Date(now.getFullYear(), Math.floor(now.getMonth() / 3) * 3, 1);
      filtered = filtered.filter((e) => new Date(e.createdAt) >= quarterStart);
    }
    return filtered.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
  }, [entries, filter]);

  const col1 = sortedEntries.filter((_, i) => i % 2 === 0);
  const col2 = sortedEntries.filter((_, i) => i % 2 === 1);

  if (isLoading) {
    return (
      <div className="gc-loading">
        <div style={{ textAlign: 'center' }}>
          <div className="gc-loading-icon"><BookOpen size={20} color="#335CFE" /></div>
          <div className="gc-loading-text">加载经验墙...</div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ position: 'relative' }}>
      {toastMsg && (
        <div style={{
          position: 'fixed', top: 24, left: '50%', transform: 'translateX(-50%)', zIndex: 9999,
          background: toastMsg.type === 'success' ? '#10b981' : '#ef4444', color: '#fff',
          padding: '8px 20px', borderRadius: 999, fontSize: 13, fontWeight: 500,
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)', animation: 'gc-toast-in 0.2s ease-out',
        }}>
          {toastMsg.text}
        </div>
      )}
      {sortedEntries.length > 0 && (
        <div>
          <div className="gc-section-header">
            <div className="gc-section-title">组织经验墙</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              {(['all', 'month', 'quarter'] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  style={{
                    padding: '4px 10px', borderRadius: 8, fontSize: 11, fontWeight: 600, border: 'none', cursor: 'pointer',
                    background: filter === f ? '#EEF3FF' : 'transparent',
                    color: filter === f ? '#335CFE' : '#94a3b8',
                  }}
                >
                  {{ all: '全部', month: '本月', quarter: '本季度' }[f]}
                </button>
              ))}
            </div>
          </div>
          <div className="gc-insight-grid">
            {sortedEntries.map((entry) => {
              const isAI = entry.authorUserName?.includes('大周') || entry.authorUserName?.includes('庆华') || entry.authorUserName?.includes('花花') || entry.authorUserName?.includes('罗茜茜') || entry.sourceType?.includes('ai');
              const hasLikes = entry.reuseCount > 0;
              const quoteText = pickQuoteText(entry);
              const authorName = entry.authorUserName || '团队';
              const projectName = entry.clientName || '';
              return (
                <div key={entry.id} className="gc-card gc-insight-card">
                  <div className="gc-insight-quote">&ldquo;{quoteText}&rdquo;</div>
                  <div className="gc-insight-meta">
                    <div className="gc-insight-author">
                      <div className={`gc-icon-token sm ${isAI ? 'brand' : 'gray'}`}>
                        {isAI ? <Sparkles size={10} color="#335CFE" /> : <Users size={10} color="#64748b" />}
                      </div>
                      <span className="gc-author-name">{authorName}</span>
                      {projectName && <span className="gc-source-tag">{projectName}</span>}
                      <span className="gc-source-tag">{sourceTypeCN(entry.sourceType || '经验')} · {weekLabelFromDate(entry.createdAt)}</span>
                    </div>
                    <button
                      className={`gc-like-btn${hasLikes ? ' liked' : ''}`}
                      onClick={() => {
                        markHandbookEntryReused(entry.id)
                          .then(() => reloadEntries())
                          .catch(() => {});
                      }}
                    >
                      <Heart size={12} fill={hasLikes ? '#5B7BFE' : 'none'} color={hasLikes ? '#5B7BFE' : '#D1D5DB'} strokeWidth={2} />
                      {entry.reuseCount > 0 ? ` ${entry.reuseCount}` : ''}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {pendingCaptures.length > 0 && (
        <div className="gc-ai-section">
          <div className="gc-ai-chip">
            <Lightbulb size={14} color="#335CFE" />
            AI 为你提炼了 {pendingCaptures.length} 条经验
          </div>
          {pendingCaptures.map((capture) => {
            const quoteText = capture.title || capture.summary || '';
            const sourceLabel = capture.summary && capture.summary.startsWith('来源')
              ? capture.summary
              : capture.clientName
                ? `来源：${capture.clientName}${capture.eventLineName ? ' · ' + capture.eventLineName : ''}`
                : capture.eventLineName
                  ? `来源：${capture.eventLineName}`
                  : `来源：${(capture.sourceType || '').replace(/_/g, ' ').replace('review insight pending', '复盘提炼')}`;
            return (
              <div key={capture.id} className="gc-card-inner" style={{ padding: 20, marginBottom: 12 }}>
                <div className="gc-insight-quote">&ldquo;{quoteText}&rdquo;</div>
                <div style={{ marginTop: 8, fontSize: 11, fontWeight: 500, color: '#94a3b8' }}>
                  {sourceLabel}
                </div>
                <div className="gc-pending-actions">
                  <button className="gc-btn-brand" disabled={pushingIds.has(capture.id)} onClick={() => void handlePushToWall(capture)}>
                    <ArrowRight size={12} color="#fff" /> {pushingIds.has(capture.id) ? '推送中…' : '推上经验墙'}
                  </button>
                  <button className="gc-btn-ghost" onClick={() => void handleSkip(capture)}>跳过</button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {sortedEntries.length === 0 && pendingCaptures.length === 0 && (
        <div className="gc-empty">
          <div className="gc-loading-icon" style={{ margin: '0 auto 12px', animation: 'none' }}>
            <BookOpen size={20} color="#335CFE" />
          </div>
          <div className="gc-empty-title">经验墙暂无内容</div>
          <div className="gc-empty-desc">完成任务复盘后，AI 会自动提取经验金句并沉淀到这里。</div>
        </div>
      )}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   Tab 2: Ability Growth
   ══════════════════════════════════════════════════════════════════ */
function AbilityGrowthTab({ overview }: { overview: GrowthOverview | null }) {
  const growthState = useGrowthOverviewState();
  const isLoading = !overview && (growthState?.isGrowthLoading ?? false);
  const abilities = overview?.abilities || [];
  const topGaps = useMemo(() => (overview?.abilityGaps || []).slice(0, 3), [overview]);

  const recentEntries = useMemo(() => {
    if (!overview?.recentEntries?.length) return [];
    const seen = new Map<string, XpLedgerEntry>();
    for (const entry of overview.recentEntries) {
      const dateKey = entry.createdAt?.slice(0, 10) || '';
      const key = `${entry.sourceType}|${entry.sourceId}|${entry.abilityKey}|${dateKey}`;
      const existing = seen.get(key);
      if (existing) {
        (existing as XpLedgerEntry & { totalXp: number }).totalXp += entry.totalXp || entry.delta;
      } else {
        seen.set(key, { ...entry });
      }
    }
    return [...seen.values()]
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      .slice(0, 8);
  }, [overview]);

  if (isLoading) {
    return (
      <div className="gc-loading">
        <div style={{ textAlign: 'center' }}>
          <div className="gc-loading-icon"><BrainCircuit size={20} color="#335CFE" /></div>
          <div className="gc-loading-text">加载能力数据...</div>
        </div>
      </div>
    );
  }

  if (!abilities.length) {
    return (
      <div className="gc-empty">
        <div className="gc-loading-icon" style={{ margin: '0 auto 12px', animation: 'none', width: 48, height: 48 }}>
          <BrainCircuit size={24} color="#335CFE" />
        </div>
        <div className="gc-empty-title">能力雷达待激活</div>
        <div className="gc-empty-desc">完成任务并写下复盘后，六维能力分布会在这里自动生成。系统会从会议、任务、复盘和知识沉淀中自动识别你的成长信号。</div>
      </div>
    );
  }

  return (
    <div className="gc-space-y">
      {/* Radar + Ability List */}
      <div className="gc-card gc-radar-card">
        <div style={{ flexShrink: 0 }}>
          <AbilityRadar abilities={abilities} gaps={topGaps} />
          <div className="gc-radar-legend" style={{ justifyContent: 'center', marginTop: 12 }}>
            <span><span className="gc-radar-legend-dot" style={{ background: '#5B7BFE' }} />当前</span>
            <span><span className="gc-radar-legend-dot" style={{ background: '#cbd5e1' }} />上期</span>
            {topGaps.length > 0 && <span><span className="gc-radar-legend-dot" style={{ background: '#f59e0b' }} />要求</span>}
          </div>
        </div>
        <div className="gc-ability-list">
          {[...abilities].sort((a, b) => b.weeklyXp - a.weeklyXp).map((ab) => {
            const v = ABILITY_VISUALS[ab.abilityKey] || ABILITY_VISUALS.exec;
            const AbIcon = v.icon;
            return (
              <div key={ab.abilityKey}>
                <div className="gc-ability-row-top">
                  <div className="gc-ability-row-left">
                    <div className="gc-ability-icon-box" style={{ background: v.bg }}>
                      <AbIcon size={14} color={v.color} />
                    </div>
                    <span className="gc-ability-name">{ab.label}</span>
                    <span className="gc-ability-stage">{ab.stage}</span>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <span className="gc-ability-xp">{ab.totalXp} XP</span>
                    {ab.weeklyXp > 0 && <span className="gc-ability-delta">+{ab.weeklyXp}</span>}
                  </div>
                </div>
                <div className="gc-ability-bar">
                  <div className="gc-ability-bar-fill" style={{ width: `${Math.min(ab.currentScore, 100)}%` }} />
                </div>
                <div className="gc-ability-evidence">{ab.evidence}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Timeline */}
      <div>
        <div className="gc-section-header">
          <div className="gc-section-title">成长时间线</div>
          <span className="gc-section-hint">近期能力变化</span>
        </div>
        {recentEntries.length > 0 ? (
          <div className="gc-card" style={{ padding: 20 }}>
            {recentEntries.map((entry, i) => {
              const v = ABILITY_VISUALS[entry.abilityKey] || ABILITY_VISUALS.exec;
              const AbIcon = v.icon;
              const isSpecial = entry.premiumXp > 0 || entry.xpType !== 'reflection' || entry.totalXp >= 14;
              const isLast = i === recentEntries.length - 1;
              return (
                <div key={`${entry.id}-${i}`} className="gc-timeline-entry">
                  <div className="gc-timeline-line">
                    <div className="gc-timeline-dot" style={{ background: v.bg }}>
                      <AbIcon size={14} color={v.color} />
                    </div>
                    {!isLast && <div className="gc-timeline-tail" />}
                  </div>
                  <div className="gc-timeline-content">
                    <div className="gc-timeline-top">
                      <div>
                        <div className="gc-timeline-title">{entry.sourceTitle || entry.reason || entry.abilityLabel}</div>
                        <div className="gc-timeline-tags">
                          <span className={`gc-timeline-tag ${isSpecial ? 'special' : 'normal'}`}>+{entry.totalXp || entry.delta} XP</span>
                          <span className="gc-timeline-tag normal">{entry.abilityLabel}</span>
                          {entry.clientName && <span className="gc-timeline-tag normal">{entry.clientName}</span>}
                        </div>
                      </div>
                      <span style={{ fontSize: 11, color: '#94a3b8', whiteSpace: 'nowrap', flexShrink: 0 }}>
                        {formatRelativeMoment(entry.createdAt)}
                      </span>
                    </div>
                    {entry.contextSummary && (
                      <div style={{ fontSize: 12, color: '#64748b', marginTop: 6, lineHeight: 1.6 }}>{entry.contextSummary}</div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="gc-empty">
            <div className="gc-loading-icon" style={{ margin: '0 auto 12px', animation: 'none' }}>
              <Sparkles size={20} color="#335CFE" />
            </div>
            <div className="gc-empty-title">本周成长记录待生成</div>
            <div className="gc-empty-desc">完成任务并写下复盘后，成长动态会在这里实时出现。</div>
          </div>
        )}
      </div>

      {/* Gap Cards */}
      {topGaps.length > 0 && (
        <div>
          <div className="gc-section-header">
            <div className="gc-section-title">能力缺口</div>
            <span className="gc-section-hint">需要重点突破的方向</span>
          </div>
          <div className="gc-gap-grid">
            {topGaps.map((gap) => {
              const v = ABILITY_VISUALS[gap.abilityKey] || ABILITY_VISUALS.exec;
              const GapIcon = v.icon;
              const pct = Math.round(gap.currentScore / gap.requiredScore * 100);
              return (
                <div key={`${gap.sourceType}-${gap.abilityKey}`} className="gc-card" style={{ padding: 20 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                    <div className="gc-ability-icon-box" style={{ background: v.bg }}>
                      <GapIcon size={16} color={v.color} />
                    </div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#1e293b' }}>{gap.label}</div>
                      <div style={{ fontSize: 11, color: '#94a3b8' }}>{gap.currentScore} → {gap.requiredScore} (差 {gap.gap})</div>
                    </div>
                  </div>
                  <div className="gc-ability-bar" style={{ marginBottom: 8 }}>
                    <div className="gc-ability-bar-fill" style={{ width: `${pct}%`, background: '#f97316' }} />
                  </div>
                  <div style={{ fontSize: 11, color: '#64748b', lineHeight: 1.6, marginBottom: 8 }}>{gap.reason}</div>
                  <div style={{ fontSize: 10, color: '#94a3b8' }}>来源: {gap.sourceLabel}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}
      {topGaps.length === 0 && (
        <div className="gc-no-gap">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, fontWeight: 600, color: '#047857' }}>
            <ShieldCheck size={16} color="#047857" />
            没有明显的能力缺口
          </div>
          <div style={{ fontSize: 11, color: 'rgba(4,120,87,0.7)', marginTop: 4, marginLeft: 24 }}>
            当前项目和事件线对你的能力要求都在覆盖范围内。
          </div>
        </div>
      )}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   Tab 3: Org Contribution
   ══════════════════════════════════════════════════════════════════ */
function OrgContributionTab({ overview }: { overview: GrowthOverview | null }) {
  const [handbookEntries, setHandbookEntries] = useState<HandbookEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    getHandbook()
      .then((res) => setHandbookEntries(res.entries || []))
      .catch(() => setHandbookEntries([]))
      .finally(() => setIsLoading(false));
  }, []);

  const totalReuses = useMemo(() => handbookEntries.reduce((sum, e) => sum + e.reuseCount, 0), [handbookEntries]);
  const templateEntries = useMemo(() => [...handbookEntries].sort((a, b) => b.reuseCount - a.reuseCount).slice(0, 8), [handbookEntries]);
  const totalContribXp = useMemo(() => handbookEntries.reduce((sum, e) => sum + e.reuseCount * 6, 0), [handbookEntries]);
  const monthlyXp = useMemo(() => {
    const cutoff = Date.now() - 30 * 24 * 3600 * 1000;
    return handbookEntries
      .filter((e) => new Date(e.createdAt).getTime() > cutoff)
      .reduce((sum, e) => sum + (e.reuseCount > 0 ? e.reuseCount * 6 : 0), 0);
  }, [handbookEntries]);

  const stats = [
    { label: '我创建的模板', value: String(handbookEntries.length) },
    { label: '被调用次数', value: String(totalReuses) },
    { label: '累计贡献 XP', value: `+${totalContribXp}` },
    { label: '本月', value: `+${monthlyXp}` },
  ];

  if (isLoading && !overview) {
    return (
      <div className="gc-loading">
        <div style={{ textAlign: 'center' }}>
          <div className="gc-loading-icon"><Layers3 size={20} color="#335CFE" /></div>
          <div className="gc-loading-text">加载贡献数据...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="gc-space-y">
      {/* Stats grid */}
      <div className="gc-stats-grid">
        {stats.map((stat) => (
          <div key={stat.label} className="gc-stat-card">
            <div className="gc-stat-label">{stat.label}</div>
            <div className="gc-stat-value">{stat.value}</div>
          </div>
        ))}
      </div>

      {/* Work templates */}
      {templateEntries.length > 0 && (
        <div>
          <div className="gc-section-header">
            <div className="gc-section-title">工作模板</div>
            <span className="gc-section-hint">被团队复用的标准流程</span>
          </div>
          <div className="gc-template-list">
            {templateEntries.map((entry) => {
              const isExpanded = expandedId === entry.id;
              const abilityKey = entry.abilityKeys?.[0];
              const v = abilityKey ? ABILITY_VISUALS[abilityKey] : null;
              const AbIcon = v?.icon || Target;
              const iconColor = v?.color || '#335CFE';
              const pct = Math.min(100, (entry.reuseCount / 10) * 100);
              const estimatedXp = entry.reuseCount * 6 + entry.tags.length * 2;

              return (
                <div key={entry.id} className="gc-card" style={{ overflow: 'hidden' }}>
                  <button
                    className="gc-template-header"
                    onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                  >
                    <div className="gc-icon-token lg brand">
                      <AbIcon size={20} color="#335CFE" />
                    </div>
                    <div className="gc-template-info">
                      <div className="gc-template-top">
                        <span className="gc-template-name">{entry.title}</span>
                        <span className="gc-template-calls">调用 {entry.reuseCount} 次</span>
                      </div>
                      <div className="gc-template-bottom">
                        <span className="gc-template-meta">{entry.tags.length} 个标签 · +{estimatedXp} XP</span>
                        <div className="gc-progress-track">
                          <div className="gc-progress-fill" style={{ width: `${pct}%`, background: 'rgba(91,123,254,0.4)' }} />
                        </div>
                      </div>
                    </div>
                    <span className="gc-chevron">{isExpanded ? '▴' : '▾'}</span>
                  </button>
                  {isExpanded && (
                    <div className="gc-template-detail">
                      <div className="gc-template-detail-inner">
                        <p style={{ fontSize: 12, lineHeight: 1.8, color: '#64748b', marginBottom: entry.tags.length > 0 ? 12 : 0 }}>
                          {entry.summary || entry.contextSummary}
                        </p>
                        {entry.tags.length > 0 && entry.tags.map((tag, i) => (
                          <div key={tag} className="gc-step-row">
                            <span className="gc-step-num">{i + 1}.</span>
                            <span className="gc-step-text">{tag}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {templateEntries.length === 0 && (
        <div className="gc-empty">
          <div className="gc-loading-icon" style={{ margin: '0 auto 12px', animation: 'none' }}>
            <Layers3 size={20} color="#335CFE" />
          </div>
          <div className="gc-empty-title">贡献数据还在积累中</div>
          <div className="gc-empty-desc">完成更多任务和复盘后，你的组织贡献分析会在这里展示。</div>
        </div>
      )}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   Tab 4: Badges & Rank
   ══════════════════════════════════════════════════════════════════ */
function BadgesAndRankTab({ overview }: { overview: GrowthOverview | null }) {
  const [badgeBoard, setBadgeBoard] = useState<BadgeBoard | null>(null);
  const [selectedBadge, setSelectedBadge] = useState<BadgeProgress | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [rankView, setRankView] = useState<'total' | 'week'>('total');

  useEffect(() => {
    setIsLoading(true);
    getGrowthBadges()
      .then(setBadgeBoard)
      .catch(() => setBadgeBoard(null))
      .finally(() => setIsLoading(false));
  }, []);

  const rank = overview?.rank;
  const totalXp = overview?.totalXp ?? 0;
  const weeklyXp = overview?.weeklyXp ?? 0;
  const boardOverview = badgeBoard?.overview;

  const allBadges = useMemo(() => {
    if (!badgeBoard?.categories) return [];
    return badgeBoard.categories.flatMap((cat) => cat.badges);
  }, [badgeBoard]);

  const coverage = overview?.sourceCoverage;
  const xpBreakdown = useMemo(() => {
    if (!coverage) return [];
    return [
      { label: '模板贡献', value: coverage.handbookSignals, icon: Layers3 },
      { label: '经验墙', value: coverage.reviewSignals, icon: Lightbulb },
      { label: '流程调用', value: coverage.taskSignals, icon: ArrowRight },
      { label: '执行质量', value: coverage.meetingSignals, icon: ShieldCheck },
    ];
  }, [coverage]);

  if (isLoading) {
    return (
      <div className="gc-loading">
        <div style={{ textAlign: 'center' }}>
          <div className="gc-loading-icon"><Trophy size={20} color="#335CFE" /></div>
          <div className="gc-loading-text">加载徽章数据...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="gc-space-y">
      {/* XP Hero */}
      <div className="gc-xp-hero">
        <div className="gc-xp-hero-top">
          <div className="gc-icon-token xl brand-border">
            <Swords size={28} color="#335CFE" strokeWidth={1.8} />
          </div>
          <div>
            <div className="gc-xp-hero-rank">{rank?.fullLabel || '加载中'}</div>
            <div className="gc-xp-hero-num">
              {totalXp.toLocaleString()} <span className="gc-xp-label">XP</span>
            </div>
          </div>
          <div style={{ marginLeft: 'auto' }}>
            {weeklyXp > 0 && (
              <div className="gc-xp-hero-badge">
                <Sparkles size={12} /> +{weeklyXp} 本周
              </div>
            )}
          </div>
        </div>
        {rank && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontSize: 11, fontWeight: 500, color: '#94a3b8' }}>
                {rank.nextName ? `距${rank.nextName}还需 ${rank.xpToNext} XP` : '已达最高段位'}
              </span>
              <span style={{ fontSize: 11, fontWeight: 500, color: '#94a3b8' }}>{rank.progress}%</span>
            </div>
            <div className="gc-progress-track" style={{ height: 4 }}>
              <div className="gc-progress-fill" style={{ width: `${rank.progress}%`, background: '#5B7BFE' }} />
            </div>
          </div>
        )}
        {xpBreakdown.length > 0 && (
          <div className="gc-xp-breakdown">
            {xpBreakdown.map((item) => {
              const BIcon = item.icon;
              return (
                <div key={item.label} className="gc-xp-break-card">
                  <div className="gc-xp-break-top">
                    <BIcon size={14} color="#335CFE" />
                    <span className="gc-xp-break-label">{item.label}</span>
                  </div>
                  <div className="gc-xp-break-val">{item.value}</div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Badge Grid */}
      <div>
        <div className="gc-section-header">
          <div className="gc-section-title">我的徽章</div>
          <span className="gc-section-hint">已点亮 {boardOverview?.litBadges ?? 0}/{boardOverview?.totalBadges ?? allBadges.length}</span>
        </div>
        {allBadges.length > 0 ? (
          <div className="gc-card" style={{ padding: 20 }}>
            <div className="gc-badge-grid">
              {allBadges.map((badge) => {
                const isLit = badge.state === 'lit' || badge.state === 'mastered';
                const isReady = badge.state === 'ready';
                const inProgress = badge.state === 'progress';
                const nameClass = isLit ? 'lit' : inProgress ? 'prog' : 'lock';

                return (
                  <button key={badge.id} className="gc-badge-cell" onClick={() => setSelectedBadge(badge)}>
                    <BadgeToken badge={badge} size="md" />
                    <span className={`gc-badge-name ${nameClass}`}>
                      {badge.state === 'locked' ? '???' : badge.name}
                    </span>
                    {isLit && (
                      <span style={{ display: 'inline-block', background: '#ecfdf5', borderRadius: 999, padding: '2px 8px', fontSize: 9, fontWeight: 600, color: '#059669' }}>
                        {STATE_LABELS[badge.state]}
                      </span>
                    )}
                    {isReady && (
                      <span style={{ display: 'inline-block', background: 'rgba(91,123,254,0.1)', borderRadius: 999, padding: '2px 8px', fontSize: 9, fontWeight: 600, color: '#335CFE' }}>
                        待点亮
                      </span>
                    )}
                    {inProgress && (
                      <span className="gc-badge-sub" style={{ color: '#5B7BFE' }}>{badge.progressPercent}%</span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="gc-empty">
            <div className="gc-loading-icon" style={{ margin: '0 auto 12px', animation: 'none' }}>
              <Trophy size={20} color="#335CFE" />
            </div>
            <div className="gc-empty-title">徽章系统加载中</div>
            <div className="gc-empty-desc">徽章数据暂未就绪，完成更多工作后会自动解锁。</div>
          </div>
        )}
      </div>

      {/* Leaderboard */}
      <div>
        <div className="gc-rank-header">
          <div className="gc-rank-header-left">
            <Trophy size={16} color="#f59e0b" />
            <div className="gc-section-title" style={{ marginBottom: 0 }}>组织排行榜</div>
          </div>
          <div className="gc-rank-toggle">
            <button
              className={`gc-rank-toggle-btn${rankView === 'total' ? ' active' : ''}`}
              onClick={() => setRankView('total')}
            >总榜</button>
            <button
              className={`gc-rank-toggle-btn${rankView === 'week' ? ' active' : ''}`}
              onClick={() => setRankView('week')}
            >本周</button>
          </div>
        </div>
        <div className="gc-card gc-rank-list">
          {overview?.userName ? (
            <div className="gc-rank-row top3">
              <span className="gc-rank-num" style={{ color: '#5B7BFE' }}>1</span>
              <div className="gc-icon-token md brand">
                <Users size={14} color="#335CFE" />
              </div>
              <span className="gc-rank-name-text">{overview.userName}</span>
              <span className="gc-rank-xp">{totalXp.toLocaleString()}</span>
              <div className="gc-rank-bar">
                <div className="gc-rank-bar-fill" style={{ width: '100%', background: '#5B7BFE' }} />
              </div>
            </div>
          ) : null}
          <p style={{ textAlign: 'center', padding: '16px 0', fontSize: 12, color: '#94a3b8' }}>更多团队成员数据积累中...</p>
        </div>

        {/* MVP */}
        {weeklyXp > 0 && overview?.userName && (
          <div className="gc-mvp">
            <div className="gc-mvp-top">
              <Crown size={16} color="#b45309" />
              <div className="gc-mvp-title">本周 MVP：{overview.userName}（+{weeklyXp} XP）</div>
            </div>
            <div className="gc-mvp-desc">持续成长，保持领先</div>
          </div>
        )}
      </div>

      {selectedBadge && <BadgeModal badge={selectedBadge} onClose={() => setSelectedBadge(null)} />}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   Main Export — GrowthCenterView
   ══════════════════════════════════════════════════════════════════ */
type GrowthTab = 'experience' | 'ability' | 'contribution' | 'badges';

const TABS: { key: GrowthTab; label: string }[] = [
  { key: 'experience', label: '经验墙' },
  { key: 'ability', label: '能力成长' },
  { key: 'contribution', label: '组织贡献' },
  { key: 'badges', label: '徽章与排行' },
];

export function GrowthCenterView() {
  const [activeTab, setActiveTab] = useState<GrowthTab>('experience');
  const growthState = useGrowthOverviewState();
  const [headerOverview, setHeaderOverview] = useState<GrowthOverview | null>(null);

  // Inject CSS on mount
  useEffect(() => { injectGrowthCSS(); }, []);

  // Load overview
  useEffect(() => {
    if (growthState?.growthOverview) return;
    getGrowthOverview().then(setHeaderOverview).catch(() => undefined);
  }, []);

  const overview = growthState?.growthOverview ?? headerOverview;
  const rankLabel = overview?.rank?.fullLabel || '加载中';
  const totalXp = overview?.totalXp ?? 0;
  const weeklyXp = overview?.weeklyXp ?? 0;

  return (
    <div className="gc-root">
      {/* Header */}
      <div className="gc-header">
        <div className="gc-header-top">
          <div>
            <div className="gc-page-title">成长中心</div>
            <div className="gc-page-subtitle">把工作经验变成组织资产</div>
          </div>
          <div className="gc-xp-area">
            <div className="gc-rank-chip">
              <Swords size={14} color="#335CFE" strokeWidth={2} />
              {rankLabel}
            </div>
            <div>
              <div className="gc-xp-num">{totalXp.toLocaleString()} <span className="gc-xp-label">XP</span></div>
              {weeklyXp > 0 && <div className="gc-xp-week">+{weeklyXp}</div>}
            </div>
          </div>
        </div>
        <div className="gc-tab-bar">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              className={`gc-tab-btn${activeTab === tab.key ? ' active' : ''}`}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="gc-content">
        <div className="gc-content-inner">
          {activeTab === 'experience' && <ExperienceWallTab overview={overview} />}
          {activeTab === 'ability' && <AbilityGrowthTab overview={overview} />}
          {activeTab === 'contribution' && <OrgContributionTab overview={overview} />}
          {activeTab === 'badges' && <BadgesAndRankTab overview={overview} />}
        </div>
      </div>
    </div>
  );
}

export default GrowthCenterView;
~~~

## `src/renderer/components/handbook/GrowthHandbookView.tsx`

- 编码: `utf-8`

~~~tsx
import React, { useEffect, useMemo, useState } from 'react';
import {
  BookOpen,
  BrainCircuit,
  Eye,
  Flame,
  GitMerge,
  PenTool,
  PlusCircle,
  Rocket,
  ShieldAlert,
  Sparkles,
  Users,
  X,
} from 'lucide-react';

import { acceptGrowthRecommendation, dismissGrowthRecommendation, getGrowthOverview, getGrowthWorkbench, updateGrowthPendingCapture } from '../../lib/api';
import { useGrowthOverviewState } from '../growth/GrowthContext';
import { GrowthAssetLibraryDrawer } from './GrowthAssetLibraryDrawer';
import { GrowthBadgeWall } from './GrowthBadgeWall';
import { GrowthLedgerDrawer } from './GrowthLedgerDrawer';
import { GrowthLearningWorkbench } from './GrowthLearningWorkbench';
import type { GrowthAbilityGap, GrowthAbilityKey, GrowthContextLink, GrowthFocusAction, GrowthOverview, GrowthPendingCapture, GrowthProjectHighlight, GrowthRank, GrowthWorkbenchSnapshot, HandbookEntry, HandbookEntryPayload, HandbookSettings, LearningRecommendation, Task } from '../../../shared/types';

type FlashLevel = 'success' | 'error';
type GrowthHandbookTab = 'overview' | 'records' | 'learning' | 'map';

type GrowthHandbookViewProps = {
  entries: HandbookEntry[];
  settings: HandbookSettings;
  currentClientId?: string | null;
  tasks?: Task[];
  onCreateEntry: (payload: HandbookEntryPayload) => Promise<HandbookEntry | void>;
  onTasksReload?: () => Promise<unknown> | void;
  onNavigate?: (tab: string) => void;
  onOpenContext?: (context: GrowthContextLink) => void;
  flash: (level: FlashLevel, message: string) => void;
};

type ExperienceCard = {
  id: string;
  title: string;
  summary: string;
  source: string;
  tags: string[];
  xp: number;
  dateLabel: string;
  type: string;
  isMethod: boolean;
};

type DailyDrop = {
  id: string;
  task: string;
  time: string;
  createdAt: string;
  xp: number;
  baseXp?: number;
  premiumXp?: number;
  premiumRate?: number;
  type: string;
  isSpecial: boolean;
  abilityLabels: string[];
  entryCount: number;
};

type LearningCard = {
  id: string;
  theme: string;
  reason: string;
  whyNow?: string;
  learnContent: {
    type: string;
    title: string;
    icon: React.ComponentType<{ className?: string }>;
  };
  practiceTask: string;
  isUrgent: boolean;
  xpReward: number;
  questType: string;
  recommendationId?: string | null;
  linkedTaskId?: string | null;
  clientName?: string | null;
  eventLineName?: string | null;
  projectStage?: string | null;
  triggerNode?: string | null;
  linkedContexts?: GrowthContextLink[];
};

type AbilityCard = {
  id: string;
  name: string;
  currentScore: number;
  previousScore: number;
  requiredScore: number;
  stage: string;
  nextStage: string;
  icon: React.ComponentType<{ className?: string }>;
  iconClassName: string;
  bgClassName: string;
  numericInc: number;
  evidence: string;
  gapReason?: string;
  gapSourceLabel?: string;
  gapSourceType?: string;
  gapSourceId?: string;
};

type DraftState = {
  title: string;
  summary: string;
  tags: string;
  sourceType: string;
};

type RankTier = {
  key: string;
  name: string;
  minXp: number;
  accent: string;
  accentSoft: string;
  accentDeep: string;
  glow: string;
  metal: string;
  ribbon: string;
  showDivision?: boolean;
};

type RankMeta = {
  key: string;
  name: string;
  tier: RankTier;
  divisionLabel: string | null;
  fullLabel: string;
  nextLabel: string | null;
  xpToNextTier: number;
  progress: number;
};

const SOURCE_XP_MAP: Record<string, number> = {
  manual: 15,
  meeting: 20,
  topic_candidate: 25,
  task: 15,
  analysis: 25,
};

const SOURCE_LABEL_MAP: Record<string, string> = {
  manual: '手动沉淀',
  meeting: '会议结论',
  topic_candidate: '情报候选',
  task: '任务复盘',
  analysis: '分析学习',
};

const SOURCE_TYPE_MAP: Record<string, string> = {
  manual: '经验',
  meeting: '结论',
  topic_candidate: '判断',
  task: '复盘',
  analysis: '方法',
};

const ABILITY_VISUALS: Record<string, Pick<AbilityCard, 'icon' | 'iconClassName' | 'bgClassName'>> = {
  exec: { icon: Rocket, iconClassName: 'text-[#5B7BFE]', bgClassName: 'bg-[#5B7BFE]/10' },
  collab: { icon: Users, iconClassName: 'text-[#5B7BFE]', bgClassName: 'bg-[#5B7BFE]/10' },
  analyze: { icon: BrainCircuit, iconClassName: 'text-gray-500', bgClassName: 'bg-gray-100' },
  insight: { icon: Eye, iconClassName: 'text-emerald-500', bgClassName: 'bg-emerald-50' },
  risk: { icon: ShieldAlert, iconClassName: 'text-orange-500', bgClassName: 'bg-orange-50' },
  write: { icon: PenTool, iconClassName: 'text-[#5B7BFE]', bgClassName: 'bg-[#5B7BFE]/10' },
};

const RANK_DIVISIONS = ['III', 'II', 'I'] as const;

const RANK_TIERS: RankTier[] = [
  {
    key: 'bronze',
    name: '倔强青铜',
    minXp: 0,
    accent: '#B67A48',
    accentSoft: '#F7D7B4',
    accentDeep: '#6E4324',
    glow: '#F4E0CC',
    metal: '#E6B889',
    ribbon: '#8D552E',
  },
  {
    key: 'silver',
    name: '秩序白银',
    minXp: 120,
    accent: '#BAC8D8',
    accentSoft: '#F5F8FF',
    accentDeep: '#6E7C90',
    glow: '#E9EEF6',
    metal: '#DCE4EF',
    ribbon: '#8896AA',
  },
  {
    key: 'gold',
    name: '荣耀黄金',
    minXp: 260,
    accent: '#D7A63A',
    accentSoft: '#FFF1B8',
    accentDeep: '#8A5A17',
    glow: '#FFF2CC',
    metal: '#F0D36F',
    ribbon: '#A46C1A',
  },
  {
    key: 'platinum',
    name: '尊贵铂金',
    minXp: 460,
    accent: '#43C3BA',
    accentSoft: '#DAFBF4',
    accentDeep: '#1D7A74',
    glow: '#D8F6F0',
    metal: '#8CE6D8',
    ribbon: '#2F8F86',
  },
  {
    key: 'diamond',
    name: '永恒钻石',
    minXp: 720,
    accent: '#5E7CFF',
    accentSoft: '#DDE6FF',
    accentDeep: '#3149B7',
    glow: '#E0E8FF',
    metal: '#AFC0FF',
    ribbon: '#3B58CB',
  },
  {
    key: 'star',
    name: '至尊星耀',
    minXp: 1040,
    accent: '#1EA8D8',
    accentSoft: '#D8F5FF',
    accentDeep: '#0D5F8F',
    glow: '#D8F1FB',
    metal: '#8AD7F0',
    ribbon: '#167AA7',
  },
  {
    key: 'king',
    name: '最强王者',
    minXp: 1420,
    accent: '#E06445',
    accentSoft: '#FFE1D6',
    accentDeep: '#8D331A',
    glow: '#FFE5DC',
    metal: '#F3B28D',
    ribbon: '#AA4425',
  },
  {
    key: 'glory',
    name: '荣耀王者',
    minXp: 1900,
    accent: '#D84A4A',
    accentSoft: '#FFE0E0',
    accentDeep: '#8B1F2D',
    glow: '#FFE1E1',
    metal: '#F2A1A1',
    ribbon: '#A92839',
  },
  {
    key: 'legend',
    name: '传奇王者',
    minXp: 2600,
    accent: '#D79D2F',
    accentSoft: '#FFF1C5',
    accentDeep: '#7A4012',
    glow: '#FFF1D9',
    metal: '#F0CF77',
    ribbon: '#A8601D',
    showDivision: false,
  },
];

function cx(...classNames: Array<string | false | null | undefined>) {
  return classNames.filter(Boolean).join(' ');
}

function buildDraft(defaultTagsText: string, sourceType = 'manual'): DraftState {
  return {
    title: '',
    summary: '',
    tags: defaultTagsText,
    sourceType,
  };
}

function formatRelativeDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const diffMs = Date.now() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays <= 0) return '今天';
  if (diffDays === 1) return '昨天';
  if (diffDays < 7) return `${diffDays}天前`;
  return date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' });
}

function formatRelativeMoment(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const diffMs = Date.now() - date.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  if (diffHours < 1) return '刚刚';
  if (diffHours < 24) return `${diffHours}小时前`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays === 1) return '昨天';
  if (diffDays < 7) return `${diffDays}天前`;
  return date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' });
}

function parseTags(value: string) {
  return value
    .split(/[，,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function isMethodEntry(entry: HandbookEntry) {
  const normalized = `${entry.title} ${entry.summary} ${entry.tags.join(' ')}`.toLowerCase();
  return ['模板', '方法', '清单', '复用', '机制'].some((keyword) => normalized.includes(keyword.toLowerCase()));
}

function getSourceLabel(sourceType: string) {
  return SOURCE_LABEL_MAP[sourceType] || sourceType || '手动沉淀';
}

function getTypeLabel(sourceType: string) {
  return SOURCE_TYPE_MAP[sourceType] || '经验';
}

function getSourceXp(sourceType: string) {
  return SOURCE_XP_MAP[sourceType] || 10;
}

function buildFallbackRank(score: number): GrowthRank {
  const currentTier = [...RANK_TIERS].reverse().find((tier) => score >= tier.minXp) || RANK_TIERS[0];
  const currentIndex = RANK_TIERS.findIndex((tier) => tier.key === currentTier.key);
  const nextTier = RANK_TIERS[currentIndex + 1] || null;
  const tierSpan = nextTier ? Math.max(1, nextTier.minXp - currentTier.minXp) : 600;
  const tierOffset = Math.max(0, score - currentTier.minXp);
  const progress = nextTier ? Math.max(0, Math.min(1, tierOffset / tierSpan)) : 1;
  const bucket = currentTier.showDivision === false ? -1 : Math.min(RANK_DIVISIONS.length - 1, Math.floor(progress * RANK_DIVISIONS.length));
  const divisionLabel = currentTier.showDivision === false ? null : RANK_DIVISIONS[Math.max(0, bucket)];
  return {
    key: currentTier.key,
    name: currentTier.name,
    division: divisionLabel,
    fullLabel: divisionLabel ? `${currentTier.name} ${divisionLabel}` : currentTier.name,
    nextName: nextTier ? nextTier.name : null,
    xpToNext: nextTier ? Math.max(0, nextTier.minXp - score) : 0,
    progress,
  };
}

function decorateRank(rank: GrowthRank): RankMeta {
  const tier = RANK_TIERS.find((item) => item.key === rank.key) || RANK_TIERS[0];
  return {
    key: rank.key,
    name: rank.name,
    tier,
    divisionLabel: rank.division || null,
    fullLabel: rank.fullLabel,
    nextLabel: rank.nextName || null,
    xpToNextTier: rank.xpToNext,
    progress: rank.progress,
  };
}

function RankBadge({ rank }: { rank: RankMeta }) {
  const suffix = rank.tier.key;
  const ringId = `rank-ring-${suffix}`;
  const wingId = `rank-wing-${suffix}`;
  const shieldId = `rank-shield-${suffix}`;
  const gemId = `rank-gem-${suffix}`;
  const ribbonId = `rank-ribbon-${suffix}`;
  const crownId = `rank-crown-${suffix}`;
  const circumference = 2 * Math.PI * 45;
  const progressOffset = circumference * (1 - rank.progress);

  return (
    <div className="relative h-[96px] w-[96px]">
      <svg className="h-full w-full overflow-visible" viewBox="0 0 100 100" aria-hidden="true">
        <defs>
          <linearGradient id={ringId} x1="10%" y1="10%" x2="90%" y2="90%">
            <stop offset="0%" stopColor={rank.tier.accentSoft} />
            <stop offset="100%" stopColor={rank.tier.accent} />
          </linearGradient>
          <linearGradient id={wingId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={rank.tier.metal} />
            <stop offset="100%" stopColor={rank.tier.accentDeep} />
          </linearGradient>
          <linearGradient id={shieldId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={rank.tier.accentSoft} />
            <stop offset="55%" stopColor={rank.tier.accent} />
            <stop offset="100%" stopColor={rank.tier.accentDeep} />
          </linearGradient>
          <linearGradient id={gemId} x1="50%" y1="0%" x2="50%" y2="100%">
            <stop offset="0%" stopColor="#FFFFFF" />
            <stop offset="30%" stopColor={rank.tier.accentSoft} />
            <stop offset="100%" stopColor={rank.tier.accent} />
          </linearGradient>
          <linearGradient id={ribbonId} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={rank.tier.ribbon} />
            <stop offset="50%" stopColor={rank.tier.accentDeep} />
            <stop offset="100%" stopColor={rank.tier.ribbon} />
          </linearGradient>
          <linearGradient id={crownId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#FFF5D7" />
            <stop offset="100%" stopColor={rank.tier.metal} />
          </linearGradient>
        </defs>

        <circle cx="50" cy="50" r="46" fill={rank.tier.glow} opacity="0.62" />
        <circle cx="50" cy="50" r="45" fill="none" stroke="#EEF2FF" strokeWidth="2.6" />
        <circle
          cx="50"
          cy="50"
          r="45"
          fill="none"
          stroke={`url(#${ringId})`}
          strokeWidth="4"
          strokeDasharray={circumference}
          strokeDashoffset={progressOffset}
          strokeLinecap="round"
          className="transition-all duration-1000 ease-out"
          transform="rotate(-90 50 50)"
        />

        <path d="M31 44 C21 39, 12 41, 7 49 C14 52, 18 56, 21 63 C26 58, 31 55, 37 54 L35 47 Z" fill={`url(#${wingId})`} opacity="0.88" />
        <path d="M69 44 C79 39, 88 41, 93 49 C86 52, 82 56, 79 63 C74 58, 69 55, 63 54 L65 47 Z" fill={`url(#${wingId})`} opacity="0.88" />

        <path d="M50 16 L67 25 L71 47 L50 74 L29 47 L33 25 Z" fill={`url(#${shieldId})`} stroke={rank.tier.metal} strokeWidth="1.6" />
        <path d="M38 21 L43 31 L50 25 L57 31 L62 21 L60 35 L40 35 Z" fill={`url(#${crownId})`} stroke={rank.tier.accentDeep} strokeWidth="0.8" />
        <polygon points="50,30 61,43 50,57 39,43" fill={`url(#${gemId})`} stroke="#FFFFFF" strokeOpacity="0.7" strokeWidth="1.2" />
        <path d="M44 43 L50 35 L56 43 L50 49 Z" fill={rank.tier.accentDeep} opacity="0.34" />

        <g opacity="0.9">
          <circle cx="35" cy="38" r="2" fill="#FFFFFF" fillOpacity="0.4" />
          <circle cx="65" cy="38" r="2" fill="#FFFFFF" fillOpacity="0.4" />
        </g>

        <rect x="32" y="66" width="36" height="11" rx="5.5" fill={`url(#${ribbonId})`} />
        <text x="50" y="74" textAnchor="middle" fontSize="8.5" fontWeight="700" letterSpacing="1.6" fill="#FFFFFF">
          {rank.divisionLabel || '巅峰'}
        </text>
      </svg>
    </div>
  );
}

function recommendationContentLabel(type: LearningRecommendation['contentType']) {
  if (type === 'method_card') return '方法卡';
  if (type === 'correction_card') return '纠偏卡';
  return '练习卡';
}

function recommendationQuestLabel(recommendation: LearningRecommendation) {
  if (recommendation.priority === 'high') return '推荐修炼';
  if (recommendation.contentType === 'correction_card') return '纠偏练习';
  if (recommendation.contentType === 'method_card') return '方法进阶';
  return '日常进阶';
}

function recommendationXpReward(recommendation: LearningRecommendation) {
  if (recommendation.contentType === 'correction_card') return 18;
  if (recommendation.contentType === 'method_card') return 20;
  return recommendation.priority === 'high' ? 28 : 24;
}

function entryTypeLabel(xpType: string) {
  if (xpType === 'codification') return '经验沉淀';
  if (xpType === 'reuse') return '方法复用';
  if (xpType === 'improvement') return '成长改进';
  return '复盘反思';
}

function contextTabLabel(tab?: string | null) {
  if (tab === 'tasks') return '任务与日历';
  if (tab === 'client_workspace') return '客户工作台';
  if (tab === 'strategic_accompaniment') return '战略陪伴';
  if (tab === 'growth_handbook' || tab === 'growth') return '成长手册';
  return '相关模块';
}

function ComposerModal({
  open,
  draft,
  setDraft,
  sourceOptions,
  saving,
  onClose,
  onSave,
}: {
  open: boolean;
  draft: DraftState;
  setDraft: React.Dispatch<React.SetStateAction<DraftState>>;
  sourceOptions: Array<{ value: string; label: string; helper: string }>;
  saving: boolean;
  onClose: () => void;
  onSave: () => Promise<void>;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/30 px-4 backdrop-blur-sm">
      <div
        className="w-full max-w-[720px] rounded-[28px] border border-white/70 bg-white p-6 shadow-[0_24px_80px_rgba(15,23,42,0.18)]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start gap-4">
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 text-slate-400 transition-colors hover:bg-slate-50 hover:text-slate-600"
            aria-label="关闭新增沉淀"
          >
            <X className="h-4 w-4" />
          </button>
          <div className="flex-1">
            <p className="text-[11px] font-medium uppercase tracking-[0.24em] text-slate-400">新增沉淀</p>
            <h3 className="mt-2 text-[24px] font-semibold tracking-tight text-slate-900">记录一条能复用的经验</h3>
            <p className="mt-2 text-[13px] leading-6 text-slate-500">
              把结论、适用场景、为什么成立，以及以后如何复用一起写清楚。
            </p>
          </div>
        </div>

        <div className="mt-6 grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-4">
            <label className="block">
              <span className="mb-2 block text-[12px] font-semibold uppercase tracking-[0.18em] text-slate-400">标题</span>
              <input
                value={draft.title}
                onChange={(event) => setDraft((prev) => ({ ...prev, title: event.target.value }))}
                placeholder="这次沉淀要记住什么？"
                className="w-full rounded-[18px] border border-slate-200 bg-slate-50 px-4 py-3 text-[14px] font-medium text-slate-700 outline-none transition-colors placeholder:text-slate-400 focus:border-[#5B7BFE]/40 focus:bg-white"
              />
            </label>
            <label className="block">
              <span className="mb-2 block text-[12px] font-semibold uppercase tracking-[0.18em] text-slate-400">摘要</span>
              <textarea
                value={draft.summary}
                onChange={(event) => setDraft((prev) => ({ ...prev, summary: event.target.value }))}
                placeholder="把结论、适用场景、为什么成立，以及以后怎么复用写清楚。"
                className="min-h-[220px] w-full rounded-[22px] border border-slate-200 bg-slate-50 px-4 py-4 text-[14px] leading-7 text-slate-700 outline-none transition-colors placeholder:text-slate-400 focus:border-[#5B7BFE]/40 focus:bg-white"
              />
            </label>
            <label className="block">
              <span className="mb-2 block text-[12px] font-semibold uppercase tracking-[0.18em] text-slate-400">标签</span>
              <input
                value={draft.tags}
                onChange={(event) => setDraft((prev) => ({ ...prev, tags: event.target.value }))}
                placeholder="标签，多个用逗号分隔"
                className="w-full rounded-[18px] border border-slate-200 bg-slate-50 px-4 py-3 text-[14px] font-medium text-slate-700 outline-none transition-colors placeholder:text-slate-400 focus:border-[#5B7BFE]/40 focus:bg-white"
              />
            </label>
          </div>

          <div className="space-y-3">
            <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-slate-400">来源归类</p>
            {sourceOptions.map((option) => {
              const active = option.value === draft.sourceType;
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setDraft((prev) => ({ ...prev, sourceType: option.value }))}
                  className={cx(
                    'w-full rounded-[20px] border px-4 py-4 text-left transition-colors',
                    active ? 'border-[#8EB3FF] bg-[#EEF4FF]' : 'border-slate-200 bg-white hover:border-slate-300',
                  )}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-[14px] font-semibold text-slate-800">{option.label}</div>
                      <div className="mt-1 text-[12px] leading-5 text-slate-500">{option.helper}</div>
                    </div>
                    <div className={cx('h-5 w-5 rounded-full border', active ? 'border-[#335CFF] bg-white' : 'border-slate-300')}>
                      <div className={cx('m-[3px] h-2.5 w-2.5 rounded-full', active ? 'bg-[#335CFF]' : 'bg-transparent')} />
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="mt-6 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-slate-200 bg-white px-4 py-2 text-[13px] font-medium text-slate-600 transition-colors hover:bg-slate-50"
          >
            取消
          </button>
          <button
            type="button"
            onClick={() => void onSave()}
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-full bg-[#335CFF] px-4 py-2 text-[13px] font-medium text-white transition-colors hover:bg-[#2C50E0] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <PlusCircle className="h-4 w-4" />
            {saving ? '保存中...' : '写入成长手册'}
          </button>
        </div>
      </div>
    </div>
  );
}

export function GrowthHandbookView({
  entries,
  settings,
  currentClientId,
  tasks = [],
  onCreateEntry,
  onTasksReload,
  onNavigate,
  onOpenContext,
  flash,
}: GrowthHandbookViewProps) {
  const [activeTab, setActiveTab] = useState<GrowthHandbookTab>('overview');
  const defaultTagsText = useMemo(() => settings.defaultTags.join(', '), [settings.defaultTags]);
  const sourceOptions = useMemo(
    () => [
      { value: 'manual', label: '手动沉淀', helper: '自己整理经验、判断或结论' },
      { value: 'meeting', label: '会议结论', helper: '把会议共识和行动准则沉淀下来' },
      { value: 'topic_candidate', label: '情报候选', helper: '记录情报站里的观察与启发' },
      ...(settings.allowTaskSource ? [{ value: 'task', label: '任务复盘', helper: '补写任务推进中的方法和复盘' }] : []),
      ...(settings.allowAnalysisSource ? [{ value: 'analysis', label: '分析学习', helper: '承接测试工作台里的学习点' }] : []),
    ],
    [settings.allowAnalysisSource, settings.allowTaskSource],
  );
  const [draft, setDraft] = useState<DraftState>(() => buildDraft(defaultTagsText, sourceOptions[0]?.value || 'manual'));
  const [isComposerOpen, setIsComposerOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [composerCaptureId, setComposerCaptureId] = useState<string | null>(null);
  const growthState = useGrowthOverviewState();
  const [fallbackGrowthOverview, setFallbackGrowthOverview] = useState<GrowthOverview | null>(null);
  const [fallbackGrowthLoading, setFallbackGrowthLoading] = useState(false);
  const [schedulingRecommendationId, setSchedulingRecommendationId] = useState<string | null>(null);
  const [dismissingRecommendationId, setDismissingRecommendationId] = useState<string | null>(null);
  const [updatingCaptureId, setUpdatingCaptureId] = useState<string | null>(null);
  const [isAssetDrawerOpen, setIsAssetDrawerOpen] = useState(false);
  const [isLedgerDrawerOpen, setIsLedgerDrawerOpen] = useState(false);
  const [ledgerAbilityFocus, setLedgerAbilityFocus] = useState<GrowthAbilityKey | null>(null);
  const [learningWorkbenchSnapshot, setLearningWorkbenchSnapshot] = useState<GrowthWorkbenchSnapshot | null>(null);
  const growthOverview = growthState?.growthOverview ?? fallbackGrowthOverview;
  const isGrowthLoading = growthState?.isGrowthLoading ?? fallbackGrowthLoading;

  const loadGrowthState = async () => {
    try {
      if (growthState) {
        await Promise.all([
          growthState.refreshGrowthOverview(),
          getGrowthWorkbench()
            .then((snapshot) => setLearningWorkbenchSnapshot(snapshot))
            .catch(() => undefined),
        ]);
        return;
      }
      setFallbackGrowthLoading(true);
      const [response, snapshot] = await Promise.all([
        getGrowthOverview(),
        getGrowthWorkbench().catch(() => null),
      ]);
      setFallbackGrowthOverview(response);
      setLearningWorkbenchSnapshot(snapshot);
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '成长数据加载失败');
    } finally {
      if (!growthState) {
        setFallbackGrowthLoading(false);
      }
    }
  };

  useEffect(() => {
    setDraft((prev) => {
      if (prev.title.trim() || prev.summary.trim()) return prev;
      return buildDraft(defaultTagsText, sourceOptions[0]?.value || 'manual');
    });
  }, [defaultTagsText, sourceOptions]);

  useEffect(() => {
    if (!growthState) {
      void loadGrowthState();
    }
  }, [growthState]);

  useEffect(() => {
    if (sourceOptions.some((option) => option.value === draft.sourceType)) return;
    setDraft((prev) => ({ ...prev, sourceType: sourceOptions[0]?.value || 'manual' }));
  }, [draft.sourceType, sourceOptions]);

  const experienceCards = useMemo<ExperienceCard[]>(() => {
    return [...entries]
      .sort((left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime())
      .map((entry) => ({
        id: entry.id,
        title: entry.title,
        summary: entry.summary,
        source: getSourceLabel(entry.sourceType),
        tags: entry.tags.length ? entry.tags : ['未分类'],
        xp: getSourceXp(entry.sourceType),
        dateLabel: formatRelativeDate(entry.createdAt),
        type: getTypeLabel(entry.sourceType),
        isMethod: isMethodEntry(entry),
      }));
  }, [entries]);

  const dailyDrops = useMemo<DailyDrop[]>(() => {
    if (growthOverview?.recentEntries.length) {
      const grouped = new Map<string, DailyDrop>();
      growthOverview.recentEntries.forEach((entry) => {
        const key = [
          entry.sourceType,
          entry.sourceId || '',
          entry.taskId || '',
          entry.reviewId || '',
          entry.meetingId || '',
          entry.handbookEntryId || '',
          entry.createdAt,
        ].join('|');
        const existing = grouped.get(key);
        if (existing) {
          existing.xp += entry.totalXp || entry.delta;
          existing.baseXp = (existing.baseXp || 0) + (entry.baseXp || 0);
          existing.premiumXp = (existing.premiumXp || 0) + (entry.premiumXp || 0);
          existing.isSpecial = existing.isSpecial || entry.premiumXp > 0 || entry.xpType !== 'reflection' || entry.delta >= 14;
          existing.entryCount += 1;
          if (entry.abilityLabel && !existing.abilityLabels.includes(entry.abilityLabel)) {
            existing.abilityLabels.push(entry.abilityLabel);
          }
          return;
        }
        grouped.set(key, {
          id: key,
          task: entry.sourceTitle || entry.reason || entry.abilityLabel,
          time: formatRelativeMoment(entry.createdAt),
          createdAt: entry.createdAt,
          xp: entry.totalXp || entry.delta,
          baseXp: entry.baseXp,
          premiumXp: entry.premiumXp,
          premiumRate: entry.premiumRate,
          type: entryTypeLabel(entry.xpType),
          isSpecial: entry.premiumXp > 0 || entry.xpType !== 'reflection' || entry.delta >= 14,
          abilityLabels: entry.abilityLabel ? [entry.abilityLabel] : [],
          entryCount: 1,
        });
      });
      return [...grouped.values()]
        .sort((left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime())
        .slice(0, 5);
    }
    return [];
  }, [entries, growthOverview]);

  const weeklyXp = useMemo(() => {
    if (growthOverview) return growthOverview.weeklyXp;
    if (!entries.length) return 0;
    return entries.reduce((sum, entry) => {
      const ageMs = Date.now() - new Date(entry.createdAt).getTime();
      if (Number.isNaN(ageMs) || ageMs > 7 * 24 * 60 * 60 * 1000) return sum;
      return sum + getSourceXp(entry.sourceType);
    }, 0);
  }, [entries, growthOverview]);
  const abilityCards = useMemo<AbilityCard[]>(() => {
    if (growthOverview?.abilities.length) {
      const gapMap = new Map(growthOverview.abilityGaps.map((gap) => [gap.abilityKey, gap]));
      return growthOverview.abilities.map((ability) => {
        const visual = ABILITY_VISUALS[ability.abilityKey] || ABILITY_VISUALS.exec;
        const gap = gapMap.get(ability.abilityKey);
        return {
          id: ability.abilityKey,
          name: ability.label,
          currentScore: ability.currentScore,
          previousScore: ability.previousScore,
          requiredScore: gap?.requiredScore ?? ability.currentScore,
          stage: ability.stage,
          nextStage: ability.nextStage,
          icon: visual.icon,
          iconClassName: visual.iconClassName,
          bgClassName: visual.bgClassName,
          numericInc: ability.weeklyXp,
          evidence: ability.evidence,
          gapReason: gap?.reason,
          gapSourceLabel: gap?.sourceLabel,
          gapSourceType: gap?.sourceType,
          gapSourceId: gap?.sourceId,
        };
      });
    }
    return [];
  }, [growthOverview]);

  const learningCards = useMemo<LearningCard[]>(() => {
    if (growthOverview?.recommendations.length) {
      return growthOverview.recommendations.map((recommendation) => ({
        id: recommendation.id,
        theme: recommendation.title,
        reason: recommendation.reason || recommendation.summary,
        learnContent: {
          type: recommendationContentLabel(recommendation.contentType),
          title: recommendation.summary || recommendation.abilityLabel,
          icon: ABILITY_VISUALS[recommendation.abilityKey]?.icon || BookOpen,
        },
        practiceTask: recommendation.practiceTask || recommendation.body,
        isUrgent: recommendation.priority === 'high',
        xpReward: recommendationXpReward(recommendation),
        questType: recommendationQuestLabel(recommendation),
        recommendationId: recommendation.id,
        linkedTaskId: recommendation.linkedTaskId,
        clientName: recommendation.clientName,
        eventLineName: recommendation.eventLineName,
        projectStage: recommendation.projectStage,
        triggerNode: recommendation.triggerNode,
        whyNow: recommendation.whyNow,
        linkedContexts: recommendation.linkedContexts,
      }));
    }
    return [];
  }, [growthOverview]);

  const totalScore = useMemo(() => {
    if (growthOverview) return growthOverview.totalXp;
    if (!experienceCards.length) return 0;
    const tagBonus = new Set(experienceCards.flatMap((item) => item.tags)).size * 8;
    return experienceCards.length * 48 + weeklyXp + tagBonus;
  }, [experienceCards, growthOverview, weeklyXp]);
  const rankMeta = useMemo(() => decorateRank(growthOverview?.rank ?? buildFallbackRank(totalScore)), [growthOverview, totalScore]);
  const displayName = growthOverview?.userName?.trim() || '继续沉淀';

  const handleSave = async () => {
    if (!draft.title.trim() || !draft.summary.trim()) {
      flash('error', '请先填写标题和摘要');
      return;
    }
    setIsSaving(true);
    try {
      const createdEntry = await onCreateEntry({
        title: draft.title.trim(),
        summary: draft.summary.trim(),
        tags: parseTags(draft.tags),
        sourceType: draft.sourceType,
        clientId: currentClientId || undefined,
      });
      if (composerCaptureId) {
        await updateGrowthPendingCapture(composerCaptureId, {
          status: 'promoted',
          reason: '已从待放大的成长信号沉淀为经验资产',
          handbookEntryId: createdEntry?.id || null,
        });
      }
      setDraft(buildDraft(defaultTagsText, sourceOptions[0]?.value || 'manual'));
      setComposerCaptureId(null);
      setIsComposerOpen(false);
      setActiveTab('records');
      await loadGrowthState();
      flash('success', '已写入成长手册');
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '保存失败');
    } finally {
      setIsSaving(false);
    }
  };

  const handleScheduleRecommendation = async (recommendationId?: string | null) => {
    if (!recommendationId) {
      flash('success', '练习卡模板已展示，后续可以继续接更细的学习库');
      return;
    }
    setSchedulingRecommendationId(recommendationId);
    try {
      const response = await acceptGrowthRecommendation(recommendationId);
      if (onTasksReload) {
        await onTasksReload();
      }
      await loadGrowthState();
      flash('success', response.task ? `已排入日程：${response.task.title}` : '已排入日程');
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '排入日程失败');
    } finally {
      setSchedulingRecommendationId(null);
    }
  };

  const handleDismissRecommendation = async (recommendationId?: string | null) => {
    if (!recommendationId) {
      flash('success', '当前练习卡没有可忽略的推荐记录');
      return;
    }
    setDismissingRecommendationId(recommendationId);
    try {
      await dismissGrowthRecommendation(recommendationId, { reason: '当前优先处理别的任务，先从学习导航中移除' });
      await loadGrowthState();
      flash('success', '已忽略这条推荐，后续会根据新成长信号重新生成');
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '忽略推荐失败');
    } finally {
      setDismissingRecommendationId(null);
    }
  };

  const openLedgerForAbility = (abilityKey: GrowthAbilityKey) => {
    setLedgerAbilityFocus(abilityKey);
    setIsLedgerDrawerOpen(true);
  };

  const openContextLink = (context?: GrowthContextLink | null) => {
    if (!context) return;
    if (onOpenContext) {
      onOpenContext(context);
      flash('success', `已定位到「${context.label}」`);
      return;
    }
    const targetTab = context.tab === 'growth' ? 'growth_handbook' : context.tab;
    onNavigate?.(targetTab);
    flash('success', `已切到${contextTabLabel(targetTab)}，继续查看「${context.label}」`);
  };

  const openSeededComposer = (seed: { title: string; summary: string; sourceType?: string }) => {
    setDraft({
      title: seed.title,
      summary: seed.summary,
      tags: defaultTagsText,
      sourceType: seed.sourceType && sourceOptions.some((option) => option.value === seed.sourceType)
        ? seed.sourceType
        : settings.allowTaskSource
          ? 'task'
        : sourceOptions[0]?.value || 'manual',
    });
    setIsComposerOpen(true);
    flash('success', `已带着「${seed.title}」打开成长沉淀`);
  };

  const openBlankComposer = () => {
    setComposerCaptureId(null);
    setIsComposerOpen(true);
  };

  const openCaptureAsEntry = (capture: GrowthPendingCapture) => {
    setComposerCaptureId(capture.id);
    openSeededComposer({
      title: capture.title,
      summary: capture.summary || capture.nextActionText || '',
      sourceType: settings.allowTaskSource ? 'task' : sourceOptions[0]?.value || 'manual',
    });
  };

  const handleCaptureState = async (capture: GrowthPendingCapture, status: 'dismissed' | 'reviewed') => {
    setUpdatingCaptureId(capture.id);
    try {
      await updateGrowthPendingCapture(capture.id, {
        status,
        reason: status === 'dismissed' ? '当前先不放大这条成长信号' : '已经查看过这条成长信号，先标记为已处理',
      });
      await loadGrowthState();
      flash('success', status === 'dismissed' ? '已从待处理列表中移除这条成长信号' : '已标记为已处理');
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '更新成长信号状态失败');
    } finally {
      setUpdatingCaptureId(null);
    }
  };

  const openCaptureReview = (capture: GrowthPendingCapture) => {
    const reviewContext = capture.linkedContexts.find((context) => context.objectType === 'review');
    const taskContext = capture.linkedContexts.find((context) => context.objectType === 'task');
    if (reviewContext) {
      openContextLink(reviewContext);
      return;
    }
    if (taskContext) {
      openContextLink(taskContext);
      flash('success', '已回到任务，可继续补周复盘或闭环说明');
      return;
    }
    onNavigate?.('tasks');
    flash('success', '已切到任务与日程，可继续补周复盘');
  };

  const pendingCaptureActions = (capture: GrowthPendingCapture) => {
    const isUpdating = updatingCaptureId === capture.id;
    const actions: Array<{ key: string; label: string; onClick: () => void; disabled?: boolean }> = [];
    const primaryContext = capture.linkedContexts.find((context) => ['task', 'event_line', 'project_flow', 'project_module', 'meeting', 'client'].includes(context.objectType));
    if (primaryContext) {
      actions.push({
        key: 'source',
        label: '回到源对象',
        onClick: () => openContextLink(primaryContext),
        disabled: isUpdating,
      });
    }
    if (capture.missingReasons.some((reason) => reason.includes('复盘') || reason.includes('解释'))) {
      actions.push({
        key: 'review',
        label: '去补复盘',
        onClick: () => openCaptureReview(capture),
        disabled: isUpdating,
      });
    }
    if (capture.missingReasons.some((reason) => reason.includes('沉淀')) || capture.sourceType === 'task_context_candidate' || capture.sourceType === 'task_attachment_candidate') {
      actions.push({
        key: 'handbook',
        label: '沉淀为经验',
        onClick: () => openCaptureAsEntry(capture),
        disabled: isUpdating,
      });
    }
    actions.push({
      key: 'reviewed',
      label: isUpdating ? '处理中...' : '标记已处理',
      onClick: () => void handleCaptureState(capture, 'reviewed'),
      disabled: isUpdating,
    });
    actions.push({
      key: 'dismiss',
      label: isUpdating ? '处理中...' : '先不提醒',
      onClick: () => void handleCaptureState(capture, 'dismissed'),
      disabled: isUpdating,
    });
    if (!actions.length) {
      actions.push({
        key: 'default',
        label: '继续补动作',
        onClick: () => openCaptureReview(capture),
        disabled: isUpdating,
      });
    }
    return actions;
  };

  const growthHighlights = useMemo<GrowthProjectHighlight[]>(
    () => [...(growthOverview?.projectGrowthHighlights || []), ...(growthOverview?.eventLineGrowthHighlights || []), ...(growthOverview?.strategicAlignmentHighlights || [])],
    [growthOverview],
  );

  const topAbilityGaps = useMemo<GrowthAbilityGap[]>(() => (growthOverview?.abilityGaps || []).slice(0, 3), [growthOverview]);
  const pendingCaptures = useMemo<GrowthPendingCapture[]>(() => growthOverview?.pendingCaptures || [], [growthOverview]);
  const currentFocusActions = useMemo<GrowthFocusAction[]>(() => growthOverview?.currentFocusActions || [], [growthOverview]);

  const TabItem = ({ label, id }: { label: string; id: GrowthHandbookTab }) => {
    const isActive = activeTab === id;
    return (
      <button
        type="button"
        onClick={() => setActiveTab(id)}
        className={cx(
          'rounded-2xl px-4 py-1.5 text-[13px] font-medium transition-colors',
          isActive ? 'bg-white text-[#5B7BFE] shadow-sm' : 'text-gray-500 hover:text-gray-700',
        )}
      >
        {label}
      </button>
    );
  };

  const OverviewView = () => (
    <div className="animate-in space-y-6 fade-in duration-300">
      <div className="flex flex-col items-center justify-between gap-6 rounded-[24px] border border-gray-100 bg-white p-6 shadow-sm lg:flex-row lg:p-8">
        <div className="flex items-center space-x-6">
          <RankBadge rank={rankMeta} />

          <div className="space-y-2">
            <h1 className="flex items-center text-[20px] font-semibold tracking-tight text-gray-800 lg:text-[22px]">
              下午好，{displayName}
              <span
                className="ml-3 rounded-full px-2.5 py-0.5 text-[10px] font-medium uppercase tracking-widest"
                style={{ backgroundColor: `${rankMeta.tier.accent}1A`, color: rankMeta.tier.accentDeep }}
              >
                {rankMeta.fullLabel}
              </span>
            </h1>
            <p className="text-[13px] font-medium leading-5 text-gray-500">
              成长手册 · 当前总经验 <span className="font-semibold text-gray-700">{totalScore} XP</span>
              {rankMeta.nextLabel ? (
                <>
                  ，距离 <span className="font-semibold text-gray-700">{rankMeta.nextLabel}</span> 还需{' '}
                  <span className="font-semibold text-gray-700">{rankMeta.xpToNextTier} XP</span>
                </>
              ) : (
                <>，已进入最高段位序列</>
              )}
            </p>
            <div className="flex items-center space-x-2 pt-1.5">
              <span className="flex items-center rounded-full border border-orange-100/50 bg-orange-50 px-2 py-0.5 text-[11px] font-medium tracking-wide text-orange-600">
                <Flame className="mr-1 h-3 w-3" /> 连续 {Math.max(1, Math.min(6, experienceCards.length))} 周沉淀
              </span>
              <span className="flex items-center rounded-full bg-[#5B7BFE]/10 px-2 py-0.5 text-[11px] font-medium tracking-wide text-[#5B7BFE]">
                <Sparkles className="mr-1 h-3 w-3" /> 本周总增量 {weeklyXp} XP
              </span>
              <span
                className="flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium tracking-wide"
                style={{ backgroundColor: `${rankMeta.tier.accent}14`, color: rankMeta.tier.accentDeep }}
              >
                段位进度 {Math.round(rankMeta.progress * 100)}%
              </span>
            </div>
          </div>
        </div>

        <div className="flex w-full pr-4 md:w-auto">
          <div className="flex min-w-[80px] flex-col justify-center">
            <div className="text-[26px] font-semibold leading-none tracking-tighter text-gray-800 lg:text-[32px]">+{weeklyXp}</div>
            <div className="mt-2 text-[11px] font-medium uppercase tracking-widest text-gray-400">本周增量</div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <div className="space-y-3">
            <div className="flex items-end justify-between px-1 pb-1">
              <h2 className="text-[16px] font-semibold text-gray-800">近期心得与复盘</h2>
              <span className="text-[11px] font-medium tracking-wider text-gray-400">完成任务不加 XP，沉淀才加</span>
            </div>

            {dailyDrops.length ? (
              <div className="overflow-hidden rounded-[24px] border border-gray-100 bg-white py-1 shadow-sm">
                {dailyDrops.map((drop, index) => (
                  <div
                    key={drop.id}
                    className={cx(
                      'flex items-center justify-between px-6 py-4 transition-colors hover:bg-gray-50/50',
                      index !== dailyDrops.length - 1 && 'border-b border-gray-50',
                    )}
                  >
                    <div className="flex min-w-0 items-center space-x-4">
                      <div className="min-w-0">
                        <div className="truncate text-[13px] font-medium leading-5 text-gray-700">{drop.task}</div>
                        {drop.abilityLabels.length > 1 ? (
                          <div className="mt-1 text-[10px] font-medium tracking-wide text-gray-400">
                            {drop.abilityLabels.join(' / ')}
                          </div>
                        ) : null}
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <span
                          className={cx(
                            'rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider',
                            drop.isSpecial ? 'bg-orange-50 text-orange-600' : 'bg-gray-100 text-gray-500',
                          )}
                        >
                          {drop.type}
                        </span>
                        {drop.entryCount > 1 ? (
                          <span className="rounded-full bg-[#EEF3FF] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-[#335CFE]">
                            {drop.entryCount} 项能力
                          </span>
                        ) : null}
                      </div>
                    </div>
                    <div className="flex items-center space-x-4">
                      <span className="text-[11px] font-medium text-gray-400">{drop.time}</span>
                      <div className="text-right">
                        <div className={cx('text-[13px] font-semibold tracking-tight', drop.isSpecial ? 'text-orange-600' : 'text-[#5B7BFE]')}>
                          +{drop.xp} XP
                        </div>
                        {drop.premiumXp ? (
                          <div className="text-[10px] font-medium tracking-wide text-gray-400">
                            基础 +{drop.baseXp || Math.max(0, drop.xp - drop.premiumXp)} / 溢价 +{drop.premiumXp}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-[24px] border border-dashed border-gray-200 bg-white px-5 py-10 text-center">
                <div className="mx-auto mb-3 w-10 h-10 rounded-full bg-indigo-50 flex items-center justify-center">
                  <BookOpen className="w-5 h-5 text-indigo-500" />
                </div>
                <p className="text-[14px] font-bold text-gray-600 mb-1">成长账本还是空的</p>
                <p className="text-[13px] text-gray-400 max-w-md mx-auto">完成一条任务并写下复盘心得，或者在周复盘中留下反思，系统就会自动生成第一条成长记录。</p>
              </div>
            )}
          </div>

          <div className="space-y-3">
            <div className="flex items-end justify-between px-1 pb-1">
              <h2 className="text-[16px] font-semibold text-gray-800">成长呼应关系</h2>
              <span className="text-[11px] font-medium tracking-wider text-gray-400">任务 / 会议 / 项目 / 战略正在如何带动成长</span>
            </div>
            {growthHighlights.length ? (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                {growthHighlights.slice(0, 4).map((highlight) => (
                  <div key={`${highlight.type}-${highlight.id}`} className="rounded-[24px] border border-gray-100 bg-white p-5 shadow-sm">
                    <div className="flex items-center justify-between gap-3">
                      <span className="rounded-full bg-[#EEF3FF] px-2 py-0.5 text-[10px] font-medium uppercase tracking-widest text-[#335CFE]">{highlight.type}</span>
                      <span className="text-[13px] font-semibold tracking-tight text-[#335CFE]">+{highlight.weeklyXp} XP</span>
                    </div>
                    <h3 className="mt-3 text-[15px] font-semibold text-slate-900">{highlight.label}</h3>
                    <p className="mt-2 text-[12px] leading-6 text-slate-500">{highlight.summary}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {highlight.abilityKeys.map((abilityKey) => (
                        <span key={`${highlight.id}-${abilityKey}`} className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.18em] text-slate-500">
                          {abilityKey}
                        </span>
                      ))}
                    </div>
                    {highlight.contexts.length ? (
                      <div className="mt-4 flex flex-wrap gap-2">
                        {highlight.contexts.slice(0, 3).map((context) => (
                          <button
                            key={`${highlight.id}-${context.objectType}-${context.objectId}`}
                            type="button"
                            onClick={() => openContextLink(context)}
                            className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-medium text-slate-600 transition hover:border-[#C9D7FF] hover:text-[#335CFE]"
                          >
                            {context.label}
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-[24px] border border-dashed border-gray-200 bg-white px-5 py-10 text-center">
                <div className="mx-auto mb-3 w-10 h-10 rounded-full bg-purple-50 flex items-center justify-center">
                  <GitMerge className="w-5 h-5 text-purple-500" />
                </div>
                <p className="text-[14px] font-bold text-gray-600 mb-1">还没有形成成长呼应</p>
                <p className="text-[13px] text-gray-400 max-w-md mx-auto">当你的任务、会议和事件线开始联动时，系统会自动识别哪些行动带来了真实成长，并在这里展示呼应关系。</p>
              </div>
            )}
          </div>

          <div className="space-y-3">
            <div className="flex items-end justify-between px-1 pb-1">
              <h2 className="text-[16px] font-semibold text-gray-800">本周成长来自哪里</h2>
              <span className="text-[11px] font-medium tracking-wider text-gray-400">按模块、客户与事件线聚合</span>
            </div>
            {growthOverview ? (
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                {[
                  { label: '任务信号', value: growthOverview.sourceCoverage.taskSignals },
                  { label: '会议信号', value: growthOverview.sourceCoverage.meetingSignals },
                  { label: '战略信号', value: growthOverview.sourceCoverage.strategicSignals },
                  { label: '周判断', value: growthOverview.sourceCoverage.reviewSignals },
                  { label: '手册信号', value: growthOverview.sourceCoverage.handbookSignals },
                  { label: '涉及客户', value: growthOverview.sourceCoverage.clientCount },
                  { label: '事件线', value: growthOverview.sourceCoverage.eventLineCount },
                  { label: '推荐动作', value: currentFocusActions.length },
                ].map((item) => (
                  <div key={item.label} className="rounded-[22px] border border-gray-100 bg-white p-4 shadow-sm">
                    <div className="text-[12px] font-medium text-gray-400">{item.label}</div>
                    <div className="mt-2 text-[24px] font-semibold tracking-tight text-slate-900">{item.value}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-[24px] border border-dashed border-gray-200 bg-white px-5 py-10 text-center">
                <p className="text-[14px] font-bold text-gray-600 mb-1">成长来源数据待积累</p>
                <p className="text-[13px] text-gray-400 max-w-md mx-auto">随着你完成任务、参加会议和提交复盘，这里会按来源分类展示你的成长信号分布。</p>
              </div>
            )}
          </div>

          <div className="space-y-3">
            <div className="flex items-end justify-between px-1 pb-1">
              <h2 className="text-[16px] font-semibold text-gray-800">系统已看到但还没放大的成长</h2>
              <span className="text-[11px] font-medium tracking-wider text-gray-400">缺资料 / 缺闭环 / 缺复盘时会先停在这里</span>
            </div>
            {pendingCaptures.length ? (
              <div className="space-y-3">
                {pendingCaptures.slice(0, 4).map((capture) => (
                  <div key={capture.id} className="rounded-[24px] border border-gray-100 bg-white p-5 shadow-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-orange-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-widest text-orange-600">{capture.sourceType}</span>
                      {capture.clientName ? <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium uppercase tracking-widest text-slate-500">{capture.clientName}</span> : null}
                      {capture.eventLineName ? <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium uppercase tracking-widest text-slate-500">{capture.eventLineName}</span> : null}
                    </div>
                    <h3 className="mt-3 text-[15px] font-semibold text-slate-900">{capture.title}</h3>
                    <p className="mt-2 text-[12px] leading-6 text-slate-500">{capture.summary}</p>
                    <div className="mt-3 rounded-2xl bg-slate-50 px-3 py-3 text-[12px] leading-6 text-slate-600">{capture.nextActionText}</div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {capture.missingReasons.map((reason) => (
                        <span key={`${capture.id}-${reason}`} className="rounded-full border border-orange-100 bg-orange-50 px-2.5 py-1 text-[11px] font-medium text-orange-700">
                          {reason}
                        </span>
                      ))}
                    </div>
                    {capture.linkedContexts.length ? (
                      <div className="mt-4 flex flex-wrap gap-2">
                        {capture.linkedContexts.map((context) => (
                          <button
                            key={`${capture.id}-${context.objectType}-${context.objectId}`}
                            type="button"
                            onClick={() => openContextLink(context)}
                            className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-medium text-slate-600 transition hover:border-[#C9D7FF] hover:text-[#335CFE]"
                          >
                            {context.label}
                          </button>
                        ))}
                      </div>
                    ) : null}
                    <div className="mt-4 flex flex-wrap gap-2">
                      {pendingCaptureActions(capture).map((action) => (
                        <button
                          key={`${capture.id}-${action.key}`}
                          type="button"
                          onClick={action.onClick}
                          disabled={action.disabled}
                          className={cx(
                            'rounded-full px-3 py-1.5 text-[11px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60',
                            action.key === 'handbook'
                              ? 'bg-[#335CFE] text-white hover:bg-[#2746C7]'
                              : 'border border-slate-200 bg-white text-slate-600 hover:border-[#C9D7FF] hover:text-[#335CFE]',
                          )}
                        >
                          {action.label}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-[24px] border border-dashed border-gray-200 bg-white px-5 py-10 text-center">
                <p className="text-[14px] font-bold text-gray-600 mb-1">暂无待放大的信号</p>
                <p className="text-[13px] text-gray-400 max-w-md mx-auto">当系统检测到你的某些行动有成长潜力但还缺少闭环时，会在这里提醒你补充。</p>
              </div>
            )}
          </div>

          <div className="space-y-3">
            <div className="flex items-end justify-between px-1 pb-1">
              <h2 className="text-[16px] font-semibold text-gray-800">下一步最值得补的动作</h2>
              <button type="button" className="text-[12px] font-medium text-[#5B7BFE] transition-colors hover:text-[#335CFF]" onClick={() => setActiveTab('learning')}>
                去学习导航
              </button>
            </div>
            {currentFocusActions.length ? (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                {currentFocusActions.slice(0, 4).map((focus) => (
                  <div key={focus.id} className="group flex flex-col justify-between rounded-[24px] border border-gray-100 bg-white p-5 shadow-sm transition-colors hover:border-[#5B7BFE]/30">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        {focus.clientName ? <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium uppercase tracking-widest text-slate-500">{focus.clientName}</span> : null}
                        {focus.eventLineName ? <span className="rounded-full bg-[#EEF3FF] px-2 py-0.5 text-[10px] font-medium uppercase tracking-widest text-[#335CFE]">{focus.eventLineName}</span> : null}
                        {focus.projectStage ? <span className="rounded-full bg-orange-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-widest text-orange-600">{focus.projectStage}</span> : null}
                      </div>
                      <h3 className="mt-3 text-[14px] font-semibold leading-snug text-gray-800">{focus.title}</h3>
                      <p className="mt-2 text-[12px] leading-6 text-gray-500">{focus.summary}</p>
                      <div className="mt-3 rounded-2xl bg-slate-50 px-3 py-3 text-[12px] leading-6 text-slate-600">{focus.whyNow}</div>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {focus.linkedContexts.length ? (
                        focus.linkedContexts.slice(0, 3).map((context) => (
                          <button
                            key={`${focus.id}-${context.objectType}-${context.objectId}`}
                            type="button"
                            onClick={() => openContextLink(context)}
                            className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-medium text-slate-600 transition hover:border-[#C9D7FF] hover:text-[#335CFE]"
                          >
                            {context.label}
                          </button>
                        ))
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            ) : learningCards.length ? (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                {learningCards.slice(0, 2).map((quest) => (
                  <div key={quest.id} className="rounded-[24px] border border-gray-100 bg-white p-5 shadow-sm">
                    <div className="flex items-center gap-2">
                      <span className={cx('rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-widest', quest.isUrgent ? 'bg-orange-50 text-orange-600' : 'bg-gray-100 text-gray-500')}>
                        {quest.questType}
                      </span>
                    </div>
                    <h3 className="mt-3 text-[14px] font-semibold text-slate-900">{quest.theme}</h3>
                    <p className="mt-2 text-[12px] leading-6 text-slate-500">{quest.whyNow || quest.reason}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-[24px] border border-dashed border-gray-200 bg-white px-5 py-10 text-center">
                <p className="text-[14px] font-bold text-gray-600 mb-1">暂无动作推荐</p>
                <p className="text-[13px] text-gray-400 max-w-md mx-auto">当项目或事件线上出现能力缺口时，系统会在这里推荐最值得补的下一步动作。</p>
              </div>
            )}
          </div>
        </div>

        <div className="space-y-3">
          <div className="flex items-end justify-between px-1 pb-1">
            <h2 className="text-[16px] font-semibold text-gray-800">近期成长最快</h2>
          </div>

          <div className="space-y-6 rounded-[24px] border border-gray-100 bg-white p-6 shadow-sm">
            {[...abilityCards].sort((left, right) => right.numericInc - left.numericInc).slice(0, 4).map((ability) => {
              const AbilityIcon = ability.icon;
              return (
                <div key={ability.id} className="group">
                  <div className="mb-2.5 flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <div className={cx('rounded-lg p-1.5', ability.bgClassName)}>
                        <AbilityIcon className={cx('h-[15px] w-[15px]', ability.iconClassName)} />
                      </div>
                      <span className="text-[13px] font-semibold leading-5 text-gray-800">{ability.name}</span>
                    </div>
                    <span className="text-[13px] font-semibold tracking-tight text-[#5B7BFE]">+{ability.numericInc}</span>
                  </div>

                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-50">
                    <div className="h-full rounded-full bg-[#5B7BFE]" style={{ width: `${ability.currentScore}%` }} />
                  </div>
                  <div className="mt-1.5 flex items-center justify-between">
                    <div className="text-[10px] font-medium uppercase tracking-widest text-gray-400">{ability.stage}期</div>
                    <button
                      type="button"
                      onClick={() => openLedgerForAbility(ability.id as GrowthAbilityKey)}
                      className="text-[11px] font-medium text-[#335CFE] transition-colors hover:text-[#2746C7]"
                    >
                      查看账本
                    </button>
                  </div>
                </div>
              );
            })}
            {!abilityCards.length ? (
              <div className="text-center py-4">
                <p className="text-[13px] font-bold text-gray-500 mb-1">能力雷达待激活</p>
                <p className="text-[12px] text-gray-400">完成任务并写下复盘后，六维能力分布会在这里自动生成。</p>
              </div>
            ) : null}
          </div>

          <div className="space-y-4 rounded-[24px] border border-gray-100 bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-[16px] font-semibold text-gray-800">当前能力差距</h2>
              <span className="text-[11px] font-medium tracking-wider text-gray-400">当前项目 / 事件线要求 vs 我的能力</span>
            </div>
            {topAbilityGaps.length ? (
              topAbilityGaps.map((gap) => (
                <button
                  key={`${gap.sourceType}-${gap.sourceId}-${gap.abilityKey}`}
                  type="button"
                  onClick={() => {
                    if (gap.sourceId && ['task', 'event_line', 'client', 'project_module', 'project_flow', 'strategic_focus', 'meeting'].includes(gap.sourceType)) {
                      openContextLink({
                        objectType: gap.sourceType,
                        objectId: gap.sourceId,
                        label: gap.sourceLabel || gap.label,
                        subtitle: gap.reason,
                        tab: gap.sourceType === 'client' ? 'client_workspace' : gap.sourceType === 'strategic_focus' ? 'strategic_accompaniment' : 'tasks',
                        statusLabel: '能力差距',
                      });
                      return;
                    }
                    openLedgerForAbility(gap.abilityKey);
                  }}
                  className="w-full rounded-[20px] border border-gray-100 bg-slate-50/70 p-4 text-left transition hover:border-[#D4DEFF]"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-[13px] font-semibold text-slate-900">{gap.label}</div>
                      <div className="mt-1 text-[12px] text-slate-500">{gap.sourceLabel}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-[13px] font-semibold text-[#335CFE]">差距 {gap.gap}</div>
                      <div className="text-[10px] uppercase tracking-widest text-slate-400">{gap.currentScore} / {gap.requiredScore}</div>
                    </div>
                  </div>
                  <div className="mt-3 text-[12px] leading-6 text-slate-600">{gap.reason}</div>
                </button>
              ))
            ) : (
              <div className="text-center py-2">
                <p className="text-[13px] font-bold text-gray-500 mb-1">没有明显的能力差距</p>
                <p className="text-[12px] text-gray-400">当前项目和事件线对你的能力要求都在覆盖范围内。</p>
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={() => setActiveTab('map')}
            className="flex w-full items-center justify-center space-x-2 rounded-[24px] border border-gray-100 bg-white p-4 text-[12px] font-medium tracking-wide text-gray-600 shadow-sm transition-colors hover:bg-gray-50"
          >
            <BrainCircuit className="h-4 w-4 text-gray-400" />
            <span>查看完整能力图谱</span>
          </button>
        </div>
      </div>
    </div>
  );

  const MapView = () => {
    const radarSize = 280;
    const center = radarSize / 2;
    const radius = 90;
    const numSides = abilityCards.length;

    const getPolygonPoints = (key: 'currentScore' | 'previousScore' | 'requiredScore') =>
      abilityCards.map((item, index) => {
        const angle = (Math.PI * 2 * index) / numSides - Math.PI / 2;
        const r = (item[key] / 100) * radius;
        return `${center + r * Math.cos(angle)},${center + r * Math.sin(angle)}`;
      }).join(' ');

    const gridLevels = [20, 40, 60, 80, 100];

    return (
      <div className="animate-in flex flex-col gap-6 fade-in duration-300 lg:flex-row">
        <div className="flex flex-col items-center rounded-[24px] border border-gray-100 bg-white p-8 shadow-sm lg:w-1/2">
          <h3 className="mb-6 w-full text-center text-[16px] font-semibold text-gray-800">核心 6 项能力分布</h3>

          <div className="relative flex w-full justify-center">
            <svg width={radarSize} height={radarSize} className="overflow-visible">
              {gridLevels.map((levelValue) => (
                <polygon
                  key={`grid-${levelValue}`}
                  points={abilityCards.map((_, index) => {
                    const angle = (Math.PI * 2 * index) / numSides - Math.PI / 2;
                    const r = (levelValue / 100) * radius;
                    return `${center + r * Math.cos(angle)},${center + r * Math.sin(angle)}`;
                  }).join(' ')}
                  fill="none"
                  stroke="#F3F4F6"
                  strokeWidth="1"
                />
              ))}

              {abilityCards.map((_, index) => {
                const angle = (Math.PI * 2 * index) / numSides - Math.PI / 2;
                return (
                  <line
                    key={`axis-${index}`}
                    x1={center}
                    y1={center}
                    x2={center + radius * Math.cos(angle)}
                    y2={center + radius * Math.sin(angle)}
                    stroke="#F3F4F6"
                    strokeWidth="1"
                  />
                );
              })}

              <polygon points={getPolygonPoints('previousScore')} fill="#9CA3AF" fillOpacity="0.08" stroke="#D1D5DB" strokeWidth="1.5" strokeDasharray="3 3" />
              <polygon points={getPolygonPoints('requiredScore')} fill="#F59E0B" fillOpacity="0.04" stroke="#F59E0B" strokeWidth="1.5" strokeDasharray="6 4" />
              <polygon points={getPolygonPoints('currentScore')} fill="#5B7BFE" fillOpacity="0.1" stroke="#5B7BFE" strokeWidth="2" strokeLinejoin="round" />

              {abilityCards.map((item, index) => {
                const angle = (Math.PI * 2 * index) / numSides - Math.PI / 2;
                const r = (item.currentScore / 100) * radius;
                const cxPoint = center + r * Math.cos(angle);
                const cyPoint = center + r * Math.sin(angle);
                return <circle key={`dot-${item.id}`} cx={cxPoint} cy={cyPoint} r="3.5" fill="#5B7BFE" />;
              })}

              {abilityCards.map((item, index) => {
                const angle = (Math.PI * 2 * index) / numSides - Math.PI / 2;
                const labelRadius = radius + 25;
                const x = center + labelRadius * Math.cos(angle);
                const y = center + labelRadius * Math.sin(angle);
                let textAnchor: 'start' | 'middle' | 'end' = 'middle';
                if (Math.abs(Math.cos(angle)) > 0.1) textAnchor = Math.cos(angle) > 0 ? 'start' : 'end';
                return (
                  <text
                    key={`label-${item.id}`}
                    x={x}
                    y={y + 4}
                    textAnchor={textAnchor}
                    fontSize="11"
                    fill="#6B7280"
                    fontWeight="500"
                    className="uppercase tracking-wide"
                  >
                    {item.name}
                  </text>
                );
              })}
            </svg>
          </div>

          <div className="mt-8 flex flex-wrap items-center gap-5 text-[11px] font-medium uppercase tracking-widest text-gray-400">
            <div className="flex items-center">
              <div className="mr-2 h-2.5 w-2.5 rounded-full bg-[#5B7BFE]" />
              当前水平
            </div>
            <div className="flex items-center">
              <div className="mr-2 h-2.5 w-2.5 rounded-full border border-gray-300 bg-white" />
              30天前
            </div>
            <div className="flex items-center">
              <div className="mr-2 h-2.5 w-2.5 rounded-full bg-amber-400" />
              当前项目要求
            </div>
          </div>
        </div>

        <div className="space-y-4 lg:w-1/2">
          <h2 className="border-b border-gray-100 pb-2 text-[16px] font-semibold text-gray-800">能力明细账</h2>
          <div className="grid grid-cols-1 gap-3">
            {abilityCards.map((ability) => (
              <button
                key={ability.id}
                type="button"
                onClick={() => {
                  if (ability.gapSourceType && ability.gapSourceId && ['task', 'event_line', 'client', 'project_module', 'project_flow', 'strategic_focus', 'meeting'].includes(ability.gapSourceType)) {
                    openContextLink({
                      objectType: ability.gapSourceType,
                      objectId: ability.gapSourceId,
                      label: ability.gapSourceLabel || ability.name,
                      subtitle: ability.gapReason || '',
                      tab: ability.gapSourceType === 'client' ? 'client_workspace' : ability.gapSourceType === 'strategic_focus' ? 'strategic_accompaniment' : 'tasks',
                      statusLabel: '能力差距',
                    });
                    return;
                  }
                  openLedgerForAbility(ability.id as GrowthAbilityKey);
                }}
                className="flex items-center justify-between rounded-[20px] border border-gray-100 bg-white p-4 text-left shadow-sm transition-colors hover:border-gray-200"
              >
                <div>
                  <div className="mb-1 flex items-center space-x-2">
                    <h4 className="text-[13px] font-semibold leading-5 text-gray-800">{ability.name}</h4>
                    <span className="rounded-md border border-gray-100 bg-gray-50 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-widest text-gray-400">
                      {ability.stage}期
                    </span>
                  </div>
                  <div className="text-[11px] font-medium text-gray-400">
                    当前 {ability.currentScore}% · 要求 {ability.requiredScore}%
                  </div>
                  {ability.gapReason ? (
                    <div className="mt-2 text-[11px] leading-5 text-slate-500">{ability.gapReason}</div>
                  ) : null}
                </div>
                <div className="text-right">
                  <div className="text-[13px] font-semibold tracking-tight text-[#5B7BFE]">+{ability.currentScore - ability.previousScore} XP</div>
                  <div className="mt-0.5 text-[10px] font-medium uppercase tracking-widest text-gray-400">
                    {ability.requiredScore > ability.currentScore ? `差距 ${ability.requiredScore - ability.currentScore}` : '已达当前要求'}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="flex h-full min-h-0 flex-col overflow-y-auto bg-[#F9FAFB] text-gray-800">
      <ComposerModal
        open={isComposerOpen}
        draft={draft}
        setDraft={setDraft}
        sourceOptions={sourceOptions}
        saving={isSaving}
        onClose={() => {
          setComposerCaptureId(null);
          setIsComposerOpen(false);
        }}
        onSave={handleSave}
      />

      <GrowthAssetLibraryDrawer
        open={isAssetDrawerOpen}
        entries={entries}
        recentEntries={growthOverview?.recentEntries || []}
        flash={flash}
        onClose={() => setIsAssetDrawerOpen(false)}
        onRefresh={loadGrowthState}
        onOpenComposer={openBlankComposer}
        onNavigate={onNavigate}
        onOpenContext={onOpenContext}
      />

      <GrowthLedgerDrawer
        open={isLedgerDrawerOpen}
        growthOverview={growthOverview || null}
        flash={flash}
        onClose={() => setIsLedgerDrawerOpen(false)}
        initialAbilityKey={ledgerAbilityFocus}
        onOpenContext={onOpenContext}
      />

      <header className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-5 pb-6 pt-6 md:flex-row md:items-center md:justify-between lg:px-8">
        <div className="flex w-full flex-col gap-3 md:flex-row md:items-center md:gap-6">
          <h1 className="text-[20px] font-semibold tracking-tight text-gray-800 lg:text-[22px]">成长手册</h1>

          <nav className="flex max-w-full items-center overflow-x-auto rounded-2xl bg-gray-100/80 p-1">
            <TabItem label="成长总览" id="overview" />
            <TabItem label="成长勋章" id="records" />
            <TabItem label="学习导航" id="learning" />
            <TabItem label="能力图谱" id="map" />
          </nav>
        </div>

        <div className="flex flex-wrap items-center gap-2 md:justify-end">
          <button
            type="button"
            onClick={() => setIsAssetDrawerOpen(true)}
            className="rounded-full border border-slate-200 bg-white px-4 py-2 text-[13px] font-medium text-slate-600 transition-colors hover:bg-slate-50"
          >
            经验资产
          </button>
          <button
            type="button"
            onClick={() => {
              setLedgerAbilityFocus(null);
              setIsLedgerDrawerOpen(true);
            }}
            className="rounded-full border border-slate-200 bg-white px-4 py-2 text-[13px] font-medium text-slate-600 transition-colors hover:bg-slate-50"
          >
            XP账本
          </button>
          <button
            type="button"
            onClick={openBlankComposer}
            className="flex items-center space-x-1.5 rounded-full bg-[#16A34A] px-4 py-2 text-[13px] font-medium text-white shadow-sm transition-colors hover:bg-[#15803D]"
          >
            <PlusCircle className="h-[16px] w-[16px]" />
            <span className="whitespace-nowrap">记录经验</span>
          </button>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col px-5 pb-20 lg:px-8">
        {isGrowthLoading && !growthOverview ? (
          <div className="mb-4 rounded-[20px] border border-[#DCE7FF] bg-white px-4 py-3 text-[12px] font-medium text-[#5B7BFE] shadow-sm">
            成长引擎正在同步最近的复盘、沉淀和推荐练习...
          </div>
        ) : null}
        {activeTab === 'overview' && <OverviewView />}
        {activeTab === 'records' && <GrowthBadgeWall flash={flash} onNavigate={onNavigate} onOpenContext={onOpenContext} />}
        {activeTab === 'learning' && (
          <GrowthLearningWorkbench
            learningCards={learningCards}
            abilityCards={abilityCards}
            dailyDrops={dailyDrops}
            workbenchSnapshot={learningWorkbenchSnapshot}
            currentFocusActions={currentFocusActions}
            pendingCaptures={pendingCaptures}
            tasks={tasks}
            flash={flash}
            onScheduleRecommendation={handleScheduleRecommendation}
            onDismissRecommendation={handleDismissRecommendation}
            schedulingRecommendationId={schedulingRecommendationId}
            dismissingRecommendationId={dismissingRecommendationId}
            onOpenComposer={openBlankComposer}
            onSeedComposer={openSeededComposer}
            onNavigate={onNavigate}
            onOpenContext={onOpenContext}
          />
        )}
        {activeTab === 'map' && <MapView />}
      </main>
    </div>
  );
}

export default GrowthHandbookView;
~~~

## `src/renderer/components/handbook/GrowthLearningWorkbench.tsx`

- 编码: `utf-8`

~~~tsx
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  Bot,
  Briefcase,
  CalendarDays,
  CheckCircle,
  CheckSquare,
  ChevronDown,
  FileText,
  ListTodo,
  MessageSquare,
  ShieldAlert,
  Target,
  Trophy,
  UserCheck,
  Users,
  X,
  Zap,
  type LucideIcon,
} from 'lucide-react';

import type {
  GrowthAfterActionCapture,
  GrowthActionPlanItem,
  GrowthContextLink,
  GrowthFocusAction,
  GrowthGenericLesson,
  GrowthLearningSummary,
  GrowthMaterialRef,
  GrowthPendingCapture,
  GrowthProjectContextPack,
  GrowthProjectGuidance,
  GrowthReasoningTrace,
  GrowthRobotAssist,
  GrowthTaskIntent,
  GrowthUniversalSkillItem,
  GrowthWorkbenchSnapshot,
  Task,
} from '../../../shared/types';

type FlashLevel = 'success' | 'error';

type LearningWorkbenchCard = {
  id: string;
  theme: string;
  reason: string;
  whyNow?: string;
  learnContent: {
    type: string;
    title: string;
    icon: React.ComponentType<{ className?: string }>;
  };
  practiceTask: string;
  isUrgent: boolean;
  xpReward: number;
  questType: string;
  recommendationId?: string | null;
  linkedTaskId?: string | null;
  clientName?: string | null;
  eventLineName?: string | null;
  projectStage?: string | null;
  triggerNode?: string | null;
  linkedContexts?: GrowthContextLink[];
};

type AbilityWorkbenchCard = {
  id: string;
  name: string;
  currentScore: number;
  previousScore: number;
  stage: string;
  numericInc: number;
  evidence: string;
};

type DailyDropCard = {
  id: string;
  task: string;
  time: string;
  xp: number;
  type: string;
  isSpecial: boolean;
};

type GrowthLearningWorkbenchProps = {
  learningCards: LearningWorkbenchCard[];
  abilityCards: AbilityWorkbenchCard[];
  dailyDrops: DailyDropCard[];
  workbenchSnapshot?: GrowthWorkbenchSnapshot | null;
  currentFocusActions?: GrowthFocusAction[];
  pendingCaptures?: GrowthPendingCapture[];
  tasks?: Task[];
  flash: (level: FlashLevel, message: string) => void;
  onScheduleRecommendation: (recommendationId?: string | null) => Promise<void>;
  onDismissRecommendation: (recommendationId?: string | null) => Promise<void>;
  schedulingRecommendationId: string | null;
  dismissingRecommendationId: string | null;
  onOpenComposer: () => void;
  onSeedComposer?: (seed: { title: string; summary: string; sourceType?: string }) => void;
  onNavigate?: (tab: string) => void;
  onOpenContext?: (context: GrowthContextLink) => void;
};

type WorkbenchTask = {
  id: string;
  title: string;
  project: string;
  deadline: string;
  urgency: string;
  urgencyColor: string;
  phase: ProcessStep['name'];
  risks: string[];
  nextAdvice: string;
  robotReady: boolean;
  robotReasons: string[];
  recommendationId?: string | null;
  linkedTaskId?: string | null;
  linkedContexts?: GrowthContextLink[];
  xpReward: number;
  contextSummary?: string;
  projectModuleName?: string | null;
  projectFlowName?: string | null;
  sourceEvidence?: string[];
  currentBlocker?: string | null;
  missingSignals?: string[];
  hasBackground: boolean;
  hasDeadline: boolean;
  isCrossDepartment: boolean;
  needsReview: boolean;
  evidenceCount: number;
  pendingCollaborations: number;
  taskIntent: GrowthTaskIntent;
  universalSkills: GrowthUniversalSkillItem[];
  projectContextPack: GrowthProjectContextPack;
  actionPlan: GrowthActionPlanItem[];
  materialRefs: GrowthMaterialRef[];
};

type WorkbenchAction = {
  id: string;
  title: string;
  output: string;
  scenario: string;
  actionLabel: string;
  supportTitle: string;
  detail?: string;
  context?: GrowthContextLink | null;
  seedTitle?: string;
  seedSummary?: string;
  kind: 'schedule' | 'support' | 'process' | 'compose' | 'task';
  recommendationId?: string | null;
};

type SupportMaterial = {
  id: string;
  title: string;
  type: '流程说明' | '经验案例' | '模板工具';
  scenario: string;
  summary?: string;
  linkedContext?: GrowthContextLink | null;
};

type ProcessStep = {
  id: string;
  name: '需求接收' | '信息核对' | '内部对齐' | '方案产出' | '沟通推进' | '交付闭环' | '复盘沉淀';
  output: string;
  bottlenecks: string[];
};

type ModalType = 'robot' | 'support' | 'process' | null;

const PROCESS_STEPS: ProcessStep[] = [
  { id: 'p1', name: '需求接收', output: '明确需求来源、目标对象和优先级', bottlenecks: ['需求来源模糊', '优先级未经确认'] },
  { id: 'p2', name: '信息核对', output: '确认关键事实、材料和依赖项都已到位', bottlenecks: ['输入材料不完整', '事实口径未统一'] },
  { id: 'p3', name: '内部对齐', output: '明确会议目标、参会人及预期结论', bottlenecks: ['未提前拉齐信息', '会议目标发散'] },
  { id: 'p4', name: '方案产出', output: '形成结构清晰、可执行的初版方案', bottlenecks: ['结构与受众不匹配', '缺少支撑数据'] },
  { id: 'p5', name: '沟通推进', output: '把边界、责任人和时间线谈清楚', bottlenecks: ['临场判断不足', '关键利益方未提前对齐'] },
  { id: 'p6', name: '交付闭环', output: '形成明确交付物、待办与复核节点', bottlenecks: ['只做了动作，没有闭环', '责任人和时间点不明确'] },
  { id: 'p7', name: '复盘沉淀', output: '把本次有效做法转成可复用经验', bottlenecks: ['只记录结果，没有方法', '经验无法迁移复用'] },
];

const PHASE_BY_INDEX: ProcessStep['name'][] = ['需求接收', '信息核对', '内部对齐', '方案产出', '沟通推进', '交付闭环', '复盘沉淀'];

const EMPTY_TASK: WorkbenchTask = {
  id: 'growth-empty-task',
  title: '等待成长上下文接入',
  project: '等待任务、会议或推荐接入',
  deadline: '尚未关联时间点',
  urgency: '等待上下文',
  urgencyColor: 'text-slate-500 bg-slate-100',
  phase: '信息核对',
  risks: ['系统需要真实任务、事件线或成长推荐才能推导具体动作，请先创建一条业务对象。'],
  nextAdvice: '先在任务与日历创建一条任务，或在客户工作台发布会议 / 行动项，任务学习页就会自动补全上下文。',
  robotReady: false,
  robotReasons: ['需要先有真实业务对象和阶段信息，机器人才能判断是否适合接手标准动作。'],
  recommendationId: null,
  linkedTaskId: null,
  linkedContexts: [],
  xpReward: 0,
  contextSummary: '',
  projectModuleName: null,
  projectFlowName: null,
  sourceEvidence: [],
  currentBlocker: null,
  missingSignals: ['缺真实任务', '缺项目上下文'],
  hasBackground: false,
  hasDeadline: false,
  isCrossDepartment: false,
  needsReview: false,
  evidenceCount: 0,
  pendingCollaborations: 0,
  taskIntent: {
    taskKind: 'general_execution',
    goal: '先形成一条真实任务，再进入任务学习页',
    deliverable: '一条带背景和时间点的任务',
    riskTypes: ['fact_gap'],
    requiredAbilities: ['exec', 'collab'],
    confidence: 0.2,
    whyRelevant: '系统需要真实任务对象才能判断更细的技能与项目背景，请先创建任务。',
  },
  universalSkills: [],
  projectContextPack: {
    title: '',
    taskNotes: [],
    attachments: [],
    memoryHints: [],
    linkedFacts: [],
    clientSummary: '',
    recentMeetings: [],
    eventLineSummary: '',
    strategicFocus: [],
    keyWarnings: [],
    contextGaps: ['缺真实任务', '缺项目背景'],
  },
  actionPlan: [],
  materialRefs: [],
};

function cx(...classNames: Array<string | false | null | undefined>) {
  return classNames.filter(Boolean).join(' ');
}

function buildFallbackTaskIntent(taskKind: string, goal: string, deliverable: string, whyRelevant: string, requiredAbilities: GrowthTaskIntent['requiredAbilities']): GrowthTaskIntent {
  return {
    taskKind,
    goal,
    deliverable,
    riskTypes: ['fact_gap', 'boundary_risk'],
    requiredAbilities,
    confidence: 0.52,
    whyRelevant,
  };
}

function buildFallbackProjectContextPack(title: string, summary: string, extras?: Partial<GrowthProjectContextPack>): GrowthProjectContextPack {
  return {
    title,
    taskNotes: summary ? [summary] : [],
    attachments: [],
    memoryHints: [],
    linkedFacts: [],
    clientSummary: '',
    recentMeetings: [],
    eventLineSummary: '',
    strategicFocus: [],
    keyWarnings: [],
    contextGaps: [],
    ...extras,
  };
}

function buildTaskFromLearningCard(card: LearningWorkbenchCard, index: number, ability?: AbilityWorkbenchCard): WorkbenchTask {
  const phase = (PROCESS_STEPS.find((step) => card.projectStage?.includes(step.name) || card.triggerNode?.includes(step.name))?.name || PHASE_BY_INDEX[Math.min(index + 2, PHASE_BY_INDEX.length - 1)]);
  const urgentColor = card.isUrgent ? 'text-red-700 bg-red-100' : index === 1 ? 'text-green-700 bg-green-100' : 'text-orange-700 bg-orange-100';
  const urgency = card.isUrgent ? '建议优先处理' : index === 1 ? '可直接推进' : '需先补关键动作';
  const heuristicText = `${card.theme}${card.learnContent.title}${card.practiceTask}`;
  const robotReady = /(模板|清单|纪要|生成|对齐|跟踪|排查)/.test(heuristicText) && card.learnContent.type !== '纠偏卡';
  const robotReasons = robotReady
    ? ['任务输出格式明确', `已匹配${card.learnContent.type}资产`, '当前阶段可先由机器人生成首稿']
    : ['关键判断仍需人工定调', '上下文还需要结合现场信息', '属于高博弈或高创造性动作'];

  return {
    id: card.id,
    title: card.theme,
    project: card.clientName || card.eventLineName || card.learnContent.title,
    deadline: card.isUrgent ? '本周内' : index === 0 ? '本周排期' : '可安排到下周',
    urgency,
    urgencyColor: urgentColor,
    phase,
    risks: [card.reason, card.whyNow || ability?.evidence || '当前场景缺少稳定复用动作，容易在关键节点返工'],
    nextAdvice: card.whyNow || card.practiceTask,
    robotReady,
    robotReasons,
    recommendationId: card.recommendationId,
    linkedTaskId: card.linkedTaskId ?? null,
    linkedContexts: card.linkedTaskId && !(card.linkedContexts || []).some((context) => context.objectType === 'task')
      ? [
          {
            objectType: 'task',
            objectId: card.linkedTaskId,
            label: card.theme,
            subtitle: card.projectStage || card.eventLineName || card.clientName || '成长练习',
            tab: 'tasks',
            statusLabel: '成长练习',
          },
          ...(card.linkedContexts || []),
        ]
      : (card.linkedContexts || []),
    xpReward: card.xpReward,
    contextSummary: card.reason || card.whyNow || card.practiceTask,
    projectModuleName: null,
    projectFlowName: null,
    sourceEvidence: [card.learnContent.title].filter(Boolean),
    currentBlocker: card.reason,
    missingSignals: [card.reason].filter(Boolean),
    hasBackground: true,
    hasDeadline: false,
    isCrossDepartment: Boolean(card.eventLineName || card.clientName),
    needsReview: false,
    evidenceCount: 1,
    pendingCollaborations: 0,
    taskIntent: buildFallbackTaskIntent(
      'growth_practice',
      card.practiceTask,
      card.learnContent.title,
      card.whyNow || card.reason || '系统根据当前成长缺口推了这条练习。',
      [card.learnContent.type === '模板' ? 'write' : 'collab', ability?.name === '分析判断' ? 'analyze' : 'exec'].filter(Boolean) as GrowthTaskIntent['requiredAbilities'],
    ),
    universalSkills: [
      {
        id: `${card.id}-skill`,
        cardType: '动作卡',
        title: card.learnContent.title,
        summary: card.summary || card.reason || card.practiceTask,
        whyRelevant: card.whyNow || card.reason || '这是当前成长缺口最接近的一条练习。',
        checklist: [card.practiceTask].filter(Boolean),
        talkTrack: [],
        templateHint: card.learnContent.title,
        sourceKind: 'rule',
        expectedOutput: card.practiceTask,
      },
    ],
    projectContextPack: buildFallbackProjectContextPack(card.clientName || card.eventLineName || card.theme, card.reason || card.practiceTask),
    actionPlan: [],
    materialRefs: [],
  };
}

function findPhaseByHint(value?: string | null): ProcessStep['name'] | null {
  const normalized = normalizeText(value);
  if (!normalized) return null;
  const matched = PROCESS_STEPS.find((step) => normalized.includes(step.name));
  return matched?.name || null;
}

function contextIdentity(context: GrowthContextLink) {
  return `${context.objectType}:${context.objectId}`;
}

function ensureTaskContext(label: string, subtitle: string, taskId?: string | null, contexts?: GrowthContextLink[]) {
  if (!taskId) return contexts || [];
  const taskContext = {
    objectType: 'task',
    objectId: taskId,
    label,
    subtitle,
    tab: 'tasks',
    statusLabel: '成长练习',
  } satisfies GrowthContextLink;
  if ((contexts || []).some((context) => context.objectType === 'task' && context.objectId === taskId)) {
    return contexts || [];
  }
  return [taskContext, ...(contexts || [])];
}

function buildTaskFromFocusAction(focus: GrowthFocusAction, index: number): WorkbenchTask {
  const phase = findPhaseByHint(focus.triggerNode || focus.projectStage || focus.summary || focus.title) || PHASE_BY_INDEX[Math.min(index + 2, PHASE_BY_INDEX.length - 1)];
  const heuristicText = `${focus.title}${focus.summary}${focus.whyNow}`;
  const robotReady = /(模板|清单|纪要|生成|对齐|跟踪|排查|草案)/.test(heuristicText);
  return {
    id: `focus-${focus.id}`,
    title: focus.title,
    project: focus.clientName || focus.eventLineName || focus.triggerNode || '成长焦点',
    deadline: focus.linkedTaskId ? '跟随当前任务' : '本周补动作',
    urgency: /风险|卡住|返工|阻塞|现在/.test(focus.whyNow) ? '建议优先处理' : '需先补关键动作',
    urgencyColor: /风险|卡住|返工|阻塞|现在/.test(focus.whyNow) ? 'text-red-700 bg-red-100' : 'text-orange-700 bg-orange-100',
    phase,
    risks: [focus.whyNow || focus.summary || '当前动作还没有稳定落到真实任务中。'],
    nextAdvice: focus.summary || focus.whyNow || `先围绕${focus.title}补一条可执行动作。`,
    robotReady,
    robotReasons: robotReady
      ? ['当前动作有清晰输出', '已匹配到可复用练习或模板', '适合先让机器人生成草案再人工判断']
      : ['仍需要人工结合现场判断', '当前动作更偏策略或协作博弈，不适合直接自动执行'],
    recommendationId: null,
    linkedTaskId: focus.linkedTaskId ?? null,
    linkedContexts: ensureTaskContext(focus.title, focus.projectStage || focus.eventLineName || focus.clientName || '当前焦点', focus.linkedTaskId, focus.linkedContexts),
    xpReward: 20,
    contextSummary: focus.summary,
    projectModuleName: null,
    projectFlowName: focus.triggerNode || null,
    sourceEvidence: [focus.whyNow || focus.summary].filter(Boolean),
    currentBlocker: focus.whyNow,
    missingSignals: [focus.whyNow].filter(Boolean),
    hasBackground: true,
    hasDeadline: false,
    isCrossDepartment: Boolean(focus.eventLineId || focus.clientId),
    needsReview: false,
    evidenceCount: 1,
    pendingCollaborations: 0,
    taskIntent: buildFallbackTaskIntent(
      'focus_action',
      focus.summary || focus.title,
      focus.triggerNode || '当前焦点动作',
      focus.whyNow || '这条动作被识别为当前最值得补的一步。',
      ['exec', 'collab'],
    ),
    universalSkills: [],
    projectContextPack: buildFallbackProjectContextPack(focus.clientName || focus.eventLineName || focus.title, focus.summary || focus.whyNow),
    actionPlan: [],
    materialRefs: [],
  };
}

function buildTaskFromPendingCapture(capture: GrowthPendingCapture, index: number): WorkbenchTask {
  const phase = findPhaseByHint(capture.projectStage || capture.nextActionText || capture.summary) || (capture.sourceType === 'task_attachment_candidate' ? '信息核对' : PHASE_BY_INDEX[Math.min(index + 3, PHASE_BY_INDEX.length - 1)]);
  return {
    id: `capture-${capture.id}`,
    title: capture.title,
    project: capture.clientName || capture.eventLineName || '待放大成长',
    deadline: '等待闭环',
    urgency: capture.missingReasons.some((reason) => /复盘|沉淀|闭环/.test(reason)) ? '需先补关键动作' : '可继续推进',
    urgencyColor: capture.missingReasons.some((reason) => /复盘|沉淀|闭环/.test(reason)) ? 'text-orange-700 bg-orange-100' : 'text-green-700 bg-green-100',
    phase,
    risks: capture.missingReasons.length ? capture.missingReasons.slice(0, 2) : [capture.summary || '系统已经识别到成长信号，但还缺最终闭环。'],
    nextAdvice: capture.nextActionText || capture.summary || '先补资料、复盘或沉淀，再把这条成长放大。 ',
    robotReady: false,
    robotReasons: ['当前更适合先由人补资料、复盘或沉淀说明', '这类信号需要解释层，不适合只靠自动执行完成'],
    recommendationId: null,
    linkedTaskId: capture.linkedContexts.find((context) => context.objectType === 'task')?.objectId ?? null,
    linkedContexts: capture.linkedContexts,
    xpReward: 16,
    contextSummary: capture.summary,
    projectModuleName: null,
    projectFlowName: capture.projectStage || null,
    sourceEvidence: capture.missingReasons,
    currentBlocker: capture.missingReasons[0] || null,
    missingSignals: capture.missingReasons,
    hasBackground: true,
    hasDeadline: false,
    isCrossDepartment: Boolean(capture.eventLineId || capture.clientId),
    needsReview: capture.missingReasons.some((reason) => /复盘|解释|说明/.test(reason)),
    evidenceCount: 1,
    pendingCollaborations: 0,
    taskIntent: buildFallbackTaskIntent(
      'pending_capture',
      capture.nextActionText || capture.summary || '把这条成长候选放大成正式沉淀',
      '一条完成闭环的成长记录',
      capture.stateReason || '系统已经看到信号，但还缺最后的解释或沉淀。',
      ['write', 'analyze'],
    ),
    universalSkills: [],
    projectContextPack: buildFallbackProjectContextPack(capture.clientName || capture.eventLineName || capture.title, capture.summary, {
      contextGaps: capture.missingReasons,
    }),
    actionPlan: [],
    materialRefs: [],
  };
}

function normalizeText(value?: string | null) {
  return (value ?? '').trim();
}

function parseTaskDate(value?: string | null) {
  if (!value) return null;
  const candidate = value.length <= 10 ? `${value}T00:00:00` : value;
  const date = new Date(candidate);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatTaskDeadline(task: Task) {
  const raw = task.dueDate || task.ddl;
  if (!raw) return '待补日期';
  const date = parseTaskDate(raw);
  if (!date) return raw;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  date.setHours(0, 0, 0, 0);
  const diffDays = Math.round((date.getTime() - today.getTime()) / 86400000);
  if (diffDays < 0) return `已超期 ${Math.abs(diffDays)} 天`;
  if (diffDays === 0) return '今天';
  if (diffDays === 1) return '明天';
  if (diffDays <= 7) return `${diffDays} 天后`;
  return `${date.getMonth() + 1}月${date.getDate()}日`;
}

function inferTaskPhase(task: Task): ProcessStep['name'] {
  const blockedStep = normalizeText(task.orgContext?.blockedAtStep);
  const haystack = `${task.title} ${task.desc} ${task.note ?? ''} ${blockedStep}`;
  if (/需求|接收|收件|待接收/.test(haystack) || task.status === 'inbox') return '需求接收';
  if (/信息|资料|材料|核对|澄清/.test(haystack)) return '信息核对';
  if (/对齐|会议|纪要|评审/.test(haystack)) return '内部对齐';
  if (/方案|白皮书|提案|文档|大纲|写作|输出/.test(haystack)) return '方案产出';
  if (/沟通|协调|协作|推进|谈判|资源/.test(haystack)) return '沟通推进';
  if (/交付|验收|上线|发布|闭环/.test(haystack)) return '交付闭环';
  if (task.status === 'done') return '复盘沉淀';
  if (task.status === 'doing') return task.orgContext?.isCrossDepartment ? '沟通推进' : '交付闭环';
  return task.orgContext?.isCrossDepartment || task.collaborators.length > 0 ? '内部对齐' : '信息核对';
}

function buildUrgencyMeta(task: Task) {
  const dueDate = parseTaskDate(task.dueDate || task.ddl);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diffDays = dueDate ? Math.round((new Date(dueDate.setHours(0, 0, 0, 0)).getTime() - today.getTime()) / 86400000) : null;
  if (diffDays !== null && diffDays < 0) {
    return { urgency: '建议优先处理', urgencyColor: 'text-red-700 bg-red-100' };
  }
  if (task.priority === 'high' || (diffDays !== null && diffDays <= 2)) {
    return { urgency: '建议优先处理', urgencyColor: 'text-red-700 bg-red-100' };
  }
  if (task.viewerInboxStatus === 'pending' || task.orgContext?.needsReview || task.orgContext?.blockedAtStep) {
    return { urgency: '需先补关键动作', urgencyColor: 'text-orange-700 bg-orange-100' };
  }
  return { urgency: '可直接推进', urgencyColor: 'text-green-700 bg-green-100' };
}

function buildTaskRisks(task: Task, phase: ProcessStep['name']) {
  const risks: string[] = [];
  if (!normalizeText(task.desc) && !normalizeText(task.note)) {
    risks.push('任务背景信息偏少，开始前建议先补齐目标、上下文和预期输出。');
  }
  if (!task.dueDate && !task.ddl) {
    risks.push('截止时间尚未明确，推进节奏容易在中途松掉。');
  }
  if (task.orgContext?.isCrossDepartment || task.collaborators.length > 0) {
    risks.push('涉及多人或跨部门协作，如果不先对齐边界和责任人，后续容易返工。');
  }
  if (task.viewerInboxStatus === 'pending' || (task.collaborationSummary?.pending ?? 0) > 0) {
    risks.push('仍有协作者未完成接收确认，关键动作可能停在等待。');
  }
  if (task.orgContext?.needsReview) {
    risks.push('当前任务仍需要复核或审批，建议先补齐说明与证据。');
  }
  if (task.status === 'inbox') {
    risks.push('任务还停留在待接收，若不尽快确认信息，容易拖成被动响应。');
  }
  if (risks.length > 0) return risks.slice(0, 2);
  const defaults: Record<ProcessStep['name'], string> = {
    需求接收: '需求来源和目标对象还未完全确认，过早执行容易方向跑偏。',
    信息核对: '关键信息口径若未先统一，后续材料和决策会反复返工。',
    内部对齐: '参会人、边界和预期结论不清楚时，会议很容易变成信息交换。',
    方案产出: '结构与受众若不匹配，方案会花很多时间在重写上。',
    沟通推进: '关键利益方未提前识别时，推进节点最容易卡在协作博弈上。',
    交付闭环: '只推进动作不收责任人和时间点，容易在最后一步失去闭环。',
    复盘沉淀: '如果只记录结果不提炼方法，这次经验很难转成下次可复用资产。',
  };
  return [defaults[phase]];
}

function buildRobotAssessment(task: Task, phase: ProcessStep['name']) {
  const contextSignals = [normalizeText(task.desc), normalizeText(task.note), task.tags.length ? 'tags' : '', task.dueDate || task.ddl || '']
    .filter(Boolean)
    .length;
  const haystack = `${task.title}${task.desc}${task.note ?? ''}`;
  const standardizable = /(会议|纪要|清单|模板|方案|提纲|白皮书|复盘|风险|对齐|材料|SOP|文档)/.test(haystack);
  const humanHeavy = task.orgContext?.isCrossDepartment || /(协调|沟通|谈判|客户|资源|博弈|冲突)/.test(haystack);
  const robotReady = contextSignals >= 2 && standardizable && !humanHeavy && task.status !== 'inbox';
  if (robotReady) {
    return {
      robotReady: true,
      robotReasons: ['任务上下文已补齐到可生成首稿', `当前处在${phase}阶段，标准输出较明确`, '可先由机器人生成准备清单或文档草稿'],
    };
  }
  const reasons = [];
  if (contextSignals < 2) reasons.push('任务描述、备注或截止信息仍不够完整');
  if (humanHeavy) reasons.push('当前阶段强依赖跨部门或现场判断，暂不适合全自动执行');
  if (!standardizable) reasons.push('任务输出结构还不够标准化，机器人难以稳定接手');
  return {
    robotReady: false,
    robotReasons: reasons.slice(0, 3).length > 0 ? reasons.slice(0, 3) : ['当前任务仍需要人先定调，再适合让机器人协助执行'],
  };
}

function buildNextAdvice(task: Task, phase: ProcessStep['name']) {
  const taskName = `「${task.title}」`;
  switch (phase) {
    case '需求接收':
      return `先为${taskName}确认目标对象、优先级和成功标准，再进入执行。`;
    case '信息核对':
      return `先补齐${taskName}所需的材料、数据和关键口径，再进入下一步。`;
    case '内部对齐':
      return `建议先把${taskName}的参会人、边界和预期结论写清楚，再开始拉会或对齐。`;
    case '方案产出':
      return `已具备开始条件，建议先为${taskName}拉出结构化大纲，再补细节。`;
    case '沟通推进':
      return `不要直接硬推，先把${taskName}的责任人、协作边界和时间线谈清楚。`;
    case '交付闭环':
      return `把${taskName}的交付物、待办和复核节点一起收拢，避免最后一步失焦。`;
    case '复盘沉淀':
      return `完成${taskName}后，尽快把有效做法沉淀成一条可复用经验。`;
    default:
      return `先补齐${taskName}的关键动作，再继续推进。`;
  }
}

function buildWorkbenchTaskFromTask(task: Task): WorkbenchTask {
  const phase = inferTaskPhase(task);
  const urgencyMeta = buildUrgencyMeta(task);
  const robotAssessment = buildRobotAssessment(task, phase);
  const linkedContexts: GrowthContextLink[] = [
    {
      objectType: 'task',
      objectId: task.id,
      label: task.title,
      subtitle: task.projectContext?.stage || task.eventLineName || task.clientName || task.listName,
      tab: 'tasks',
      statusLabel: task.status,
    },
  ];
  if (task.eventLineId && task.eventLineName) {
    linkedContexts.push({
      objectType: 'event_line',
      objectId: task.eventLineId,
      label: task.eventLineName,
      subtitle: task.businessCategory || task.projectContext?.stage || '事件线',
      tab: 'tasks',
      statusLabel: '事件线',
    });
  }
  if (task.clientId && task.clientName) {
    linkedContexts.push({
      objectType: 'client',
      objectId: task.clientId,
      label: task.clientName,
      subtitle: task.projectContext?.stage || task.businessCategory || '项目工作台',
      tab: 'client_workspace',
      statusLabel: '客户项目',
    });
  }
  const projectModuleId = task.projectContext?.projectModuleId || task.projectModuleId;
  const projectModuleName = task.projectContext?.projectModuleName || task.projectModuleName;
  if (projectModuleId && projectModuleName) {
    linkedContexts.push({
      objectType: 'project_module',
      objectId: projectModuleId,
      label: projectModuleName,
      subtitle: task.clientName || task.eventLineName || '项目模块',
      tab: 'tasks',
      statusLabel: '项目模块',
    });
  }
  const projectFlowId = task.projectContext?.projectFlowId || task.projectFlowId;
  const projectFlowName = task.projectContext?.projectFlowName || task.projectFlowName;
  if (projectFlowId && projectFlowName) {
    linkedContexts.push({
      objectType: 'project_flow',
      objectId: projectFlowId,
      label: projectFlowName,
      subtitle: task.projectContext?.stage || task.businessCategory || '流程节点',
      tab: 'tasks',
      statusLabel: '项目流程',
    });
  }
  const contextSummary = task.projectContext?.backgroundSummary || task.desc || task.note || '';
  const taskIntent = buildFallbackTaskIntent(
    /(协议|合同|条款|合作说明|说明迭代)/.test(`${task.title}${task.desc}`) ? 'agreement_alignment'
      : /(沟通|对接|访谈|老师|客户)/.test(`${task.title}${task.desc}`) ? 'external_communication'
      : /(会议|议程|纪要|评审)/.test(`${task.title}${task.desc}`) ? 'meeting_preparation'
      : /(方案|白皮书|提案|大纲|说明书)/.test(`${task.title}${task.desc}`) ? 'proposal_output'
      : 'general_execution',
    task.projectContext?.goalSummary || task.nextAction || buildNextAdvice(task, phase),
    task.projectContext?.projectFlowSummary || task.projectContext?.projectModuleSummary || task.nextAction || '一条明确的后续动作',
    task.currentBlocker || task.projectContext?.riskSummary || '系统根据当前任务字段推导了最小作战建议。',
    /(方案|白皮书|提案|大纲|说明书)/.test(`${task.title}${task.desc}`) ? ['write', 'analyze'] : ['collab', 'exec'],
  );
  const projectContextPack = buildFallbackProjectContextPack(task.clientName || task.eventLineName || task.title, contextSummary, {
    taskNotes: [task.desc, task.note || '', task.projectContext?.goalSummary || '', task.recentDecision || ''].map((item) => normalizeText(item)).filter(Boolean).slice(0, 4),
    attachments: task.attachments.map((item) => item.title).filter(Boolean).slice(0, 4),
    memoryHints: task.memoryHints.slice(0, 4),
    linkedFacts: task.linkedFactsPreview.map((item) => item.factValue).filter(Boolean).slice(0, 4),
    clientSummary: task.projectContext?.backgroundSummary || '',
    eventLineSummary: [task.eventLineName || '', task.projectContext?.currentFocus || '', task.projectContext?.currentBlocker || ''].map((item) => normalizeText(item)).filter(Boolean).join('；'),
    keyWarnings: task.projectContext?.riskSummary ? [task.projectContext.riskSummary] : [],
    contextGaps: [
      !normalizeText(task.desc) && !normalizeText(task.note) ? '缺任务背景说明' : '',
      !task.attachments.length && !task.linkedFactsPreview.length ? '缺附件或事实依据' : '',
      !task.clientId && !task.eventLineId ? '缺项目归属' : '',
    ].filter(Boolean),
  });
  return {
    id: task.id,
    title: task.title,
    project: task.projectContext?.projectFlowName || task.projectContext?.projectModuleName || task.eventLineName || task.projectContext?.clientName || task.clientName || task.listName || task.ownerName || '任务执行',
    deadline: formatTaskDeadline(task),
    urgency: urgencyMeta.urgency,
    urgencyColor: urgencyMeta.urgencyColor,
    phase,
    risks: buildTaskRisks(task, phase),
    nextAdvice: task.nextAction || task.projectContext?.nextAction || buildNextAdvice(task, phase),
    robotReady: robotAssessment.robotReady,
    robotReasons: robotAssessment.robotReasons,
    recommendationId: null,
    linkedTaskId: task.id,
    linkedContexts,
    xpReward: task.priority === 'high' ? 28 : task.priority === 'normal' ? 22 : 16,
    contextSummary,
    projectModuleName,
    projectFlowName,
    sourceEvidence: task.projectContext?.sourceEvidence || [],
    currentBlocker: task.currentBlocker || task.projectContext?.currentBlocker || task.orgContext?.blockedAtStep || null,
    missingSignals: [
      !normalizeText(task.desc) && !normalizeText(task.note) ? '缺任务背景说明' : '',
      !task.dueDate && !task.ddl ? '缺明确时间点' : '',
      (task.orgContext?.isCrossDepartment || task.collaborators.length > 0) ? '缺协作边界确认' : '',
      task.orgContext?.needsReview ? '缺复核说明' : '',
    ].filter(Boolean),
    hasBackground: Boolean(normalizeText(task.desc) || normalizeText(task.note) || normalizeText(task.projectContext?.backgroundSummary)),
    hasDeadline: Boolean(task.dueDate || task.ddl),
    isCrossDepartment: Boolean(task.orgContext?.isCrossDepartment || task.collaborators.length > 0),
    needsReview: Boolean(task.orgContext?.needsReview),
    evidenceCount: task.evidenceCount,
    pendingCollaborations: task.collaborationSummary?.pending ?? 0,
    taskIntent,
    universalSkills: [],
    projectContextPack,
    actionPlan: [],
    materialRefs: [],
  };
}

function buildSkillLabel(ability: AbilityWorkbenchCard) {
  if (ability.currentScore >= 75) return { label: '可放大', tone: 'bg-green-50 text-green-700 border-green-100' };
  if (ability.currentScore - ability.previousScore >= 12) return { label: '适合练一次', tone: 'bg-orange-50 text-orange-600 border-orange-100' };
  return { label: '需补动作', tone: 'bg-red-50 text-red-600 border-red-100' };
}

function sourceKindLabel(sourceKind: string) {
  const labels: Record<string, string> = {
    rule: '通用规则',
    project_context: '项目背景',
    ai_supplement: 'AI 补位',
    task_material: '任务材料',
    client_workspace: '客户工作台',
    event_line: '事件线',
    strategic_focus: '战略焦点',
  };
  return labels[sourceKind] || sourceKind;
}

function sourceKindTone(sourceKind: string) {
  if (sourceKind === 'rule') return 'bg-blue-50 text-blue-700 border-blue-100';
  if (sourceKind === 'project_context' || sourceKind === 'client_workspace' || sourceKind === 'event_line' || sourceKind === 'strategic_focus') {
    return 'bg-emerald-50 text-emerald-700 border-emerald-100';
  }
  if (sourceKind === 'ai_supplement') return 'bg-amber-50 text-amber-700 border-amber-100';
  return 'bg-slate-100 text-slate-600 border-slate-200';
}

function materialIcon(type: SupportMaterial['type']): LucideIcon {
  if (type === '流程说明') return BookOpen;
  if (type === '经验案例') return AlertTriangle;
  return FileText;
}

function processStepForPhase(phase: ProcessStep['name']) {
  return PROCESS_STEPS.find((step) => step.name === phase) || PROCESS_STEPS[2];
}

function normalizePhaseName(value?: string | null): ProcessStep['name'] {
  return PROCESS_STEPS.find((step) => step.name === value)?.name || '信息核对';
}

function contextsOverlap(left: GrowthContextLink[] = [], right: GrowthContextLink[] = []) {
  if (!left.length || !right.length) return false;
  const rightKeys = new Set(right.map(contextIdentity));
  return left.some((context) => rightKeys.has(contextIdentity(context)));
}

function workbenchTaskMatchesTask(
  task: WorkbenchTask,
  input: {
    linkedTaskId?: string | null;
    linkedContexts?: GrowthContextLink[];
    clientName?: string | null;
    eventLineName?: string | null;
    projectStage?: string | null;
  },
) {
  if (input.linkedTaskId && task.linkedTaskId && input.linkedTaskId === task.linkedTaskId) return true;
  if (contextsOverlap(task.linkedContexts || [], input.linkedContexts || [])) return true;
  if (normalizeText(input.eventLineName) && normalizeText(task.project).includes(normalizeText(input.eventLineName))) return true;
  if (normalizeText(input.clientName) && normalizeText(task.project).includes(normalizeText(input.clientName))) return true;
  const hintedPhase = findPhaseByHint(input.projectStage);
  if (hintedPhase && hintedPhase === task.phase) return true;
  return false;
}

function buildProcessSteps(
  task: WorkbenchTask,
  focusActions: GrowthFocusAction[],
  captures: GrowthPendingCapture[],
): ProcessStep[] {
  return PROCESS_STEPS.map((step) => {
    if (step.name === task.phase) {
      return {
        ...step,
        output: task.nextAdvice || focusActions[0]?.summary || task.contextSummary || step.output,
        bottlenecks:
          task.risks.length > 0
            ? task.risks.slice(0, 2)
            : captures.flatMap((capture) => capture.missingReasons).filter(Boolean).slice(0, 2).length
              ? captures.flatMap((capture) => capture.missingReasons).filter(Boolean).slice(0, 2)
              : step.bottlenecks,
      };
    }
    if (step.name === '复盘沉淀' && captures.length) {
      return {
        ...step,
        output: captures[0]?.nextActionText || step.output,
        bottlenecks: captures.flatMap((capture) => capture.missingReasons).filter(Boolean).slice(0, 2).length
          ? captures.flatMap((capture) => capture.missingReasons).filter(Boolean).slice(0, 2)
          : step.bottlenecks,
      };
    }
    return step;
  });
}

function buildProcessChecklist(
  task: WorkbenchTask,
  step: ProcessStep,
  focusActions: GrowthFocusAction[],
  captures: GrowthPendingCapture[],
) {
  const items = [
    `明确该节点的预期产出：${step.output}`,
    !task.hasBackground ? '补齐任务背景、目标和预期输出' : '',
    !task.hasDeadline ? '补齐明确的截止时间或推进节奏' : '',
    task.isCrossDepartment ? '把协作边界、责任人和时间点讲清楚' : '',
    task.pendingCollaborations > 0 ? `完成 ${task.pendingCollaborations} 个待确认协作动作` : '',
    task.needsReview ? '补复核说明、审批依据或验证证据' : '',
    task.evidenceCount <= 0 && ['信息核对', '方案产出', '交付闭环'].includes(step.name) ? '补关键材料、附件或事实依据' : '',
    focusActions[0] ? `把「${focusActions[0].title}」压进当前任务动作清单` : '',
    captures[0] ? `完成后处理「${captures[0].title}」的复盘或经验沉淀` : '',
  ].filter(Boolean) as string[];
  return Array.from(new Set(items)).slice(0, 5);
}

function buildSupportMaterials(
  task: WorkbenchTask,
  learningCards: LearningWorkbenchCard[],
  focusActions: GrowthFocusAction[],
  captures: GrowthPendingCapture[],
): SupportMaterial[] {
  const materials: SupportMaterial[] = [];
  if (task.projectFlowName || task.projectModuleName) {
    materials.push({
      id: `${task.id}-flow`,
      title: task.projectFlowName || task.projectModuleName || '当前项目流程说明',
      type: '流程说明',
      scenario: task.contextSummary || `适用于当前${task.phase}阶段`,
      summary: task.sourceEvidence?.[0] || task.nextAdvice,
      linkedContext: task.linkedContexts.find((context) => ['project_flow', 'project_module', 'task'].includes(context.objectType)) || null,
    });
  }
  if (learningCards[0]) {
    materials.push({
      id: `learning-${learningCards[0].id}`,
      title: learningCards[0].learnContent.title,
      type: learningCards[0].learnContent.type === '模板' ? '模板工具' : learningCards[0].learnContent.type === '方法卡' ? '流程说明' : '经验案例',
      scenario: learningCards[0].whyNow || learningCards[0].reason,
      summary: learningCards[0].practiceTask,
      linkedContext: learningCards[0].linkedContexts?.[0] || null,
    });
  }
  if (captures[0]) {
    materials.push({
      id: `capture-${captures[0].id}`,
      title: captures[0].title,
      type: '经验案例',
      scenario: captures[0].summary || captures[0].projectStage || '系统已识别到待放大的成长信号',
      summary: captures[0].missingReasons.join('；') || captures[0].nextActionText,
      linkedContext: captures[0].linkedContexts[0] || null,
    });
  }
  if (focusActions[0] && materials.length < 3) {
    materials.push({
      id: `focus-${focusActions[0].id}`,
      title: focusActions[0].title,
      type: '模板工具',
      scenario: focusActions[0].whyNow || focusActions[0].summary,
      summary: focusActions[0].summary,
      linkedContext: focusActions[0].linkedContexts[0] || null,
    });
  }
  if (!materials.length && task.sourceEvidence?.length) {
    materials.push({
      id: `${task.id}-evidence`,
      title: task.sourceEvidence[0] || '当前任务背景材料',
      type: '流程说明',
      scenario: task.contextSummary || '来自当前任务的项目背景',
      summary: task.nextAdvice,
      linkedContext: task.linkedContexts[0] || null,
    });
  }
  return materials.slice(0, 3);
}

function buildSupportCopy(task: WorkbenchTask, step: ProcessStep, captures: GrowthPendingCapture[]) {
  const title = task.isCrossDepartment
    ? '为什么这件事要先讲清边界与责任？'
    : !task.hasBackground
      ? '为什么开始前一定要先补齐上下文？'
      : step.name === '复盘沉淀'
        ? '为什么动作刚做完就要立刻沉淀？'
        : `为什么在「${step.name}」阶段要先补关键动作？`;
  const intro = task.isCrossDepartment
    ? '这类跨部门或多人任务最容易翻车的点，不是大家不努力，而是边界、责任人和时间点没有先被讲清楚。'
    : !task.hasBackground
      ? '系统已经识别到当前任务缺少背景、目标或预期输出。没有这些上下文，后续动作看起来很忙，但很容易做偏。'
      : captures.length
        ? '系统已经识别到这条任务里出现了可转化为成长的信号。如果不趁热补复盘或经验沉淀，这次有效动作很快就会丢掉。'
        : '任务学习页不是给你堆资料，而是先指出当前节点最应该补的关键动作。先把动作做对，再去扩写内容。';
  const bullets = [
    task.hasBackground ? '当前任务已经有基础背景，可以直接对齐关键动作。' : '先写清任务目标、对象和预期交付物。',
    task.hasDeadline ? '当前已经有时间点，下一步重点是把责任和边界讲清楚。' : '没有截止时间时，动作很容易在中途失焦。',
    task.isCrossDepartment ? '跨部门任务要优先处理协作边界，避免会后推诿返工。' : '单点任务更要先补事实依据和当前阶段判断。',
  ].filter(Boolean);
  return { title, intro, bullets: bullets.slice(0, 3) };
}

function buildRobotPlan(task: WorkbenchTask, step: ProcessStep, focusActions: GrowthFocusAction[], captures: GrowthPendingCapture[]) {
  const items = [
    `根据${task.project}的上下文，先拟一版「${step.name}」阶段动作清单`,
    task.currentBlocker ? `围绕当前卡点「${task.currentBlocker}」生成一版应对草案` : '',
    focusActions[0] ? `把推荐动作「${focusActions[0].title}」整理成可直接执行的脚本或清单` : '',
    captures[0] ? `预先生成「${captures[0].title}」对应的复盘或经验沉淀骨架` : '',
  ].filter(Boolean);
  return Array.from(new Set(items)).slice(0, 3);
}

function buildLearningSummaryFallback(task: WorkbenchTask, sourceMode: GrowthWorkbenchSnapshot['sourceMode']): GrowthLearningSummary {
  if (sourceMode === 'empty') {
    return {
      headline: '学习导航等待真实任务接入',
      whyItMatters: '系统需要真实任务、项目上下文或成长信号才能给出负责任的学习判断。',
      immediateMove: '前往任务与日历、客户工作台或战略陪伴创建一条真实对象，学习导航将自动激活。',
      generator: 'rules',
      confidence: 'low',
    };
  }
  if (sourceMode === 'growth_seed') {
    return {
      headline: '先把成长信号压成真实任务，再谈更深的项目判断。',
      whyItMatters: '当前更多来自成长推荐或待放大信号，还不是一条上下文完整的真实任务。',
      immediateMove: task.nextAdvice || '先把这条信号落成真实任务，并补齐背景、附件和责任人。',
      generator: 'rules',
      confidence: 'low',
    };
  }
  if (!task.hasBackground) {
    return {
      headline: '这次最该学的不是直接推进，而是先把任务背景、目标和边界补清楚。',
      whyItMatters: '如果目标、上下文和预期输出没说清，后续动作再多也会变成低质量忙碌。',
      immediateMove: task.nextAdvice,
      generator: 'rules',
      confidence: 'low',
    };
  }
  if (task.isCrossDepartment) {
    return {
      headline: '这次真正要学的是：多人协作里先收边界、责任人与时间线。',
      whyItMatters: '跨部门动作最怕默认别人会懂，真正的学习价值在于把协作边界收成可执行对象。',
      immediateMove: task.nextAdvice,
      generator: 'rules',
      confidence: task.evidenceCount > 0 ? 'medium' : 'low',
    };
  }
  return {
    headline: '这次真正要学的是：先判断当前阶段最关键的一步，再推进动作。',
    whyItMatters: '任务学习页的价值不是多给动作，而是先说清这次任务真正值得学的判断。',
    immediateMove: task.nextAdvice,
    generator: 'rules',
    confidence: task.evidenceCount > 0 || task.sourceEvidence.length ? 'medium' : 'low',
  };
}

function buildGenericLessonsFallback(task: WorkbenchTask, learningCards: LearningWorkbenchCard[]): GrowthGenericLesson[] {
  if (learningCards.length > 0) {
    return learningCards.slice(0, 3).map((card) => ({
      id: `learning-${card.id}`,
      title: card.learnContent.title,
      judgment: card.reason || card.whyNow || card.practiceTask,
      applicableScene: card.projectStage || card.triggerNode || task.phase,
      whyItWorks: card.whyNow || card.reason || '这条方法来自近期真实成长推荐，可以直接作为当前任务的练习模板。',
      reuseHint: card.practiceTask || '把这条方法沉淀到成长手册或任务模板里。',
      linkedContext: card.linkedContexts?.[0] || task.linkedContexts?.[0] || null,
    }));
  }
  const defaults: GrowthGenericLesson[] = [];
  if (task.isCrossDepartment) {
    defaults.push({
      id: `${task.id}-lesson-collab`,
      title: '边界不清先补对齐话术',
      judgment: '跨组动作先把目标、交付边界和依赖讲清楚，再进入推进。',
      applicableScene: '多人协作、跨部门推进、需要共同确认责任时',
      whyItWorks: '协作问题大多不是执行力差，而是边界没被提前说清。',
      reuseHint: '把目标、责任人、时间点和依赖写进会前对齐模板。',
      linkedContext: task.linkedContexts?.[0] || null,
    });
  }
  defaults.push({
    id: `${task.id}-lesson-phase`,
    title: '先把当前阶段最关键的一步做对',
    judgment: task.nextAdvice,
    applicableScene: `当前处在「${task.phase}」阶段`,
    whyItWorks: '任务学习页不该把所有动作一次性抛给执行者，而要先把当前阶段最关键的一步说清楚。',
    reuseHint: '以后遇到同类阶段，先按这个判断来收目标、材料或边界。',
    linkedContext: task.linkedContexts?.[0] || null,
  });
  if (!task.hasBackground) {
    defaults.push({
      id: `${task.id}-lesson-background`,
      title: '开始前先补任务背景',
      judgment: '没有背景、目标和预期输出时，任何动作都容易做偏。',
      applicableScene: '任务说明偏少、附件不足、事件线不明确时',
      whyItWorks: '补背景是为了让后续判断更稳，不是为了把页面填满。',
      reuseHint: '下次建任务时先写清对象、目标和预期交付物。',
      linkedContext: task.linkedContexts?.[0] || null,
    });
  }
  return defaults.slice(0, 3);
}

function buildProjectGuidanceFallback(task: WorkbenchTask, sourceMode: GrowthWorkbenchSnapshot['sourceMode']): GrowthProjectGuidance[] {
  const items: GrowthProjectGuidance[] = [];
  if (sourceMode !== 'task') {
    items.push({
      id: `${task.id}-context-mode`,
      title: '当前还不是完整项目判断',
      judgment: '现在更多来自成长推荐或待放大信号，不是来自一条上下文完整的真实任务。',
      whySpecial: '没有真实任务、附件和事件线连续上下文时，系统只能给规则基础版建议。',
      guidanceType: 'context_gap',
      linkedContexts: task.linkedContexts || [],
      evidenceRefs: task.missingSignals || ['缺真实任务上下文'],
    });
  }
  if (task.projectFlowName || task.projectModuleName || task.project) {
    items.push({
      id: `${task.id}-project-specific`,
      title: '这个项目真正特殊的地方',
      judgment: task.currentBlocker || `当前动作挂在「${task.projectFlowName || task.projectModuleName || task.project}」下，判断标准不是把内容写满，而是让这个节点继续向前。`,
      whySpecial: '一旦任务已经有明确项目挂接，它就不是通用待办，而是某条业务线上的推进节点。',
      guidanceType: 'project_specific',
      linkedContexts: task.linkedContexts || [],
      evidenceRefs: [...task.sourceEvidence, ...(task.currentBlocker ? [task.currentBlocker] : [])].slice(0, 3),
    });
  }
  items.push({
    id: `${task.id}-stage-risk`,
    title: '当前阶段最容易返工的点',
    judgment: task.risks[0] || '当前阶段如果不先补关键动作，后面很容易返工。',
    whySpecial: '这条风险来自当前任务对象本身，而不是通用模板里的套话。',
    guidanceType: 'stage_risk',
    linkedContexts: task.linkedContexts || [],
    evidenceRefs: [...task.risks, ...task.missingSignals].slice(0, 3),
  });
  return items.slice(0, 3);
}

function buildReasoningTraceFallback(
  task: WorkbenchTask,
  sourceMode: GrowthWorkbenchSnapshot['sourceMode'],
  focusActions: GrowthFocusAction[],
  captures: GrowthPendingCapture[],
): GrowthReasoningTrace {
  const usedInputs = [
    ...(task.linkedContexts || []).slice(0, 4).map((context) => ({
      id: `${context.objectType}-${context.objectId}`,
      sourceType: ['task', 'event_line', 'client', 'project_module', 'project_flow'].includes(context.objectType) ? (context.objectType as GrowthReasoningTrace['usedInputs'][number]['sourceType']) : 'rule',
      label: context.label,
      detail: context.subtitle || context.statusLabel || '',
    })),
    ...focusActions.slice(0, 1).map((item) => ({
      id: `focus-${item.id}`,
      sourceType: 'focus_action' as const,
      label: item.title,
      detail: item.summary || item.whyNow,
    })),
    ...captures.slice(0, 1).map((item) => ({
      id: `capture-${item.id}`,
      sourceType: 'pending_capture' as const,
      label: item.title,
      detail: item.summary || item.nextActionText,
    })),
  ];
  const missingContext = Array.from(
    new Set(
      [
        ...task.missingSignals,
        sourceMode !== 'task' ? '当前没有真实任务上下文' : '',
        !task.linkedContexts.some((context) => context.objectType === 'event_line') ? '缺事件线连续上下文' : '',
        (!task.evidenceCount && task.sourceEvidence.length === 0) ? '缺附件或明确证据' : '',
        !task.hasBackground ? '缺任务背景说明' : '',
      ].filter(Boolean),
    ),
  );
  return {
    mode: 'rules_only',
    usedInputs: usedInputs.length
      ? usedInputs
      : [
          {
            id: 'rule-only',
            sourceType: 'rule',
            label: '规则推导基线',
            detail: '当前没有足够的真实对象输入，系统只能输出基础规则判断。',
          },
        ],
    evidenceRefs: Array.from(new Set([...task.sourceEvidence, ...(task.currentBlocker ? [task.currentBlocker] : []), ...task.risks])).slice(0, 6),
    missingContext,
    aiContribution: [],
    modelLabel: null,
    confidence: sourceMode === 'task' && task.hasBackground && (task.evidenceCount > 0 || task.sourceEvidence.length > 0) && missingContext.length <= 1 ? 'high' : missingContext.length >= 3 ? 'low' : 'medium',
  };
}

function buildRobotAssistFallback(task: WorkbenchTask): GrowthRobotAssist {
  const haystack = `${task.title}${task.project}${task.contextSummary}${task.currentBlocker ?? ''}`;
  const canDelegate = [
    /(会议|对齐|沟通|纪要)/.test(haystack) ? '会议议程初稿' : '',
    /(会议|对齐|沟通|纪要)/.test(haystack) ? '行动项清单' : '',
    /(方案|提案|白皮书|文档|大纲|写)/.test(haystack) ? '结构化大纲或首版文档骨架' : '',
    /(复盘|总结|方法|沉淀)/.test(haystack) ? '复盘骨架或方法卡初稿' : '',
    task.evidenceCount > 0 || task.sourceEvidence.length > 0 ? '材料整理与证据摘录' : '待确认问题清单',
  ].filter(Boolean);
  const mustStayHuman = [
    task.isCrossDepartment || task.pendingCollaborations > 0 ? '跨部门边界和责任分配' : '',
    /(客户|沟通|谈判|协调)/.test(haystack) ? '关键对象口径和现场判断' : '',
    task.needsReview ? '复核 / 审批结论' : '',
    '最终优先级和是否推进的拍板',
  ].filter(Boolean);
  return {
    ready: task.robotReady,
    canDelegate: Array.from(new Set(canDelegate)).slice(0, 3),
    mustStayHuman: Array.from(new Set(mustStayHuman)).slice(0, 3),
    why: Array.from(new Set(task.robotReasons)).slice(0, 3),
  };
}

function buildAfterActionCaptureFallback(task: WorkbenchTask, captures: GrowthPendingCapture[]): GrowthAfterActionCapture {
  if (captures[0]) {
    return {
      title: captures[0].title,
      summary: captures[0].summary || captures[0].nextActionText,
      experienceType: '待放大成长信号',
      recommendedWriteback: captures[0].eventLineName ? `优先写回事件线「${captures[0].eventLineName}」` : captures[0].clientName ? `优先写回客户「${captures[0].clientName}」` : '写回成长手册或项目经验库',
    };
  }
  return {
    title: `${task.title}：${task.phase} 阶段复盘`,
    summary: `记录这次在「${task.phase}」阶段的关键判断、有效动作、适用边界和下次可复用的方法。`,
    experienceType: task.isCrossDepartment || task.phase === '复盘沉淀' ? '方法卡' : '复盘卡',
    recommendedWriteback: task.project ? `优先写回「${task.project}」相关背景或成长手册` : '写回成长手册',
  };
}

function RocketIcon(props: React.ComponentProps<'svg'>) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z" />
      <path d="m12 15-3-3a22 22 0 0 1 3.82-13 1.5 1.5 0 0 0-1.83 2.5 19.3 19.3 0 0 0-3 3.5C6.19 6.85 4.38 9.07 3 11a19 19 0 0 0 6.13 6.13c1.93-1.38 4.15-3.19 6-5.01a19.3 19.3 0 0 0 3.5-3 1.5 1.5 0 0 0 2.5-1.83A22 22 0 0 1 15 12z" />
      <path d="m12 15 3 3" />
      <path d="m9 12 3 3" />
    </svg>
  );
}

export function GrowthLearningWorkbench({
  learningCards,
  abilityCards,
  dailyDrops,
  workbenchSnapshot,
  currentFocusActions = [],
  pendingCaptures = [],
  tasks: sourceTasks = [],
  flash,
  onScheduleRecommendation,
  onDismissRecommendation,
  schedulingRecommendationId,
  dismissingRecommendationId,
  onOpenComposer,
  onSeedComposer,
  onNavigate,
  onOpenContext,
}: GrowthLearningWorkbenchProps) {
  const realTasks = useMemo(() => {
    const statusRank: Record<Task['status'], number> = { doing: 0, todo: 1, inbox: 2, done: 3, rejected: 4 };
    const priorityRank: Record<Task['priority'], number> = { high: 0, normal: 1, low: 2 };
    return sourceTasks
      .filter((task) => task.status !== 'done' && task.status !== 'rejected')
      .sort((left, right) => {
        const statusDiff = statusRank[left.status] - statusRank[right.status];
        if (statusDiff !== 0) return statusDiff;
        const priorityDiff = priorityRank[left.priority] - priorityRank[right.priority];
        if (priorityDiff !== 0) return priorityDiff;
        const leftDue = parseTaskDate(left.dueDate || left.ddl)?.getTime() ?? Number.MAX_SAFE_INTEGER;
        const rightDue = parseTaskDate(right.dueDate || right.ddl)?.getTime() ?? Number.MAX_SAFE_INTEGER;
        if (leftDue !== rightDue) return leftDue - rightDue;
        return new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime();
      })
      .slice(0, 3)
      .map(buildWorkbenchTaskFromTask);
  }, [sourceTasks]);
  const normalizedWorkbenchSnapshot = useMemo(() => {
    if (!workbenchSnapshot) return null;
    return {
      tasks: workbenchSnapshot.tasks.map((task) => ({
        ...task,
        phase: normalizePhaseName(task.phase),
        taskIntent: task.taskIntent || EMPTY_TASK.taskIntent,
        universalSkills: task.universalSkills || [],
        projectContextPack: task.projectContextPack || EMPTY_TASK.projectContextPack,
        actionPlan: task.actionPlan || [],
        materialRefs: task.materialRefs || [],
      })) as WorkbenchTask[],
      processSteps: workbenchSnapshot.processSteps.map((step) => ({
        ...step,
        name: normalizePhaseName(step.name),
      })) as ProcessStep[],
      actionGroups: {
        before: workbenchSnapshot.actionsBefore.map((action) => ({
          ...action,
          context: action.linkedContext || null,
        })) as WorkbenchAction[],
        during: workbenchSnapshot.actionsDuring.map((action) => ({
          ...action,
          context: action.linkedContext || null,
        })) as WorkbenchAction[],
        after: workbenchSnapshot.actionsAfter.map((action) => ({
          ...action,
          context: action.linkedContext || null,
        })) as WorkbenchAction[],
      },
      supportMaterials: workbenchSnapshot.supportMaterials.map((material) => ({
        ...material,
        linkedContext: material.linkedContext || null,
      })) as SupportMaterial[],
      checklistItems: workbenchSnapshot.checklistItems,
      learningSummary: workbenchSnapshot.learningSummary,
      genericLessons: workbenchSnapshot.genericLessons || [],
      projectGuidance: workbenchSnapshot.projectGuidance || [],
      reasoningTrace: workbenchSnapshot.reasoningTrace,
      robotAssist: workbenchSnapshot.robotAssist,
      afterActionCapture: workbenchSnapshot.afterActionCapture,
      supportCopy: workbenchSnapshot.supportCopy,
      robotPlan: workbenchSnapshot.robotPlan,
      activeTaskId: workbenchSnapshot.activeTaskId || null,
      activeProcessId: workbenchSnapshot.activeProcessId || null,
      sourceMode: workbenchSnapshot.sourceMode,
    };
  }, [workbenchSnapshot]);
  const hasRealTaskContext = realTasks.length > 0;
  const tasks = useMemo(() => {
    if (normalizedWorkbenchSnapshot?.tasks.length) return normalizedWorkbenchSnapshot.tasks;
    if (hasRealTaskContext) return realTasks;
    const derived = [
      ...currentFocusActions.slice(0, 2).map((action, index) => buildTaskFromFocusAction(action, index)),
      ...learningCards.slice(0, 2).map((card, index) => buildTaskFromLearningCard(card, index, abilityCards[index])),
      ...pendingCaptures.slice(0, 2).map((capture, index) => buildTaskFromPendingCapture(capture, index)),
    ];
    const seen = new Set<string>();
    return derived.filter((item) => {
      const key = item.linkedTaskId || item.id;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    }).slice(0, 3);
  }, [abilityCards, currentFocusActions, hasRealTaskContext, learningCards, normalizedWorkbenchSnapshot, pendingCaptures, realTasks]);
  const hasRecommendationContext = !hasRealTaskContext && tasks.length > 0;
  const currentSourceMode: GrowthWorkbenchSnapshot['sourceMode'] = normalizedWorkbenchSnapshot?.sourceMode || (hasRealTaskContext ? 'task' : tasks.length ? 'growth_seed' : 'empty');
  const [activeTaskId, setActiveTaskId] = useState(tasks[0]?.id || EMPTY_TASK.id);
  const [activeProcessId, setActiveProcessId] = useState(processStepForPhase(tasks[0]?.phase || EMPTY_TASK.phase).id);
  const [modalType, setModalType] = useState<ModalType>(null);
  const lastTaskIdRef = useRef<string | null>(null);

  const activeTask = useMemo(() => tasks.find((task) => task.id === activeTaskId) || tasks[0] || EMPTY_TASK, [activeTaskId, tasks]);
  const relatedLearningCards = useMemo(
    () =>
      learningCards.filter((card) =>
        workbenchTaskMatchesTask(activeTask, {
          linkedTaskId: card.linkedTaskId,
          linkedContexts: card.linkedContexts,
          clientName: card.clientName,
          eventLineName: card.eventLineName,
          projectStage: card.projectStage || card.triggerNode,
        }),
      ).slice(0, 3),
    [activeTask, learningCards],
  );
  const relatedFocusActions = useMemo(
    () =>
      currentFocusActions.filter((action) =>
        workbenchTaskMatchesTask(activeTask, {
          linkedTaskId: action.linkedTaskId,
          linkedContexts: action.linkedContexts,
          clientName: action.clientName,
          eventLineName: action.eventLineName,
          projectStage: action.projectStage || action.triggerNode,
        }),
      ).slice(0, 3),
    [activeTask, currentFocusActions],
  );
  const relatedCaptures = useMemo(
    () =>
      pendingCaptures.filter((capture) =>
        workbenchTaskMatchesTask(activeTask, {
          linkedContexts: capture.linkedContexts,
          clientName: capture.clientName,
          eventLineName: capture.eventLineName,
          projectStage: capture.projectStage,
        }),
      ).slice(0, 3),
    [activeTask, pendingCaptures],
  );
  const learningSummary = useMemo(
    () => normalizedWorkbenchSnapshot?.learningSummary || buildLearningSummaryFallback(activeTask, currentSourceMode),
    [activeTask, currentSourceMode, normalizedWorkbenchSnapshot],
  );
  const genericLessons = useMemo(
    () => (normalizedWorkbenchSnapshot?.genericLessons?.length ? normalizedWorkbenchSnapshot.genericLessons : buildGenericLessonsFallback(activeTask, relatedLearningCards.length ? relatedLearningCards : learningCards)),
    [activeTask, learningCards, normalizedWorkbenchSnapshot, relatedLearningCards],
  );
  const projectGuidance = useMemo(
    () => (normalizedWorkbenchSnapshot?.projectGuidance?.length ? normalizedWorkbenchSnapshot.projectGuidance : buildProjectGuidanceFallback(activeTask, currentSourceMode)),
    [activeTask, currentSourceMode, normalizedWorkbenchSnapshot],
  );
  const reasoningTrace = useMemo(
    () => normalizedWorkbenchSnapshot?.reasoningTrace || buildReasoningTraceFallback(activeTask, currentSourceMode, relatedFocusActions, relatedCaptures),
    [activeTask, currentSourceMode, normalizedWorkbenchSnapshot, relatedCaptures, relatedFocusActions],
  );
  const robotAssist = useMemo(
    () => normalizedWorkbenchSnapshot?.robotAssist || buildRobotAssistFallback(activeTask),
    [activeTask, normalizedWorkbenchSnapshot],
  );
  const afterActionCapture = useMemo(
    () => normalizedWorkbenchSnapshot?.afterActionCapture || buildAfterActionCaptureFallback(activeTask, relatedCaptures),
    [activeTask, normalizedWorkbenchSnapshot, relatedCaptures],
  );
  const processSteps = useMemo(
    () => normalizedWorkbenchSnapshot?.processSteps.length ? normalizedWorkbenchSnapshot.processSteps : buildProcessSteps(activeTask, relatedFocusActions, relatedCaptures),
    [activeTask, normalizedWorkbenchSnapshot, relatedCaptures, relatedFocusActions],
  );
  const activeProcess = useMemo(
    () => processSteps.find((step) => step.id === activeProcessId) || processSteps.find((step) => step.name === activeTask.phase) || processSteps[2],
    [activeProcessId, activeTask.phase, processSteps],
  );

  useEffect(() => {
    setActiveTaskId((current) => {
      if (normalizedWorkbenchSnapshot?.activeTaskId && tasks.some((task) => task.id === normalizedWorkbenchSnapshot.activeTaskId)) {
        return normalizedWorkbenchSnapshot.activeTaskId;
      }
      return tasks.some((task) => task.id === current) ? current ?? tasks[0]?.id ?? EMPTY_TASK.id : tasks[0]?.id || EMPTY_TASK.id;
    });
  }, [normalizedWorkbenchSnapshot?.activeTaskId, tasks]);

  useEffect(() => {
    if (lastTaskIdRef.current !== activeTask.id) {
      lastTaskIdRef.current = activeTask.id;
      setActiveProcessId(
        normalizedWorkbenchSnapshot?.activeProcessId
          || (processSteps.find((step) => step.name === activeTask.phase) || processStepForPhase(activeTask.phase)).id,
      );
    }
  }, [activeTask.id, activeTask.phase, normalizedWorkbenchSnapshot?.activeProcessId, processSteps]);

  const actionGroups = useMemo<{ before: WorkbenchAction[]; during: WorkbenchAction[]; after: WorkbenchAction[] }>(
    () =>
      normalizedWorkbenchSnapshot?.actionGroups || {
        before: [
          {
            id: `${activeTask.id}-before-1`,
            title: relatedFocusActions[0]?.title || `开始前先定：${activeTask.title} 的目标与边界`,
            output: relatedFocusActions[0]?.summary || `${activeProcess.output}，并明确第一责任人`,
            scenario: `${activeTask.phase} 开始前`,
            actionLabel: activeTask.recommendationId ? (activeTask.robotReady ? '一键生成草案' : '排入练习') : '打开当前任务',
            supportTitle: '查看为什么要做这一步',
            detail: relatedFocusActions[0]?.whyNow || activeTask.contextSummary,
            kind: activeTask.recommendationId ? 'schedule' : 'task',
            recommendationId: activeTask.recommendationId,
          },
          {
            id: `${activeTask.id}-before-2`,
            title: activeTask.currentBlocker ? `优先处理卡点：${activeTask.currentBlocker}` : '识别风险：先排查最可能翻车的 2 个点',
            output: relatedCaptures[0]?.nextActionText || '关键争议点 + 一条可执行预案',
            scenario: '正式拉人或开工前',
            actionLabel: activeTask.currentBlocker ? '回到当前任务' : '先做风险排查',
            supportTitle: '查看常见翻车案例',
            detail: relatedCaptures[0]?.missingReasons[0] || activeTask.risks[0],
            kind: activeTask.currentBlocker ? 'task' : 'support',
          },
        ],
        during: [
          {
            id: `${activeTask.id}-during-1`,
            title: `执行中关键动作：稳住${activeTask.phase}`,
            output: activeTask.isCrossDepartment ? '各方认同的交付物、边界与时间线' : (relatedFocusActions[1]?.summary || activeProcess.output),
            scenario: '讨论开始发散或推进变慢时',
            actionLabel: activeTask.isCrossDepartment ? '生成沟通话术' : '查看节点清单',
            supportTitle: activeTask.isCrossDepartment ? '查看沟通原理' : '查看节点标准',
            kind: 'support',
          },
        ],
        after: [
          {
            id: `${activeTask.id}-after-1`,
            title: relatedCaptures[0]?.title ? `完成后补强：${relatedCaptures[0].title}` : '完成后沉淀：把这次动作转成可复用经验',
            output: relatedCaptures[0]?.nextActionText || `一条可复用经验 + ${activeTask.xpReward} XP 的练习回流`,
            scenario: '动作完成后 2 小时内',
            actionLabel: relatedCaptures[0] ? '沉淀为经验' : '去记录经验',
            supportTitle: relatedCaptures[0]?.missingReasons[0] ? '查看为什么还没放大' : '查看标准沉淀方式',
            seedTitle: relatedCaptures[0]?.title,
            seedSummary: relatedCaptures[0]?.summary || relatedCaptures[0]?.nextActionText,
            kind: 'compose',
          },
        ],
      },
    [activeProcess.output, activeTask, normalizedWorkbenchSnapshot, relatedCaptures, relatedFocusActions],
  );

  const fallbackMaterials = useMemo<SupportMaterial[]>(
    () =>
      normalizedWorkbenchSnapshot?.supportMaterials
      || buildSupportMaterials(activeTask, relatedLearningCards.length ? relatedLearningCards : learningCards, relatedFocusActions, relatedCaptures),
    [activeTask, learningCards, normalizedWorkbenchSnapshot, relatedCaptures, relatedFocusActions, relatedLearningCards],
  );
  const universalMaterials = useMemo(
    () =>
      genericLessons.map((lesson) => ({
        id: `generic-${lesson.id}`,
        title: lesson.title,
        summary: lesson.judgment,
        scenario: lesson.applicableScene,
        linkedContext: lesson.linkedContext || null,
      })),
    [genericLessons],
  );
  const projectMaterials = useMemo(
    () =>
      fallbackMaterials
        .filter((material) => Boolean(material.linkedContext) || Boolean(material.summary))
        .slice(0, 3),
    [fallbackMaterials],
  );
  const processChecklist = useMemo(
    () => normalizedWorkbenchSnapshot?.checklistItems || buildProcessChecklist(activeTask, activeProcess, relatedFocusActions, relatedCaptures),
    [activeProcess, activeTask, normalizedWorkbenchSnapshot, relatedCaptures, relatedFocusActions],
  );
  const supportCopy = useMemo(
    () => normalizedWorkbenchSnapshot?.supportCopy || buildSupportCopy(activeTask, activeProcess, relatedCaptures),
    [activeProcess, activeTask, normalizedWorkbenchSnapshot, relatedCaptures],
  );
  const robotPlan = useMemo(
    () => normalizedWorkbenchSnapshot?.robotPlan || buildRobotPlan(activeTask, activeProcess, relatedFocusActions, relatedCaptures),
    [activeProcess, activeTask, normalizedWorkbenchSnapshot, relatedCaptures, relatedFocusActions],
  );
  const structuredActionPlan = useMemo<GrowthActionPlanItem[]>(
    () =>
      activeTask.actionPlan.length
        ? activeTask.actionPlan
        : [
            ...actionGroups.before.map((action) => ({
              id: action.id,
              phaseGroup: 'before' as const,
              title: action.title,
              purpose: action.detail || action.scenario,
              expectedOutput: action.output,
              ifMissing: action.detail || activeTask.risks[0] || '',
              actionLabel: action.actionLabel,
              sourceKind: 'rule' as const,
              linkedContext: action.context || undefined,
            })),
            ...actionGroups.during.map((action) => ({
              id: action.id,
              phaseGroup: 'during' as const,
              title: action.title,
              purpose: action.detail || action.scenario,
              expectedOutput: action.output,
              ifMissing: action.detail || activeTask.risks[0] || '',
              actionLabel: action.actionLabel,
              sourceKind: 'rule' as const,
              linkedContext: action.context || undefined,
            })),
            ...actionGroups.after.map((action) => ({
              id: action.id,
              phaseGroup: 'after' as const,
              title: action.title,
              purpose: action.detail || action.scenario,
              expectedOutput: action.output,
              ifMissing: action.detail || activeTask.risks[0] || '',
              actionLabel: action.actionLabel,
              sourceKind: 'rule' as const,
              linkedContext: action.context || undefined,
            })),
          ],
    [actionGroups.after, actionGroups.before, actionGroups.during, activeTask],
  );
  const structuredActionGroups = useMemo(
    () => ({
      before: structuredActionPlan.filter((item) => item.phaseGroup === 'before'),
      during: structuredActionPlan.filter((item) => item.phaseGroup === 'during'),
      after: structuredActionPlan.filter((item) => item.phaseGroup === 'after'),
    }),
    [structuredActionPlan],
  );
  const highlightedAbilities = useMemo(() => {
    const ranked = [...abilityCards].sort((left, right) => {
      const leftGap = left.currentScore - left.previousScore;
      const rightGap = right.currentScore - right.previousScore;
      return rightGap - leftGap;
    });
    return ranked.slice(0, 2);
  }, [abilityCards]);

  const experienceEchoes = useMemo(() => dailyDrops.slice(0, 2), [dailyDrops]);

  const preferredTaskContext = useMemo(() => {
    const contexts = activeTask.linkedContexts || [];
    return (
      contexts.find((context) => context.objectType === 'task')
      || contexts.find((context) => context.objectType === 'event_line')
      || contexts.find((context) => context.objectType === 'client')
      || contexts[0]
      || null
    );
  }, [activeTask.linkedContexts]);

  const openActiveTaskContext = () => {
    if (preferredTaskContext && onOpenContext) {
      onOpenContext(preferredTaskContext);
      return;
    }
    onNavigate?.('tasks');
    flash('success', '已打开任务页，可继续围绕这条真实任务推进动作');
  };

  const handleAction = async (action: WorkbenchAction) => {
    if (action.kind === 'schedule') {
      await onScheduleRecommendation(action.recommendationId);
      return;
    }
    if (action.kind === 'compose') {
      if (action.seedTitle && action.seedSummary && onSeedComposer) {
        onSeedComposer({ title: action.seedTitle, summary: action.seedSummary, sourceType: 'task' });
        return;
      }
      onOpenComposer();
      return;
    }
    if (action.kind === 'task') {
      if (action.context && onOpenContext) {
        onOpenContext(action.context);
        return;
      }
      openActiveTaskContext();
      return;
    }
    if (action.kind === 'process') {
      setModalType('process');
      return;
    }
    setModalType('support');
  };

  const handleActionPlanItem = (item: GrowthActionPlanItem) => {
    if (item.phaseGroup === 'after') {
      if (onSeedComposer) {
        onSeedComposer({
          title: activeTask.title,
          summary: item.expectedOutput || activeTask.nextAdvice,
          sourceType: 'task',
        });
        return;
      }
      onOpenComposer();
      return;
    }
    if (item.linkedContext && onOpenContext) {
      onOpenContext(item.linkedContext);
      return;
    }
    if (item.phaseGroup === 'during') {
      setModalType('support');
      return;
    }
    openActiveTaskContext();
  };

  const handleSecondaryAction = async (label: string) => {
    if (label === 'calendar') {
      setModalType('process');
      return;
    }
    if (label === 'assign') {
      setModalType(activeTask.robotReady ? 'robot' : 'support');
      return;
    }
    if (label === 'tasks') {
      openActiveTaskContext();
      return;
    }
    if (label === 'dismiss') {
      await onDismissRecommendation(activeTask.recommendationId);
      return;
    }
    flash('success', '当前动作已经进入任务学习页的执行清单');
  };

  return (
    <div className="animate-in space-y-6 fade-in duration-300">
      <section>
        <div className="mb-4 flex gap-3 overflow-x-auto pb-2">
          {tasks.map((task) => (
            <button
              key={task.id}
              type="button"
              onClick={() => setActiveTaskId(task.id)}
              className={cx(
                'w-64 flex-shrink-0 rounded-2xl border p-3 text-left transition-all',
                activeTask.id === task.id ? 'border-blue-600 bg-white shadow-md ring-1 ring-blue-600' : 'border-slate-200 bg-white opacity-75 hover:border-slate-300 hover:opacity-100',
              )}
            >
              <div className="mb-2 flex items-start justify-between gap-2">
                <h3 className="truncate text-sm font-semibold text-slate-900">{task.title}</h3>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-xs text-slate-500">{task.deadline}</span>
                <span className={cx('rounded px-1.5 py-0.5 text-[10px] font-medium', task.urgencyColor)}>{task.urgency}</span>
              </div>
            </button>
          ))}
        </div>
        {!tasks.length ? (
          <div className="mb-4 rounded-[24px] border border-dashed border-slate-200 bg-white px-5 py-8 text-center shadow-sm">
            <p className="text-[13px] font-bold text-slate-500">学习导航等待内容接入</p>
            <p className="mt-1 text-[12px] text-slate-400">在任务与日历创建任务、在客户工作台发起会议动作，或在战略陪伴添加成长推荐后，学习导航将自动补全阶段、风险和动作。</p>
          </div>
        ) : null}
        <div className="flex gap-4">
          <div className="relative flex-1 overflow-hidden rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
            <div className="pointer-events-none absolute right-0 top-0 text-slate-900 opacity-5">
              <Target className="translate-x-10 -translate-y-10 h-[200px] w-[200px]" />
            </div>
            <div className="relative z-10 flex h-full flex-col justify-center">
              <div className="mb-2 flex items-center gap-2">
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">当前聚焦执行</span>
                <span className="text-sm text-slate-500">
                  {activeTask.project || '客户项目'} · 处在 <strong className="font-medium text-blue-600">{activeTask.phase}</strong> 阶段
                </span>
              </div>
              <h2 className="mb-6 text-2xl font-bold text-slate-900">{activeTask.title}</h2>
              <div className="mb-4 rounded-2xl border border-red-100 bg-red-50/80 p-4">
                <div className="mb-2 flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4 text-red-600" />
                  <h4 className="text-sm font-bold text-red-900">这件事现在最容易做错的地方</h4>
                </div>
                <ul className="mb-3 list-disc space-y-1 pl-6 text-sm text-red-800">
                  {(activeTask.risks.length ? activeTask.risks : [learningSummary.whyItMatters]).slice(0, 3).map((risk, index) => (
                    <li key={`${activeTask.id}-risk-${index}`}>{risk}</li>
                  ))}
                </ul>
                <div className="flex items-center gap-2 rounded-lg bg-white/60 px-3 py-2 text-xs font-medium text-red-800">
                  <ArrowRight className="h-3.5 w-3.5" />
                  <span>{activeTask.nextAdvice || learningSummary.immediateMove}</span>
                </div>
              </div>
              {activeTask.linkedContexts.length ? (
                <div className="flex flex-wrap gap-2">
                  {activeTask.linkedContexts.slice(0, 3).map((context) => (
                    <button
                      key={`${activeTask.id}-${context.objectType}-${context.objectId}`}
                      type="button"
                      onClick={() => onOpenContext?.(context)}
                      className="rounded-full border border-[#D9E3FF] bg-[#F6F8FF] px-3 py-1.5 text-[12px] font-medium text-[#335CFE] transition hover:bg-[#EEF3FF]"
                    >
                      {context.label}
                      {context.subtitle ? <span className="ml-1 text-slate-400">· {context.subtitle}</span> : null}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          </div>

          <div className={cx('w-80 rounded-[28px] border p-5 transition-all', activeTask.robotReady ? 'border-emerald-200 bg-emerald-50 shadow-[0_0_15px_rgba(16,185,129,0.1)]' : 'border-slate-200 bg-slate-50')}>
            <div className="mb-3 flex items-center gap-2">
              <div className={cx('rounded-lg p-2', activeTask.robotReady ? 'bg-emerald-100 text-emerald-600' : 'bg-slate-200 text-slate-400')}>
                <Bot className="h-6 w-6" />
              </div>
              <div>
                <h3 className={cx('text-sm font-bold', activeTask.robotReady ? 'text-emerald-900' : 'text-slate-600')}>招聘机器人同事协助</h3>
                <p className="mt-1 text-[10px] uppercase tracking-wider text-slate-500">
                  {activeTask.robotReady ? 'AI AGENT READY' : 'CONDITION UNMET'}
                </p>
              </div>
            </div>

            {activeTask.robotReady ? (
              <>
                <p className="mb-4 flex-1 text-xs font-medium text-emerald-800">已满足此阶段自动执行条件，可指派机器人完成大部分标准化筹备工作。</p>
                <div className="mb-4 space-y-1.5">
                  {robotAssist.canDelegate.slice(0, 3).map((item, index) => (
                    <div key={`${activeTask.id}-delegate-${index}`} className="flex items-start gap-1.5 text-[11px] text-emerald-700/80">
                      <CheckCircle className="mt-0.5 h-3 w-3 shrink-0" />
                      <span>{item}</span>
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => setModalType('robot')}
                  className="flex w-full items-center justify-center gap-2 rounded-2xl bg-emerald-600 py-2.5 text-sm font-bold text-white shadow-sm transition hover:bg-emerald-700"
                >
                  <UserCheck className="h-4 w-4" />
                  <span>查看并录用机器人</span>
                </button>
              </>
            ) : (
              <>
                <p className="mb-4 flex-1 text-xs text-slate-500">当前任务暂不具备自动执行条件，需人类主导判断与执行。</p>
                <div className="mb-4 space-y-1.5 rounded-xl bg-white/60 p-3">
                  <p className="mb-1 text-[10px] font-bold text-slate-400">未满足原因：</p>
                  {robotAssist.mustStayHuman.slice(0, 3).map((item, index) => (
                    <div key={`${activeTask.id}-human-${index}`} className="flex items-start gap-1.5 text-[11px] text-slate-500">
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-slate-300" />
                      <span>{item}</span>
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  disabled
                  className="w-full cursor-not-allowed rounded-2xl bg-slate-200 py-2.5 text-sm font-bold text-slate-400"
                >
                  仅支持辅助执行
                </button>
              </>
            )}
          </div>
        </div>
      </section>

      <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm">
        <div className="grid gap-0 xl:grid-cols-3 xl:divide-x xl:divide-slate-100">
          {([
            { key: 'before', title: '开始前必须确认', dot: 'bg-orange-500', cards: actionGroups.before, buttonTone: 'bg-blue-600 text-white hover:bg-blue-700', icon: Zap },
            { key: 'during', title: '执行中可调用', dot: 'bg-blue-500', cards: actionGroups.during, buttonTone: 'border border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100', icon: MessageSquare },
            { key: 'after', title: '完成后沉淀', dot: 'bg-green-500', cards: actionGroups.after, buttonTone: 'bg-slate-100 text-slate-700 hover:bg-slate-200', icon: FileText },
          ] as const).map((section, sectionIndex) => {
            const ActionIcon = section.icon;
            return (
              <div key={section.key} className={cx('p-6', sectionIndex !== 1 && 'bg-slate-50/30')}>
                <h3 className="mb-4 flex items-center gap-2 text-sm font-bold text-slate-900">
                  <span className={cx('h-2 w-2 rounded-sm', section.dot)} />
                  {section.title}
                </h3>
                <div className="space-y-4">
                  {section.cards.length ? section.cards.map((action) => (
                    <div key={action.id} className="group relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-4 transition hover:border-blue-400">
                      <div className="absolute left-0 top-0 h-full w-1 bg-slate-200 transition-colors group-hover:bg-blue-400" />
                      <h4 className="mb-1 pr-4 text-sm font-bold text-slate-800">{action.title}</h4>
                      <p className="mb-2 text-[11px] text-slate-500">适用场景：{action.scenario}</p>
                      <div className="mb-4 flex items-start gap-2 rounded-lg border border-slate-100 bg-slate-50 px-2.5 py-1.5 text-xs text-slate-700">
                        <Target className="mt-0.5 h-3.5 w-3.5 shrink-0 text-blue-500" />
                        <span>预期产出：<span className="font-medium">{action.output}</span></span>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <button
                          type="button"
                          onClick={() => void handleAction(action)}
                          className={cx('inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition', section.buttonTone)}
                        >
                          <ActionIcon className="h-3 w-3" />
                          <span>{action.actionLabel}</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => setModalType('support')}
                          className="text-[11px] text-slate-400 underline underline-offset-2 hover:text-blue-600"
                        >
                          {action.supportTitle}
                        </button>
                      </div>
                    </div>
                  )) : (
                    <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-6">
                      <p className="text-[13px] font-bold text-slate-500">此阶段尚无动作卡</p>
                      <p className="mt-1 text-[12px] text-slate-400">补充任务描述或关联更多上下文后，系统会自动生成该阶段的动作建议。</p>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-8 flex items-center justify-between">
          <h3 className="text-base font-bold text-slate-900">岗位标准流转节点</h3>
        </div>

        <div className="relative mb-6 flex flex-wrap items-start justify-between gap-y-6">
          <div className="absolute left-0 top-2.5 hidden h-0.5 w-full -translate-y-1/2 bg-slate-100 md:block" />
          {processSteps.map((step) => {
            const isActive = activeProcess.id === step.id;
            return (
              <button key={step.id} type="button" onClick={() => setActiveProcessId(step.id)} className="relative z-10 flex min-w-[80px] flex-col items-center gap-2 text-center">
                {isActive ? <span className="absolute -top-7 rounded bg-blue-100 px-2 py-0.5 text-[10px] font-bold text-blue-700 shadow-sm">当前所处</span> : null}
                <div className={cx('h-5 w-5 rounded-full border-[3px] transition-all', isActive ? 'border-blue-600 bg-white shadow-[0_0_0_4px_rgba(37,99,235,0.1)]' : 'border-slate-300 bg-white hover:border-blue-400')} />
                <span className={cx('text-xs font-bold', isActive ? 'text-blue-700' : 'text-slate-500')}>{step.name}</span>
              </button>
            );
          })}
        </div>

        <div className="mt-8 flex flex-col gap-4 rounded-2xl bg-slate-50/60 p-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 text-blue-600">
              <CheckSquare className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-bold text-slate-800">在【{activeProcess.name}】阶段应该做什么？</p>
              <p className="mt-1 text-xs leading-6 text-slate-500">此阶段必须产出：{activeProcess.output}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setModalType('process')}
            className="rounded-xl border border-slate-300 bg-white px-5 py-2 text-sm font-bold text-slate-700 shadow-sm transition hover:border-blue-500 hover:text-blue-600"
          >
            查看该节点标准动作清单
          </button>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
        <section className="flex h-full flex-col rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="mb-6 text-base font-bold text-slate-900">需调用技能补强</h3>
          <div className="flex-1 space-y-6">
            {highlightedAbilities.map((ability, index) => {
              const badge = buildSkillLabel(ability);
              const knowledgeScore = Math.min(100, Math.max(ability.currentScore, ability.previousScore + 18));
              const practiceScore = Math.max(12, Math.min(ability.currentScore, 100));
              return (
                <div key={ability.id} className={cx(index > 0 && 'border-t border-slate-100 pt-5')}>
                  <div className="mb-2 flex items-end justify-between gap-4">
                    <span className="text-sm font-bold text-slate-800">{ability.name}</span>
                    <span className={cx('rounded border px-1.5 py-0.5 text-[10px] font-medium', badge.tone)}>{badge.label}</span>
                  </div>
                  <div className="mb-3 flex items-center gap-2">
                    <span className="w-8 text-[10px] text-slate-400">认知 {knowledgeScore}</span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                      <div className="h-full bg-slate-300" style={{ width: `${knowledgeScore}%` }} />
                    </div>
                  </div>
                  <div className="mb-3 flex items-center gap-2">
                    <span className="w-8 text-[10px] text-slate-400">实战 {practiceScore}</span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                      <div className="h-full bg-blue-600" style={{ width: `${practiceScore}%` }} />
                    </div>
                  </div>
                  <p className="mb-3 text-[11px] leading-5 text-slate-500">{ability.evidence}</p>
                <button
                  type="button"
                  onClick={() => void (activeTask.recommendationId ? onScheduleRecommendation(activeTask.recommendationId) : handleSecondaryAction('tasks'))}
                  disabled={Boolean(activeTask.recommendationId && schedulingRecommendationId === activeTask.recommendationId)}
                  className="inline-flex w-full items-center justify-center gap-1.5 rounded-xl border border-blue-100/50 bg-blue-50 py-2 text-xs font-bold text-blue-600 transition hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
                >
                    <Zap className="h-3 w-3" />
                    <span>{activeTask.recommendationId && schedulingRecommendationId === activeTask.recommendationId ? '处理中...' : `在当前任务中练一次`}</span>
                  </button>
                </div>
              );
            })}
          </div>
        </section>

        <div className="space-y-6">
          <section className="relative overflow-hidden rounded-[28px] bg-slate-900 p-6 text-white shadow-xl">
            <div className="absolute right-0 top-0 h-64 w-64 translate-x-1/2 -translate-y-1/2 rounded-full bg-blue-600/20 blur-3xl" />
            <div className="absolute bottom-0 left-0 h-40 w-40 -translate-x-1/2 translate-y-1/2 rounded-full bg-indigo-500/20 blur-2xl" />
            <div className="relative z-10 flex flex-col gap-6">
              <div>
                <h3 className="mb-2 flex items-center gap-2 text-xl font-bold">
                  <RocketIcon className="h-5 w-5" />
                  现在就推进这件事
                </h3>
                <p className="max-w-xl text-sm text-slate-400">别停在"我看完了"。选一个马上能执行的动作，把刚才的标准直接压回当前任务。</p>
              </div>

              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  disabled={Boolean(activeTask.recommendationId && schedulingRecommendationId === activeTask.recommendationId)}
                  onClick={() => void (activeTask.recommendationId ? onScheduleRecommendation(activeTask.recommendationId) : handleSecondaryAction('tasks'))}
                  className="inline-flex items-center gap-2 rounded-2xl bg-blue-600 px-4 py-2.5 text-sm font-bold text-white shadow-lg transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <ListTodo className="h-4 w-4" />
                  <span>{activeTask.recommendationId && schedulingRecommendationId === activeTask.recommendationId ? '处理中...' : '针对此任务生成准备清单'}</span>
                </button>
                <button
                  type="button"
                  onClick={() => void handleSecondaryAction('calendar')}
                  className="inline-flex items-center gap-2 rounded-2xl border border-white/20 bg-white/10 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-white/20"
                >
                  <CalendarDays className="h-4 w-4" />
                  <span>查看节点清单</span>
                </button>
                <button
                  type="button"
                  onClick={() => void handleSecondaryAction('assign')}
                  className="inline-flex items-center gap-2 rounded-2xl border border-white/20 bg-white/10 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-white/20"
                >
                  <Users className="h-4 w-4" />
                  <span>{activeTask.robotReady ? '查看机器人可接手包' : '查看机器人协作边界'}</span>
                </button>
              </div>

              <div className="flex flex-wrap gap-3 text-xs text-white/80">
                <button
                  type="button"
                  onClick={() => void handleSecondaryAction('tasks')}
                  className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 font-medium transition hover:bg-white/10"
                >
                  <ArrowRight className="h-3.5 w-3.5" />
                  去任务页继续执行
                </button>
                {activeTask.recommendationId ? (
                  <button
                    type="button"
                    onClick={() => void handleSecondaryAction('dismiss')}
                    disabled={dismissingRecommendationId === activeTask.recommendationId}
                    className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 font-medium transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <X className="h-3.5 w-3.5" />
                    {dismissingRecommendationId === activeTask.recommendationId ? '忽略中...' : '先忽略这条推荐'}
                  </button>
                ) : null}
              </div>
            </div>
          </section>

          <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="mb-4 flex items-center justify-between text-sm font-bold text-slate-900">
              <span>如果你还不确定，可以看这 3 条辅助信息</span>
            </h3>
            <div className="space-y-2">
              {fallbackMaterials.length ? fallbackMaterials.map((material) => {
                const Icon = materialIcon(material.type);
                return (
                  <button
                    key={material.id}
                    type="button"
                    onClick={() => {
                      if (material.linkedContext && onOpenContext) {
                        onOpenContext(material.linkedContext);
                        return;
                      }
                      setModalType('support');
                    }}
                    className="group flex w-full items-center justify-between rounded-2xl border border-transparent p-3 text-left transition hover:border-slate-200 hover:bg-slate-50"
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-slate-100 text-slate-500">
                        <Icon className="h-4 w-4" />
                      </div>
                      <div>
                        <h4 className="text-sm font-medium text-slate-800 transition group-hover:text-blue-600">{material.title}</h4>
                        <p className="mt-0.5 text-[11px] text-slate-500">
                          {material.type} · 适用：{material.scenario}
                        </p>
                        {material.summary ? <p className="mt-1 text-[11px] leading-5 text-slate-400">{material.summary}</p> : null}
                      </div>
                    </div>
                    <span className="rounded bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-600 opacity-0 transition group-hover:opacity-100">
                      {material.linkedContext ? '打开对象' : '立即查看'}
                    </span>
                  </button>
                );
              }) : (
                <div className="rounded-[20px] border border-dashed border-slate-200 bg-slate-50 px-4 py-6">
                  <p className="text-[13px] font-bold text-slate-500">暂未匹配到参考材料</p>
                  <p className="mt-1 text-[12px] text-slate-400">丰富任务背景或添加附件后，系统会自动匹配流程说明、经验案例和模板工具。</p>
                </div>
              )}
            </div>
          </section>
        </div>
      </div>

      <section className="mt-10 rounded-t-[28px] border-t-4 border-slate-800 bg-white p-6 shadow-[0_-4px_10px_rgba(0,0,0,0.02)]">
        <div className="grid gap-8 lg:grid-cols-2">
          <div className="border-slate-100 pr-0 lg:border-r lg:pr-8">
            <h3 className="mb-4 flex items-center gap-2 text-sm font-bold text-slate-900">
              <Trophy className="h-4 w-4 text-slate-700" />
              实战应用与经验沉淀
            </h3>
            <div className="space-y-5">
              {experienceEchoes.length ? (
                experienceEchoes.map((echo, index) => (
                  <div key={echo.id} className={cx('relative pl-4', index === 0 ? 'border-l-2 border-green-500' : 'border-l-2 border-slate-200')}>
                    <div className={cx('absolute -left-[5px] top-1 h-2.5 w-2.5 rounded-full', index === 0 ? 'bg-green-500' : 'bg-slate-300')} />
                    <p className="text-sm text-slate-700">
                      在 <span className="font-bold text-slate-900">{echo.task}</span> 中记录了动作结果
                    </p>
                    <p className={cx('mt-1.5 flex items-center gap-1.5 text-xs', index === 0 ? 'text-slate-500' : 'text-slate-400')}>
                      {index === 0 ? <CheckCircle className="h-3 w-3 text-green-500" /> : null}
                      <span>
                        {index === 0 ? `成功转化为 1 条实战经验 · +${echo.xp} XP` : `${echo.time} · 动作已记录`}
                      </span>
                    </p>
                  </div>
                ))
              ) : (
                <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6">
                  <p className="text-[13px] font-bold text-slate-500">实战回流等待第一条记录</p>
                  <p className="mt-1 text-[12px] text-slate-400">把上方任意一个动作排进日程并完成后，回流记录会自动出现在这里。</p>
                </div>
              )}
            </div>
          </div>

          <div className="pl-0 lg:pl-2">
            <h3 className="mb-4 text-sm font-bold text-slate-900">能力增幅表现</h3>
            <div className="mb-4 flex flex-col gap-4 sm:flex-row">
              {highlightedAbilities.slice(0, 1).map((ability) => (
                <div key={ability.id} className="flex-1 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <div className="mb-1 text-xs text-slate-500">
                    因实战应用导致 <strong className="text-slate-700">{ability.name}</strong> 增长
                  </div>
                  <div className="text-xl font-bold text-slate-900">
                    +{Math.max(ability.numericInc, 6)} <span className="text-xs font-normal text-slate-500">实战经验值</span>
                  </div>
                </div>
              ))}
            </div>
            <div className="flex items-start gap-2 rounded-xl border border-blue-100 bg-blue-50/60 p-2.5 text-xs text-slate-600">
              <Zap className="mt-0.5 h-3.5 w-3.5 shrink-0 text-blue-500" />
              <span>
                下一步建议：你的"{activeTask.phase}"动作已经进入可执行阶段，当前最值得补做的是
                <strong>"{actionGroups.after[0]?.title || '把结果转成一条可复用经验'}"</strong>。
              </span>
            </div>
          </div>
        </div>
      </section>

      {modalType === 'robot' ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-sm">
          <div className="flex w-full max-w-xl flex-col overflow-hidden rounded-[28px] bg-white shadow-2xl">
            <div className="relative bg-emerald-600 p-6 text-white">
              <button type="button" onClick={() => setModalType(null)} className="absolute left-4 top-4 text-emerald-200 hover:text-white">
                <X className="h-5 w-5" />
              </button>
              <div className="flex items-center gap-4">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white/20">
                  <Bot className="h-8 w-8" />
                </div>
                <div>
                  <h2 className="text-xl font-bold">机器人可接手包</h2>
                  <p className="mt-1 text-sm text-emerald-100">先说清机器人能接什么、人必须拍板什么，以及当前为什么只能协助到这一步。</p>
                </div>
              </div>
            </div>

            <div className="max-h-[60vh] overflow-y-auto p-6">
              <div className="mb-6 rounded-xl border border-emerald-100 bg-emerald-50 p-3 text-sm font-medium text-emerald-800">
                我已读取当前任务"{activeTask.title}"的学习上下文。下面先区分机器人可接手的交付物、人必须拍板的部分，以及当前这样分工的原因。
              </div>
              <div className="space-y-5">
                <div>
                  <div className="mb-3 text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">机器人先做什么</div>
                  <ul className="relative space-y-3 before:absolute before:inset-y-2 before:left-[11px] before:w-0.5 before:bg-slate-100">
                    {robotAssist.canDelegate.map((item) => (
                      <li key={item} className="relative flex min-h-[24px] flex-col justify-center pl-8">
                        <div className="absolute left-0 z-10 flex h-6 w-6 items-center justify-center rounded-full border border-emerald-200 bg-emerald-100 text-emerald-600">
                          <CheckCircle className="h-3 w-3" />
                        </div>
                        <span className="text-sm font-bold text-slate-700">{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <div className="mb-3 text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">人必须拍板什么</div>
                  <div className="space-y-2">
                    {robotAssist.mustStayHuman.map((item) => (
                      <div key={item} className="rounded-xl border border-amber-100 bg-amber-50 px-3 py-2 text-[13px] leading-6 text-amber-900">
                        {item}
                      </div>
                    ))}
                  </div>
                </div>
                {robotAssist.why.length ? (
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <div className="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">为什么现在是这种分工</div>
                    <div className="space-y-2 text-[13px] leading-6 text-slate-600">
                      {robotAssist.why.map((item) => (
                        <div key={item}>{item}</div>
                      ))}
                    </div>
                  </div>
                ) : null}
                {robotPlan.length ? (
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <div className="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">可直接生成的首稿</div>
                    <div className="space-y-2 text-[13px] leading-6 text-slate-600">
                      {robotPlan.map((item) => (
                        <div key={item}>{item}</div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            </div>

            <div className="flex gap-3 border-t border-slate-100 bg-slate-50 p-4">
              <button
                type="button"
                onClick={async () => {
                  setModalType(null);
                  if (activeTask.recommendationId) {
                    await onScheduleRecommendation(activeTask.recommendationId);
                  } else {
                    await handleSecondaryAction('tasks');
                  }
                }}
                disabled={Boolean(activeTask.recommendationId && schedulingRecommendationId === activeTask.recommendationId)}
                className="flex-1 rounded-2xl bg-emerald-600 py-2.5 font-bold text-white shadow-sm transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {activeTask.recommendationId && schedulingRecommendationId === activeTask.recommendationId ? '处理中...' : '生成首稿并回到任务'}
              </button>
              <button type="button" onClick={() => setModalType(null)} className="flex-1 rounded-2xl border border-slate-300 bg-white py-2.5 font-bold text-slate-700 transition hover:bg-slate-50">
                先只看分工，不生成
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {modalType === 'process' ? (
        <div className="fixed inset-0 z-40 flex justify-end bg-slate-900/30 backdrop-blur-sm">
          <div className="flex h-full w-full max-w-[480px] flex-col bg-white shadow-2xl animate-in slide-in-from-right duration-300">
            <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50 px-6 py-4">
              <h2 className="font-bold text-slate-900">节点：{activeProcess.name} 标准清单</h2>
              <button type="button" onClick={() => setModalType(null)} className="p-1 text-slate-400 hover:text-slate-600">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-6">
              <div className="mb-6 rounded-xl border border-blue-100 bg-blue-50 p-4">
                <h4 className="mb-1 text-xs font-bold uppercase tracking-wider text-blue-900">该节点必须输出</h4>
                <p className="text-sm font-medium text-blue-800">{activeProcess.output}</p>
              </div>

              <h4 className="mb-3 text-sm font-bold text-slate-900">必须完成的检查项</h4>
              <div className="mb-8 space-y-2">
                {processChecklist.map((item) => (
                  <label key={item} className="flex cursor-pointer items-center gap-3 rounded-lg border border-slate-200 p-3 hover:bg-slate-50">
                    <input type="checkbox" className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500" />
                    <span className="text-sm text-slate-700">{item}</span>
                  </label>
                ))}
              </div>

              <h4 className="mb-3 text-sm font-bold text-slate-900">此节点常见雷区</h4>
              <ul className="mb-8 space-y-2 pl-5 text-sm text-red-600">
                {activeProcess.bottlenecks.map((bottleneck) => (
                  <li key={bottleneck} className="list-disc">
                    {bottleneck}
                  </li>
                ))}
              </ul>

              <h4 className="mb-3 text-sm font-bold text-slate-900">可用模板工具</h4>
              <button
                type="button"
                onClick={() => {
                  const context = fallbackMaterials[0]?.linkedContext;
                  if (context && onOpenContext) {
                    onOpenContext(context);
                    setModalType(null);
                    return;
                  }
                  setModalType('support');
                }}
                className="group flex w-full items-center justify-between rounded-lg border border-slate-200 p-3 hover:bg-slate-50"
              >
                <span className="flex items-center gap-2 text-sm text-slate-700">
                  <FileText className="h-4 w-4 text-blue-500" />
                  {fallbackMaterials[0]?.title || '标准动作提报表'}
                </span>
                <span className="text-xs font-bold text-blue-600 opacity-0 transition group-hover:opacity-100">{fallbackMaterials[0]?.linkedContext ? '打开来源' : '一键调用'}</span>
              </button>
            </div>
            <div className="border-t border-slate-100 bg-white p-4">
              <button
                type="button"
                onClick={async () => {
                  setModalType(null);
                  if (activeTask.recommendationId) {
                    await onScheduleRecommendation(activeTask.recommendationId);
                  } else {
                    await handleSecondaryAction('tasks');
                  }
                }}
                disabled={Boolean(activeTask.recommendationId && schedulingRecommendationId === activeTask.recommendationId)}
                className="w-full rounded-2xl bg-slate-900 py-3 font-bold text-white disabled:cursor-not-allowed disabled:opacity-60"
              >
                {activeTask.recommendationId && schedulingRecommendationId === activeTask.recommendationId ? '处理中...' : '将以上清单加入当前任务'}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {modalType === 'support' ? (
        <div className="fixed inset-0 z-40 flex justify-end bg-slate-900/30 backdrop-blur-sm">
          <div className="flex h-full w-full max-w-[400px] flex-col bg-white shadow-2xl animate-in slide-in-from-right duration-300">
            <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50 px-6 py-4">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">判断依据与沉淀建议</span>
              <button type="button" onClick={() => setModalType(null)} className="p-1 text-slate-400 hover:text-slate-600">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-6">
              <h2 className="mb-4 text-xl font-bold text-slate-900">{learningSummary.headline}</h2>
              <div className="space-y-4 text-sm leading-7 text-slate-600">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">当前判断模式</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <span className={cx('rounded-full px-2.5 py-1 text-[11px] font-semibold', reasoningTrace.mode === 'ai_synthesized' ? 'bg-violet-100 text-violet-700' : 'bg-slate-200 text-slate-700')}>
                      {reasoningTrace.mode === 'ai_synthesized' ? 'AI 综合判断' : '规则推导基础版'}
                    </span>
                    <span className={cx('rounded-full px-2.5 py-1 text-[11px] font-semibold', reasoningTrace.confidence === 'high' ? 'bg-emerald-100 text-emerald-700' : reasoningTrace.confidence === 'medium' ? 'bg-amber-100 text-amber-700' : 'bg-rose-100 text-rose-700')}>
                      置信度 {reasoningTrace.confidence === 'high' ? '高' : reasoningTrace.confidence === 'medium' ? '中' : '低'}
                    </span>
                    {reasoningTrace.modelLabel ? (
                      <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600">
                        模型 {reasoningTrace.modelLabel}
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-3 text-[13px] leading-6 text-slate-600">
                    {reasoningTrace.mode === 'ai_synthesized'
                      ? '这次判断包含 AI 的提炼与比较，下面会列出模型实际用到的输入和结论缺口。'
                      : '这次判断主要来自规则基线：任务阶段、背景缺口、协作复杂度、附件/证据情况和显式阻塞。'}
                  </p>
                </div>

                <div>
                  <div className="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">真正用到的输入</div>
                  <div className="space-y-2">
                    {reasoningTrace.usedInputs.slice(0, 6).map((item) => (
                      <div key={item.id} className="rounded-xl border border-slate-200 px-3 py-2">
                        <div className="text-[12px] font-semibold text-slate-800">{item.label}</div>
                        {item.detail ? <div className="mt-1 text-[12px] leading-5 text-slate-500">{item.detail}</div> : null}
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <div className="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">当前仍缺什么</div>
                  <div className="space-y-2">
                    {reasoningTrace.missingContext.length ? reasoningTrace.missingContext.map((item) => (
                      <div key={item} className="rounded-xl border border-amber-100 bg-amber-50 px-3 py-2 text-[12px] leading-5 text-amber-800">
                        {item}
                      </div>
                    )) : (
                      <div className="rounded-xl border border-emerald-100 bg-emerald-50 px-3 py-2 text-[12px] leading-5 text-emerald-700">
                        当前关键上下文已到位，可作为较稳的规则判断基础。
                      </div>
                    )}
                  </div>
                </div>

                {reasoningTrace.aiContribution.length ? (
                  <div>
                    <div className="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">AI 这次具体做了什么</div>
                    <div className="space-y-2">
                      {reasoningTrace.aiContribution.map((item) => (
                        <div key={item} className="rounded-xl border border-violet-100 bg-violet-50 px-3 py-2 text-[12px] leading-5 text-violet-900">
                          {item}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                {supportCopy.bullets.length ? (
                  <div>
                    <div className="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">标准动作要求</div>
                    <ul className="space-y-2 pl-5">
                      {supportCopy.bullets.map((bullet) => (
                        <li key={bullet} className="list-disc">
                          {bullet}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">完成后应该沉淀成什么</div>
                  <div className="mt-2 text-sm font-semibold text-slate-900">{afterActionCapture.title}</div>
                  <p className="mt-2 text-[13px] leading-6 text-slate-600">{afterActionCapture.summary}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <span className="rounded-full bg-white px-2.5 py-1 text-[11px] text-slate-600 ring-1 ring-slate-200">{afterActionCapture.experienceType}</span>
                    <span className="rounded-full bg-white px-2.5 py-1 text-[11px] text-slate-600 ring-1 ring-slate-200">{afterActionCapture.recommendedWriteback}</span>
                  </div>
                </div>
              </div>
            </div>
            <div className="border-t border-slate-100 bg-white p-6 text-center">
              <p className="mb-3 text-xs text-slate-500">看清依据和缺口后，再回到任务里推进</p>
              <button type="button" onClick={() => setModalType(null)} className="w-full rounded-2xl bg-blue-600 py-3 font-bold text-white shadow-sm">
                返回执行当前动作
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default GrowthLearningWorkbench;
~~~

## `src/renderer/components/handbook/GrowthLedgerDrawer.tsx`

- 编码: `utf-8`

~~~tsx
import React, { useEffect, useMemo, useState } from 'react';
import { Filter, Sparkles, X } from 'lucide-react';

import { getGrowthLedger } from '../../lib/api';
import type { GrowthAbilityKey, GrowthContextLink, GrowthOverview, XpLedgerEntry } from '../../../shared/types';

type FlashLevel = 'success' | 'error';

type GrowthLedgerDrawerProps = {
  open: boolean;
  growthOverview: GrowthOverview | null;
  flash: (level: FlashLevel, message: string) => void;
  onClose: () => void;
  initialAbilityKey?: GrowthAbilityKey | null;
  onOpenContext?: (context: GrowthContextLink) => void;
};

function cx(...classNames: Array<string | false | null | undefined>) {
  return classNames.filter(Boolean).join(' ');
}

function formatDateLabel(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(date);
}

function sourceLabel(sourceType: string) {
  if (sourceType === 'badge_unlock') return '勋章点亮';
  if (sourceType === 'handbook_entry') return '经验沉淀';
  if (sourceType === 'handbook_reuse') return '方法复用';
  if (sourceType === 'weekly_review' || sourceType === 'weekly_review_task_entry' || sourceType === 'weekly_review_note') return '周复盘';
  if (sourceType === 'meeting_publish') return '会议发布';
  if (sourceType === 'meeting_action_item_publish') return '会议行动项';
  if (sourceType === 'strategic_confirm') return '战略确认';
  if (sourceType === 'strategic_meeting_apply') return '战略作战包';
  return sourceType || '成长事件';
}

function validationLabel(state: string) {
  if (state === 'candidate') return '候选信号';
  if (state === 'confirmed') return '已确认';
  if (state === 'observed') return '已观察';
  if (state === 'validated') return '已验证';
  if (state === 'institutionalized') return '已机制化';
  if (!state) return '待确认';
  return state;
}

export function GrowthLedgerDrawer({ open, growthOverview, flash, onClose, initialAbilityKey = null, onOpenContext }: GrowthLedgerDrawerProps) {
  const [entries, setEntries] = useState<XpLedgerEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [scope, setScope] = useState<'current' | 'all'>('current');
  const [abilityKey, setAbilityKey] = useState<GrowthAbilityKey | 'all'>(initialAbilityKey || 'all');
  const currentWeekLabel = useMemo(() => growthOverview?.recentEntries.find((entry) => entry.weekLabel)?.weekLabel || '', [growthOverview]);

  useEffect(() => {
    if (!open) return;
    setAbilityKey(initialAbilityKey || 'all');
  }, [initialAbilityKey, open]);

  useEffect(() => {
    if (!open) return;
    const load = async () => {
      setIsLoading(true);
      try {
        const response = await getGrowthLedger({
          abilityKey: abilityKey === 'all' ? undefined : abilityKey,
          weekLabel: scope === 'current' && currentWeekLabel ? currentWeekLabel : undefined,
        });
        setEntries(response.entries);
      } catch (error) {
        flash('error', error instanceof Error ? error.message : 'XP 账本加载失败');
      } finally {
        setIsLoading(false);
      }
    };
    void load();
  }, [abilityKey, currentWeekLabel, flash, open, scope]);

  const totals = useMemo(
    () =>
      entries.reduce(
        (acc, entry) => {
          acc.total += entry.totalXp;
          acc.base += entry.baseXp;
          acc.premium += entry.premiumXp;
          return acc;
        },
        { total: 0, base: 0, premium: 0 },
      ),
    [entries],
  );

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-slate-900/30 backdrop-blur-sm">
      <div className="flex h-full w-full max-w-[920px] flex-col bg-white shadow-2xl animate-in slide-in-from-right duration-300">
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">XP 账本</div>
            <h2 className="mt-1 text-[22px] font-semibold tracking-tight text-slate-900">成长分数从哪里来</h2>
          </div>
          <button type="button" onClick={onClose} className="rounded-full p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="border-b border-slate-100 px-6 py-4">
          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-[20px] border border-slate-100 bg-slate-50/70 p-4">
              <div className="text-[12px] font-medium text-slate-400">总经验</div>
              <div className="mt-2 text-[28px] font-semibold tracking-tight text-slate-900">+{totals.total}</div>
            </div>
            <div className="rounded-[20px] border border-slate-100 bg-slate-50/70 p-4">
              <div className="text-[12px] font-medium text-slate-400">基础经验</div>
              <div className="mt-2 text-[28px] font-semibold tracking-tight text-slate-900">+{totals.base}</div>
            </div>
            <div className="rounded-[20px] border border-slate-100 bg-slate-50/70 p-4">
              <div className="text-[12px] font-medium text-slate-400">组织溢价</div>
              <div className="mt-2 text-[28px] font-semibold tracking-tight text-[#335CFE]">+{totals.premium}</div>
            </div>
          </div>

          <div className="mt-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => setScope('current')} className={cx('rounded-full px-3 py-1.5 text-[12px] font-medium transition', scope === 'current' ? 'bg-[#335CFE] text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200')}>
                本周
              </button>
              <button type="button" onClick={() => setScope('all')} className={cx('rounded-full px-3 py-1.5 text-[12px] font-medium transition', scope === 'all' ? 'bg-[#335CFE] text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200')}>
                全部
              </button>
              {currentWeekLabel && scope === 'current' ? (
                <span className="inline-flex items-center rounded-full border border-[#D9E3FF] bg-[#F6F8FF] px-3 py-1.5 text-[12px] font-medium text-[#335CFE]">
                  <Sparkles className="mr-1.5 h-3.5 w-3.5" />
                  {currentWeekLabel}
                </span>
              ) : null}
            </div>

            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-slate-400" />
              <select
                value={abilityKey}
                onChange={(event) => setAbilityKey(event.target.value as GrowthAbilityKey | 'all')}
                className="rounded-full border border-slate-200 bg-white px-3 py-2 text-[12px] font-medium text-slate-600 outline-none focus:border-[#C9D7FF]"
              >
                <option value="all">全部能力</option>
                {(growthOverview?.abilities || []).map((ability) => (
                  <option key={ability.abilityKey} value={ability.abilityKey}>
                    {ability.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-6">
          {isLoading ? <div className="rounded-[24px] border border-dashed border-slate-200 bg-slate-50 px-4 py-12 text-center text-[13px] font-medium text-slate-400">XP 账本加载中...</div> : null}
          {!isLoading && !entries.length ? <div className="rounded-[24px] border border-dashed border-slate-200 bg-slate-50 px-4 py-12 text-center text-[13px] font-medium text-slate-400">当前筛选条件下没有 XP 记录</div> : null}

          {!isLoading ? (
            <div className="space-y-3">
              {entries.map((entry) => (
                <div key={entry.id} className="rounded-[22px] border border-slate-100 bg-white p-4 shadow-sm">
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full bg-[#EBF0FF] px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.18em] text-[#335CFE]">{entry.abilityLabel}</span>
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.18em] text-slate-500">{sourceLabel(entry.sourceType)}</span>
                        {entry.contributionTags.length ? <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.18em] text-emerald-700">组织贡献 +{entry.premiumXp}</span> : null}
                      </div>
                      <div className="mt-3 text-[15px] font-semibold text-slate-900">{entry.sourceTitle || entry.reason}</div>
                      <div className="mt-1 text-[12px] leading-6 text-slate-500">{entry.reason}</div>
                    </div>
                    <div className="shrink-0 text-right">
                      <div className="text-[18px] font-semibold tracking-tight text-slate-900">+{entry.totalXp} XP</div>
                      <div className="mt-1 text-[11px] text-slate-400">{formatDateLabel(entry.createdAt)}</div>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-2 md:grid-cols-3">
                    <div className="rounded-2xl bg-slate-50 px-3 py-2 text-[12px] text-slate-600">基础经验 <span className="font-semibold text-slate-900">+{entry.baseXp}</span></div>
                    <div className="rounded-2xl bg-slate-50 px-3 py-2 text-[12px] text-slate-600">组织溢价 <span className="font-semibold text-[#335CFE]">+{entry.premiumXp}</span></div>
                    <div className="rounded-2xl bg-slate-50 px-3 py-2 text-[12px] text-slate-600">验证状态 <span className="font-semibold text-slate-900">{validationLabel(entry.validationState)}</span></div>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2">
                    {entry.clientName ? (
                      <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600">客户 · {entry.clientName}</span>
                    ) : null}
                    {entry.eventLineName ? (
                      <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600">事件线 · {entry.eventLineName}</span>
                    ) : null}
                    {entry.projectStage ? (
                      <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600">阶段 · {entry.projectStage}</span>
                    ) : null}
                    {entry.businessCategory ? (
                      <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600">业务 · {entry.businessCategory}</span>
                    ) : null}
                  </div>

                  {entry.sourceRoute.length ? (
                    <div className="mt-3">
                      <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">来源路径</div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {entry.sourceRoute.map((segment, index) => (
                          <span key={`${entry.id}-route-${segment}-${index}`} className="rounded-full bg-[#EEF3FF] px-2.5 py-1 text-[11px] font-medium text-[#335CFE]">
                            {segment}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {entry.contextSummary ? (
                    <div className="mt-3 rounded-2xl border border-slate-100 bg-slate-50/80 px-3 py-3 text-[12px] leading-6 text-slate-600">
                      {entry.contextSummary}
                    </div>
                  ) : null}

                  {(entry.strategicLink || entry.evidenceRefs.length || entry.linkedContexts.length) ? (
                    <div className="mt-3 grid gap-3 lg:grid-cols-3">
                      <div className="rounded-2xl border border-slate-100 bg-white px-3 py-3">
                        <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">战略呼应</div>
                        <div className="mt-2 text-[12px] leading-6 text-slate-600">{entry.strategicLink || '当前没有直接绑定战略线'}</div>
                      </div>
                      <div className="rounded-2xl border border-slate-100 bg-white px-3 py-3">
                        <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">证据数量</div>
                        <div className="mt-2 text-[12px] leading-6 text-slate-600">
                          {entry.evidenceRefs.length ? entry.evidenceRefs.join(' / ') : '当前没有独立证据引用'}
                        </div>
                      </div>
                      <div className="rounded-2xl border border-slate-100 bg-white px-3 py-3">
                        <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">上下文回链</div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {entry.linkedContexts.length ? (
                            entry.linkedContexts.slice(0, 3).map((context) => (
                              <button
                                key={`${entry.id}-${context.objectType}-${context.objectId}`}
                                type="button"
                                onClick={() => {
                                  onClose();
                                  if (onOpenContext) {
                                    onOpenContext(context);
                                  }
                                }}
                                className={cx(
                                  'rounded-full px-2.5 py-1 text-[11px] font-medium transition',
                                  onOpenContext ? 'bg-[#EEF3FF] text-[#335CFE] hover:bg-[#E1E9FF]' : 'bg-slate-100 text-slate-600',
                                )}
                              >
                                {context.label}
                              </button>
                            ))
                          ) : (
                            <span className="text-[12px] text-slate-400">暂无回链</span>
                          )}
                        </div>
                      </div>
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export default GrowthLedgerDrawer;
~~~

## `src/renderer/components/settings/BrandLogoSettingsCard.tsx`

- 编码: `utf-8`

~~~tsx
import React, { useRef, useState } from 'react';
import { ImagePlus, RefreshCw, Save, Trash2 } from 'lucide-react';

type BrandLogoMarkProps = {
  logoDataUrl?: string | null;
  className?: string;
};

export function BrandLogoMark({ logoDataUrl, className = 'w-8 h-8' }: BrandLogoMarkProps) {
  const normalized = logoDataUrl?.trim() || '';
  if (normalized) {
    return (
      <div className={`${className} shrink-0 overflow-hidden rounded-[18px] bg-white border border-gray-100 shadow-[0_8px_24px_rgba(37,99,235,0.12)]`}>
        <img src={normalized} alt="组织 Logo" className="w-full h-full object-contain" />
      </div>
    );
  }

  return (
    <div className={`${className} text-[#2563EB] flex shrink-0 items-center justify-center transition-transform hover:scale-105 duration-300`}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-full h-full drop-shadow-sm">
        <rect x="3" y="3" width="18" height="18" rx="3.5" />
        <path d="M8 8h8v8H8z" />
        <path d="M12 8v8" />
        <path d="M8 12h8" />
        <circle cx="3" cy="12" r="1.5" fill="currentColor" stroke="none" />
        <circle cx="21" cy="12" r="1.5" fill="currentColor" stroke="none" />
        <circle cx="12" cy="3" r="1.5" fill="currentColor" stroke="none" />
        <circle cx="12" cy="21" r="1.5" fill="currentColor" stroke="none" />
      </svg>
    </div>
  );
}

type Props = {
  logoDataUrl?: string | null;
  canManage: boolean;
  busy: boolean;
  hasUnsavedChange: boolean;
  onPickLogo: (file: File) => Promise<void>;
  onClearDraft: () => void;
  onSave: () => Promise<void>;
};

export function BrandLogoSettingsCard({
  logoDataUrl,
  canManage,
  busy,
  hasUnsavedChange,
  onPickLogo,
  onClearDraft,
  onSave,
}: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [isPicking, setIsPicking] = useState(false);

  async function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setLocalError(null);
    setIsPicking(true);
    try {
      await onPickLogo(file);
    } catch (error) {
      setLocalError(error instanceof Error ? error.message : 'PNG 处理失败');
    } finally {
      setIsPicking(false);
    }
  }

  const pending = busy || isPicking;

  return (
    <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm">
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          <h2 className="text-[16px] font-bold text-gray-900">品牌 Logo</h2>
          <p className="text-[12px] text-gray-500 mt-1">
            左上角品牌位支持上传透明背景 PNG。保存后会替换当前内置图标。
          </p>
        </div>
        <div className={`text-[11px] font-bold px-3 py-1.5 rounded-full border ${hasUnsavedChange ? 'border-amber-200 bg-amber-50 text-amber-700' : 'border-slate-100 bg-slate-50 text-slate-600'}`}>
          {hasUnsavedChange ? '有未保存更改' : '已与当前生效稿一致'}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[160px_minmax(0,1fr)] gap-6 items-start">
        <div className="rounded-[28px] border border-gray-100 bg-gradient-to-br from-[#eef3ff] via-white to-[#f8fbff] p-5 flex flex-col items-center gap-3">
          <BrandLogoMark logoDataUrl={logoDataUrl} className="w-20 h-20" />
          <div className="text-center">
            <p className="text-[12px] font-bold text-gray-900">侧栏实时预览</p>
            <p className="text-[11px] text-gray-500 mt-1">建议使用方形 PNG</p>
          </div>
        </div>

        <div className="space-y-4">
          <input ref={inputRef} type="file" accept="image/png" className="hidden" onChange={(event) => void handleFileChange(event)} />

          <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-4">
            <p className="text-[12px] font-bold text-slate-900">上传规则</p>
            <p className="text-[12px] text-slate-600 mt-2 leading-relaxed">
              仅支持 PNG。上传后会在前端压到不超过 256px 的方形边界，再保存进系统设置，避免把大图直接塞进配置。
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-white border border-gray-200 text-[13px] font-bold text-gray-700 disabled:opacity-50"
              onClick={() => inputRef.current?.click()}
              disabled={!canManage || pending}
            >
              {isPicking ? <RefreshCw size={15} className="animate-spin" /> : <ImagePlus size={15} />}
              {logoDataUrl ? '替换 PNG' : '上传 PNG'}
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-white border border-gray-200 text-[13px] font-bold text-gray-700 disabled:opacity-50"
              onClick={onClearDraft}
              disabled={!canManage || pending || !logoDataUrl}
            >
              <Trash2 size={15} />
              清空预览
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-[#5B7BFE] text-white text-[13px] font-bold shadow-sm disabled:opacity-50"
              onClick={() => void onSave()}
              disabled={!canManage || pending || !hasUnsavedChange}
            >
              {busy ? <RefreshCw size={15} className="animate-spin" /> : <Save size={15} />}
              保存 Logo
            </button>
          </div>

          {localError && (
            <div className="rounded-2xl border border-rose-100 bg-rose-50 px-4 py-3 text-[12px] text-rose-700">
              {localError}
            </div>
          )}

          {!canManage && (
            <div className="rounded-2xl border border-amber-100 bg-amber-50 px-4 py-3 text-[12px] text-amber-700">
              当前账号只能查看品牌 Logo，不能上传或替换。
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
~~~

## `src/renderer/components/settings/FeishuAccountBindingPanel.tsx`

- 编码: `utf-8`

~~~tsx
import React, { useEffect, useState } from 'react';
import { Copy, ExternalLink, Link2, QrCode, RefreshCw, ShieldAlert, ShieldCheck, Unplug, X } from 'lucide-react';

import type { FeishuUserBinding } from '../../../shared/types';

type BusyAction = 'idle' | 'starting' | 'refreshing' | 'clearing';

export type FeishuBindingFlowState = {
  authorizeUrl: string;
  callbackUrl: string;
  expiresAt: string;
  qrReady: boolean;
  qrBlockedReason?: string | null;
  qrCodeDataUrl?: string | null;
  statusMessage?: string;
  isPolling?: boolean;
};

type Props = {
  binding: FeishuUserBinding;
  busyAction: BusyAction;
  currentUserName?: string | null;
  pendingAuthorization?: FeishuBindingFlowState | null;
  onStartBinding: () => Promise<void>;
  onRefresh: () => Promise<void>;
  onClearBinding: () => Promise<void>;
  onOpenBindingInBrowser: () => Promise<void>;
  onClosePendingAuthorization: () => void;
};

function statusTone(binding: FeishuUserBinding) {
  if (binding.linked) return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  if (!binding.readyForAuthorization) return 'border-amber-100 bg-amber-50 text-amber-700';
  return 'border-slate-100 bg-slate-50 text-slate-600';
}

export function FeishuAccountBindingPanel({
  binding,
  busyAction,
  currentUserName,
  pendingAuthorization,
  onStartBinding,
  onRefresh,
  onClearBinding,
  onOpenBindingInBrowser,
  onClosePendingAuthorization,
}: Props) {
  const isBusy = busyAction !== 'idle';
  const canShowQr = Boolean(pendingAuthorization?.qrReady && pendingAuthorization?.qrCodeDataUrl);
  const [copyStatus, setCopyStatus] = useState<'idle' | 'copied' | 'failed'>('idle');

  useEffect(() => {
    setCopyStatus('idle');
  }, [pendingAuthorization?.authorizeUrl]);

  const handleCopyAuthorizeUrl = async () => {
    if (!pendingAuthorization?.authorizeUrl) return;
    try {
      await navigator.clipboard.writeText(pendingAuthorization.authorizeUrl);
      setCopyStatus('copied');
      window.setTimeout(() => setCopyStatus('idle'), 1800);
    } catch {
      setCopyStatus('failed');
      window.setTimeout(() => setCopyStatus('idle'), 1800);
    }
  };

  return (
    <>
      <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm space-y-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-[16px] font-bold text-gray-900 flex items-center gap-2">
              <Link2 size={17} />
              飞书账号绑定
            </h2>
            <p className="text-[12px] text-gray-500 mt-1 leading-relaxed">
              当前登录用户先绑定自己的飞书身份，任务与日历里发起飞书会议时，系统会优先按你的绑定账号发送。
            </p>
          </div>
          <div className={`text-[11px] font-bold px-3 py-1.5 rounded-full border ${statusTone(binding)}`}>
            {binding.linked ? '已绑定个人飞书' : binding.readyForAuthorization ? '待绑定' : '缺少飞书授权底座'}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-2xl bg-slate-50 border border-slate-200 p-4">
            <p className="text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-2">当前登录用户</p>
            <p className="text-[13px] font-bold text-slate-900">{currentUserName || binding.userId || '未识别'}</p>
            <p className="text-[12px] text-slate-600 mt-1 break-all">{binding.userId || '尚未加载用户 ID'}</p>
          </div>
          <div className="rounded-2xl bg-slate-50 border border-slate-200 p-4">
            <p className="text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-2">飞书应用</p>
            <p className="text-[13px] font-bold text-slate-900">{binding.appId || '尚未配置 App ID'}</p>
            <p className="text-[12px] text-slate-600 mt-1">
              {binding.linked
                ? `最近校验：${binding.lastVerifiedAt || binding.boundAt || '刚刚'}`
                : binding.readyForAuthorization
                  ? '当前已经具备授权条件'
                  : '需要管理员先配置飞书 App ID、App Secret 和机器人基础设置'}
            </p>
          </div>
        </div>

        {binding.linked ? (
          <div className="rounded-2xl border border-emerald-100 bg-emerald-50/70 px-4 py-4 text-[12px] text-emerald-800 space-y-2">
            <div className="flex items-center gap-2 font-bold">
              <ShieldCheck size={14} />
              已绑定飞书身份
            </div>
            <p>显示名称：{binding.name || binding.enName || '未返回姓名'}</p>
            <p>飞书邮箱：{binding.email || '飞书未返回邮箱'}</p>
            <p className="break-all">open_id：{binding.openId || '未返回 open_id'}</p>
          </div>
        ) : (
          <div className={`rounded-2xl border px-4 py-4 text-[12px] leading-relaxed ${binding.readyForAuthorization ? 'border-blue-100 bg-blue-50/70 text-slate-700' : 'border-amber-100 bg-amber-50 text-amber-800'}`}>
            <div className="flex items-center gap-2 font-bold mb-2">
              {binding.readyForAuthorization ? <QrCode size={14} /> : <ShieldAlert size={14} />}
              {binding.readyForAuthorization ? '还没有绑定个人飞书账号' : '当前还不能发起个人飞书绑定'}
            </div>
            <p>
              {binding.readyForAuthorization
                ? '点击“绑定飞书账号”后会弹出二维码/授权面板。系统会优先尝试使用云端 HTTPS 中继让手机扫码完成授权；如果当前环境还没有公网入口，仍可在当前电脑浏览器完成授权。'
                : '请先让管理员在“飞书单机器人”里配置飞书 App ID、App Secret；如果需要自定义回调地址，也可以单独配置个人绑定回调 URL。'}
            </p>
            {binding.lastError ? <p className="mt-2 text-rose-700">最近错误：{binding.lastError}</p> : null}
          </div>
        )}

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="inline-flex items-center gap-2 px-4 py-3 rounded-2xl bg-[#335CFF] text-white text-[13px] font-bold disabled:opacity-50"
            onClick={() => void onStartBinding()}
            disabled={!binding.readyForAuthorization || isBusy}
          >
            {busyAction === 'starting' ? <RefreshCw size={16} className="animate-spin" /> : <QrCode size={16} />}
            {binding.linked ? '重新绑定飞书账号' : '绑定飞书账号'}
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-2 px-4 py-3 rounded-2xl bg-white border border-gray-200 text-[13px] font-bold text-gray-700 disabled:opacity-50"
            onClick={() => void onRefresh()}
            disabled={isBusy}
          >
            {busyAction === 'refreshing' ? <RefreshCw size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            刷新绑定状态
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-2 px-4 py-3 rounded-2xl bg-white border border-gray-200 text-[13px] font-bold text-gray-700 disabled:opacity-50"
            onClick={() => void onClearBinding()}
            disabled={!binding.linked || isBusy}
          >
            {busyAction === 'clearing' ? <RefreshCw size={16} className="animate-spin" /> : <Unplug size={16} />}
            解除绑定
          </button>
        </div>
      </div>

      {pendingAuthorization ? (
        <div className="fixed inset-0 z-50 bg-slate-950/35 backdrop-blur-sm flex items-center justify-center p-5">
          <div className="w-full max-w-4xl bg-white rounded-[28px] shadow-[0_24px_80px_rgba(15,23,42,0.18)] border border-slate-100 overflow-hidden" onClick={(event) => event.stopPropagation()}>
            <div className="flex items-center gap-4 px-6 py-5 border-b border-slate-100">
              <button type="button" className="w-10 h-10 shrink-0 rounded-2xl border border-slate-200 text-slate-500 hover:text-slate-800 hover:bg-slate-50 flex items-center justify-center" onClick={onClosePendingAuthorization} aria-label="关闭飞书授权绑定">
                <X size={16} />
              </button>
              <div className="flex-1">
                <h3 className="text-[18px] font-bold text-slate-900">飞书授权绑定</h3>
                <p className="text-[12px] text-slate-500 mt-1">授权完成后，工作台会自动刷新个人绑定状态。</p>
              </div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-[280px_minmax(0,1fr)] gap-6 px-6 py-6">
              <div className="rounded-[24px] border border-slate-100 bg-slate-50 p-5 flex flex-col items-center justify-center text-center min-h-[320px]">
                {canShowQr ? (
                  <>
                    <div className="w-[232px] h-[232px] rounded-[24px] bg-white border border-slate-200 shadow-sm flex items-center justify-center overflow-hidden">
                      <img src={pendingAuthorization.qrCodeDataUrl || undefined} alt="飞书绑定二维码" className="w-[208px] h-[208px]" />
                    </div>
                    <p className="mt-4 text-[13px] font-bold text-slate-900">请用飞书扫码完成授权</p>
                    <p className="mt-2 text-[12px] leading-6 text-slate-500">扫码后在飞书里确认授权，工作台会自动刷新绑定结果。</p>
                  </>
                ) : (
                  <>
                    <div className="w-14 h-14 rounded-2xl bg-amber-50 border border-amber-100 flex items-center justify-center text-amber-500">
                      <ShieldAlert size={24} />
                    </div>
                    <p className="mt-4 text-[13px] font-bold text-slate-900">当前还不能用手机扫码完成绑定</p>
                    <p className="mt-2 text-[12px] leading-6 text-slate-500">{pendingAuthorization.qrBlockedReason || '当前授权回调仍指向本机地址。'}</p>
                  </>
                )}
              </div>

              <div className="space-y-4">
                <div className="rounded-[24px] border border-slate-100 bg-white p-5">
                  <p className="text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-2">当前回调地址</p>
                  <p className="text-[13px] font-semibold text-slate-900 break-all">{pendingAuthorization.callbackUrl}</p>
                  <p className="text-[12px] text-slate-500 mt-2 leading-6">
                    手机扫码能否直接完成绑定，取决于这里是否是飞书后台允许的公网 HTTPS 回调地址。系统会优先走云端 HTTPS 中继；如果当前仍是本机地址，就只能在这台电脑浏览器继续授权。
                  </p>
                </div>

                <div className="rounded-[24px] border border-slate-100 bg-slate-50 p-5">
                  <p className="text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-2">当前状态</p>
                  <p className="text-[13px] font-semibold text-slate-900">{pendingAuthorization.statusMessage || '等待授权中'}</p>
                  <p className="text-[12px] text-slate-500 mt-2">
                    {pendingAuthorization.isPolling ? '工作台正在后台轮询绑定结果。' : `本次授权有效期到 ${pendingAuthorization.expiresAt.replace('T', ' ')}`}
                  </p>
                </div>

                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    className="inline-flex items-center gap-2 px-4 py-3 rounded-2xl bg-[#335CFF] text-white text-[13px] font-bold disabled:opacity-50"
                    onClick={() => void onOpenBindingInBrowser()}
                  >
                    <ExternalLink size={16} />
                    在浏览器中继续授权
                  </button>
                  <button
                    type="button"
                    className="inline-flex items-center gap-2 px-4 py-3 rounded-2xl bg-white border border-slate-200 text-[13px] font-bold text-slate-700"
                    onClick={() => void handleCopyAuthorizeUrl()}
                  >
                    <Copy size={16} />
                    {copyStatus === 'copied' ? '授权链接已复制' : copyStatus === 'failed' ? '复制失败' : '复制授权链接'}
                  </button>
                  <button
                    type="button"
                    className="inline-flex items-center gap-2 px-4 py-3 rounded-2xl bg-white border border-slate-200 text-[13px] font-bold text-slate-700"
                    onClick={() => void onRefresh()}
                  >
                    <RefreshCw size={16} />
                    手动刷新绑定状态
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
~~~

## `src/renderer/components/settings/FeishuBotSettingsPanel.tsx`

- 编码: `utf-8`

~~~tsx
import React, { useEffect, useMemo, useState } from 'react';
import { AlertCircle, Bot, CheckCircle2, KeyRound, RefreshCw, Send } from 'lucide-react';

import type { FeishuBotSettings, FeishuBotSettingsPayload, FeishuReceiveIdType } from '../../../shared/types';

type Props = {
  settings: FeishuBotSettings;
  canManage: boolean;
  defaultReceiverEmail?: string | null;
  onSubmit: (payload: FeishuBotSettingsPayload) => Promise<FeishuBotSettings>;
};

const RECEIVE_TYPE_LABELS: Record<FeishuReceiveIdType, string> = {
  open_id: 'open_id',
  user_id: 'user_id',
  email: '邮箱',
  chat_id: 'chat_id',
};

const RECEIVE_TYPE_HINTS: Record<FeishuReceiveIdType, string> = {
  open_id: '适合已经拿到飞书用户 open_id 的场景。',
  user_id: '适合企业内已知 user_id 的场景。',
  email: '如果你的飞书邮箱和当前账号一致，优先用这个。',
  chat_id: '适合先发到群或机器人私聊 chat。',
};

function statusTone(status: FeishuBotSettings['lastConnectionStatus']) {
  if (status === 'success') return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  if (status === 'failed') return 'border-rose-100 bg-rose-50 text-rose-700';
  return 'border-slate-100 bg-slate-50 text-slate-600';
}

export function FeishuBotSettingsPanel({ settings, canManage, defaultReceiverEmail, onSubmit }: Props) {
  const [appId, setAppId] = useState(settings.appId);
  const [receiveIdType, setReceiveIdType] = useState<FeishuReceiveIdType>(settings.receiveIdType);
  const [receiverId, setReceiverId] = useState(settings.receiverId);
  const [botName, setBotName] = useState(settings.botName);
  const [userBindingCallbackUrl, setUserBindingCallbackUrl] = useState(settings.userBindingCallbackUrl);
  const [appSecret, setAppSecret] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);

  useEffect(() => {
    setAppId(settings.appId);
    setReceiveIdType(settings.receiveIdType);
    setReceiverId(settings.receiverId);
    setBotName(settings.botName);
    setUserBindingCallbackUrl(settings.userBindingCallbackUrl);
  }, [settings]);

  const receiverPlaceholder = useMemo(() => {
    if (receiveIdType === 'email') return '请输入你的飞书邮箱';
    if (receiveIdType === 'chat_id') return '请输入 chat_id';
    if (receiveIdType === 'user_id') return '请输入 user_id';
    return '请输入 open_id';
  }, [receiveIdType]);

  const canSendTestMessage = appId.trim() && receiverId.trim() && (settings.hasAppSecret || appSecret.trim());
  const defaultTestMessage = `${botName.trim() || '罗茜茜'} 已接通成功，现在可以给你发消息了。`;

  async function handleSave() {
    setIsSaving(true);
    try {
      await onSubmit({
        appId: appId.trim(),
        receiveIdType,
        receiverId: receiverId.trim(),
        botName: botName.trim() || '罗茜茜',
        userBindingCallbackUrl: userBindingCallbackUrl.trim() || undefined,
        appSecret: appSecret.trim() || undefined,
      });
      setAppSecret('');
    } finally {
      setIsSaving(false);
    }
  }

  async function handleConnectAndSend() {
    setIsTesting(true);
    try {
      await onSubmit({
        appId: appId.trim(),
        receiveIdType,
        receiverId: receiverId.trim(),
        botName: botName.trim() || '罗茜茜',
        userBindingCallbackUrl: userBindingCallbackUrl.trim() || undefined,
        appSecret: appSecret.trim() || undefined,
        sendTestMessage: true,
        testMessage: defaultTestMessage,
      });
      setAppSecret('');
    } finally {
      setIsTesting(false);
    }
  }

  async function handleClearSecret() {
    setIsSaving(true);
    try {
      await onSubmit({
        appId: appId.trim(),
        receiveIdType,
        receiverId: receiverId.trim(),
        botName: botName.trim() || '罗茜茜',
        userBindingCallbackUrl: userBindingCallbackUrl.trim() || undefined,
        clearAppSecret: true,
      });
      setAppSecret('');
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm">
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          <h2 className="text-[16px] font-bold text-gray-900 flex items-center gap-2">
            <Bot size={17} />
            飞书单机器人
          </h2>
          <p className="text-[12px] text-gray-500 mt-1">
            先打通“接通成功即发测试消息”的最小闭环。App Secret 只进本机钥匙串，不落本地业务库。
          </p>
        </div>
        <div className={`text-[11px] font-bold px-3 py-1.5 rounded-full border ${statusTone(settings.lastConnectionStatus)}`}>
          {settings.lastConnectionStatus === 'success' ? '最近连接成功' : settings.lastConnectionStatus === 'failed' ? '最近连接失败' : '尚未测试'}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <input
              value={appId}
              onChange={(event) => setAppId(event.target.value)}
              placeholder="飞书 App ID"
              className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none"
              disabled={!canManage}
            />
            <input
              value={botName}
              onChange={(event) => setBotName(event.target.value)}
              placeholder="机器人称呼，例如 罗茜茜"
              className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none"
              disabled={!canManage}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-[180px_1fr_auto] gap-4">
            <select
              value={receiveIdType}
              onChange={(event) => setReceiveIdType(event.target.value as FeishuReceiveIdType)}
              className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none"
              disabled={!canManage}
            >
              {Object.entries(RECEIVE_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  接收方类型：{label}
                </option>
              ))}
            </select>
            <input
              value={receiverId}
              onChange={(event) => setReceiverId(event.target.value)}
              placeholder={receiverPlaceholder}
              className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none"
              disabled={!canManage}
            />
            {receiveIdType === 'email' && defaultReceiverEmail ? (
              <button
                type="button"
                className="px-4 py-3 rounded-2xl border border-blue-100 bg-blue-50 text-[12px] font-bold text-[#5B7BFE] disabled:opacity-50"
                onClick={() => setReceiverId(defaultReceiverEmail)}
                disabled={!canManage}
              >
                使用当前邮箱
              </button>
            ) : (
              <div />
            )}
          </div>

          <div className="rounded-2xl border border-gray-100 bg-gray-50 px-4 py-4">
            <div className="flex items-center gap-2 mb-3">
              <KeyRound size={15} className="text-slate-500" />
              <p className="text-[12px] font-bold text-gray-900">App Secret</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-3">
              <input
                type="password"
                value={appSecret}
                onChange={(event) => setAppSecret(event.target.value)}
                placeholder={settings.hasAppSecret ? '已保存到钥匙串；如要更新可重新输入' : '请输入飞书 App Secret'}
                className="w-full bg-white border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none"
                disabled={!canManage}
              />
              <button
                type="button"
                className="px-4 py-3 rounded-2xl border border-gray-200 bg-white text-[12px] font-bold text-gray-600 disabled:opacity-50"
                onClick={() => void handleClearSecret()}
                disabled={!canManage || (!settings.hasAppSecret && !appSecret.trim()) || isSaving || isTesting}
              >
                清空密钥
              </button>
            </div>
            <p className="text-[12px] text-gray-500 mt-3 leading-relaxed">
              {settings.hasAppSecret ? `当前密钥来源：${settings.secretSource}` : '当前还没有可用密钥。'}
              {settings.secretFingerprint ? ` · 指纹 ${settings.secretFingerprint}` : ''}
            </p>
          </div>

          <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-4">
            <p className="text-[12px] font-bold text-slate-900">飞书事件回调路径</p>
            <p className="text-[12px] text-slate-700 mt-2 break-all">/api/v1/channels/feishu/events</p>
            <p className="text-[12px] text-slate-500 mt-2 leading-relaxed">
              当前桌面版后端默认只跑在本机 `127.0.0.1`。如果要让飞书真正收到“你是谁？”并自动回复，还需要把这条路径暴露成公网可访问地址。
            </p>
          </div>

          <div className="rounded-2xl border border-dashed border-blue-100 bg-blue-50/70 px-4 py-4 space-y-3">
            <div>
              <p className="text-[12px] font-bold text-slate-900">个人绑定回调 URL（可选）</p>
              <p className="text-[12px] text-slate-500 mt-2 leading-relaxed">
                如果这里留空，系统会优先尝试使用云端 HTTPS 中继来支持手机扫码绑定；只有在没有公网入口时，才会退回当前桌面端本机浏览器授权。需要自定义回调时，再填写飞书后台允许的公网 HTTPS 回调地址。
              </p>
            </div>
            <input
              value={userBindingCallbackUrl}
              onChange={(event) => setUserBindingCallbackUrl(event.target.value)}
              placeholder="https://your-domain.example.com/api/v1/auth/feishu/callback"
              className="w-full bg-white border border-blue-100 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none"
              disabled={!canManage}
            />
            <p className="text-[12px] text-slate-600 break-all">
              当前保存值：{settings.userBindingCallbackUrl || '未单独配置，将优先尝试云端 HTTPS 中继；不可用时再回到本机 http://127.0.0.1:47829/api/v1/auth/feishu/callback'}
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-white border border-gray-200 text-[13px] font-bold text-gray-700 disabled:opacity-50"
              onClick={() => void handleSave()}
              disabled={!canManage || isSaving || isTesting}
            >
              {isSaving ? <RefreshCw size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}
              保存飞书配置
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-[#5B7BFE] text-white text-[13px] font-bold shadow-sm disabled:opacity-50"
              onClick={() => void handleConnectAndSend()}
              disabled={!canManage || isSaving || isTesting || !canSendTestMessage}
            >
              {isTesting ? <RefreshCw size={15} className="animate-spin" /> : <Send size={15} />}
              连接并发测试消息
            </button>
          </div>

          {!canManage && (
            <div className="rounded-2xl border border-amber-100 bg-amber-50 px-4 py-3 text-[12px] text-amber-700">
              当前账号只能查看飞书连接状态，不能修改凭据或发送测试消息。
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className={`rounded-2xl border px-4 py-4 ${statusTone(settings.lastConnectionStatus)}`}>
            <div className="flex items-start gap-3">
              {settings.lastConnectionStatus === 'failed' ? <AlertCircle size={18} /> : <CheckCircle2 size={18} />}
              <div className="min-w-0">
                <p className="text-[13px] font-bold">
                  {settings.lastConnectionStatus === 'success' ? '最近一次连接结果正常' : settings.lastConnectionStatus === 'failed' ? '最近一次连接失败' : '尚未执行连通性测试'}
                </p>
                <p className="text-[12px] mt-1 leading-relaxed">
                  {settings.lastConnectionMessage || '填好 App ID、密钥和接收方标识后，点击“连接并发测试消息”。'}
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-gray-100 bg-gray-50 px-4 py-4 space-y-3">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">接收方</p>
              <p className="text-[13px] font-bold text-gray-900 mt-1">
                {RECEIVE_TYPE_LABELS[receiveIdType]} · {receiverId || '尚未填写'}
              </p>
              <p className="text-[12px] text-gray-500 mt-1">{RECEIVE_TYPE_HINTS[receiveIdType]}</p>
            </div>
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">测试消息文案</p>
              <p className="text-[12px] text-gray-700 mt-1 leading-relaxed">{defaultTestMessage}</p>
            </div>
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">个人绑定回调</p>
              <p className="text-[12px] text-gray-700 mt-1 break-all">
                {settings.userBindingCallbackUrl || '未单独配置，默认回到本机回调'}
              </p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="rounded-2xl bg-white border border-gray-100 px-4 py-3">
                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">最近连接</p>
                <p className="text-[12px] text-gray-700 mt-1">{settings.lastConnectedAt || '尚未连接'}</p>
              </div>
              <div className="rounded-2xl bg-white border border-gray-100 px-4 py-3">
                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">最近发消息</p>
                <p className="text-[12px] text-gray-700 mt-1">{settings.lastTestMessageAt || '尚未发送'}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
~~~

## `src/renderer/components/settings/FeishuOrgIntegrationPanel.tsx`

- 编码: `utf-8`

~~~tsx
import React, { useEffect, useMemo, useState } from 'react';
import { Bot, CheckCircle2, Phone, RefreshCw, ShieldAlert, Users } from 'lucide-react';

import type {
  FeishuDeliveryProfile,
  FeishuDeliveryProfilePayload,
  LocalInputMemoryFeishuIntegration,
  OrgFeishuIntegration,
  OrgFeishuIntegrationPayload,
  OrgMembershipSummary,
} from '../../../shared/types';

type Props = {
  sessionMode: 'local' | 'cloud';
  membership: OrgMembershipSummary;
  integration: OrgFeishuIntegration;
  deliveryProfile: FeishuDeliveryProfile;
  currentUserName?: string | null;
  saveBusy: boolean;
  savePhoneBusy: boolean;
  rememberedInputs: LocalInputMemoryFeishuIntegration;
  onSaveIntegration: (payload: OrgFeishuIntegrationPayload) => Promise<void>;
  onSaveRememberedInputs: (payload: LocalInputMemoryFeishuIntegration) => Promise<void>;
  onSaveDeliveryProfile: (payload: FeishuDeliveryProfilePayload) => Promise<void>;
  onOpenOrganizationSetup: () => void;
  onOpenCloudAuth: () => void;
};

function statusTone(status: 'idle' | 'success' | 'failed') {
  if (status === 'success') {
    return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  }
  if (status === 'failed') {
    return 'border-rose-100 bg-rose-50 text-rose-700';
  }
  return 'border-slate-100 bg-slate-50 text-slate-600';
}

function deliveryTone(status: FeishuDeliveryProfile['deliveryStatus']) {
  if (status === 'matched') {
    return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  }
  if (status === 'failed') {
    return 'border-rose-100 bg-rose-50 text-rose-700';
  }
  if (status === 'not_found') {
    return 'border-amber-100 bg-amber-50 text-amber-700';
  }
  return 'border-slate-100 bg-slate-50 text-slate-600';
}

export function FeishuOrgIntegrationPanel({
  sessionMode,
  membership,
  integration,
  deliveryProfile,
  currentUserName,
  saveBusy,
  savePhoneBusy,
  rememberedInputs,
  onSaveIntegration,
  onSaveRememberedInputs,
  onSaveDeliveryProfile,
  onOpenOrganizationSetup,
  onOpenCloudAuth,
}: Props) {
  const [appId, setAppId] = useState(integration.appId || rememberedInputs.appId || '');
  const [appSecret, setAppSecret] = useState(rememberedInputs.appSecret || '');
  const [rememberLocalInputs, setRememberLocalInputs] = useState(rememberedInputs.rememberInputs);
  const [mobile, setMobile] = useState(deliveryProfile.mobile || '');

  useEffect(() => {
    setAppId(integration.appId || rememberedInputs.appId || '');
    setAppSecret(rememberedInputs.appSecret || '');
    setRememberLocalInputs(rememberedInputs.rememberInputs);
  }, [
    integration.appId,
    rememberedInputs.appId,
    rememberedInputs.appSecret,
    rememberedInputs.rememberInputs,
  ]);

  useEffect(() => {
    setMobile(deliveryProfile.mobile || '');
  }, [deliveryProfile.mobile]);

  const integrationChanges =
    appId.trim() !== (integration.appId || '')
    || Boolean(appSecret.trim());
  const canConfigureIntegration = sessionMode === 'cloud' && membership.hasOrganization;
  const canSaveIntegration = canConfigureIntegration && integrationChanges && !saveBusy;
  const canSaveDeliveryProfile = sessionMode === 'cloud' && mobile.trim() !== (deliveryProfile.mobile || '') && !savePhoneBusy;

  const integrationHelper = useMemo(() => {
    if (sessionMode !== 'cloud') {
      return '连接云端并加入组织后，才能启用飞书任务提醒。';
    }
    if (!membership.hasOrganization) {
      return '你还没有加入任何组织。飞书提醒依赖组织信息，请先加入组织或创建组织。';
    }
    if (integration.enabled) {
      return '当前组织飞书应用已验证。成员填写飞书手机号后，任务提醒即可自动按手机号匹配发送。';
    }
    return integration.lastValidationMessage || '完成后，软件会按成员填写的飞书手机号自动发送任务提醒。';
  }, [integration.lastValidationMessage, membership.hasOrganization, sessionMode]);

  const deliveryHelper = useMemo(() => {
    if (sessionMode !== 'cloud') {
      return '先连接云端，再填写你的飞书接收手机号。';
    }
    if (!membership.hasOrganization) {
      return '先加入或创建组织，再填写你的飞书接收手机号。';
    }
    if (!integration.enabled) {
      return '当前组织尚未接通飞书。接通后，软件才会按手机号匹配并发送任务提醒。';
    }
    return deliveryProfile.blockedReason
      || '请填写你登录飞书时使用的手机号。软件会按这个手机号匹配你的飞书身份并发送任务提醒。';
  }, [deliveryProfile.blockedReason, integration.enabled, membership.hasOrganization, sessionMode]);

  const handleSaveIntegration = async () => {
    const payload: OrgFeishuIntegrationPayload = {
      appId: appId.trim(),
      appSecret: appSecret.trim() || undefined,
    };
    await onSaveIntegration(payload);
    await onSaveRememberedInputs({
      rememberInputs: rememberLocalInputs,
      appId: payload.appId || '',
      appSecret: payload.appSecret || '',
    });
    if (!rememberLocalInputs) {
      setAppSecret('');
    }
  };

  const handleSaveDeliveryProfile = async () => {
    await onSaveDeliveryProfile({ mobile: mobile.trim() || null });
  };

  return (
    <div className="space-y-6">
      <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm space-y-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-[16px] font-bold text-gray-900 flex items-center gap-2">
              <Bot size={17} />
              组织飞书接入
            </h2>
            <p className="text-[12px] text-gray-500 mt-1 leading-relaxed">
              这一步配置的是整个组织共用的飞书应用。验证通过后，软件会按成员填写的飞书手机号自动发送任务提醒。
            </p>
          </div>
          <div className={`text-[11px] font-bold px-3 py-1.5 rounded-full border ${statusTone(integration.lastValidationStatus)}`}>
            {integration.enabled ? '组织已接通飞书' : '组织尚未接通飞书'}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <input
            value={appId}
            onChange={(event) => setAppId(event.target.value)}
            placeholder="飞书 App ID"
            className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none disabled:text-gray-400 disabled:bg-gray-100"
            disabled={!canConfigureIntegration}
          />
          <input
            type="password"
            value={appSecret}
            onChange={(event) => setAppSecret(event.target.value)}
            placeholder={integration.hasAppSecret ? '已保存组织密钥；如需更新请重新输入' : '飞书 App Secret'}
            className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none disabled:text-gray-400 disabled:bg-gray-100"
            disabled={!canConfigureIntegration}
          />
        </div>

        <label className="flex items-center gap-2 text-[12px] font-medium text-gray-700">
          <input
            type="checkbox"
            checked={rememberLocalInputs}
            onChange={(event) => setRememberLocalInputs(event.target.checked)}
          />
          在本机记住 App ID / App Secret
        </label>

        <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
          <p className="text-[12px] font-bold text-slate-900">
            当前组织：{membership.organizationName || '尚未加入组织'}
          </p>
          <p className="text-[12px] text-slate-600 mt-2 leading-6">{integrationHelper}</p>
          {integration.configuredBy && integration.configuredAt ? (
            <p className="text-[11px] text-slate-400 mt-2">
              最近配置：{integration.configuredBy} · {integration.configuredAt}
            </p>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => {
              if (sessionMode !== 'cloud') {
                onOpenCloudAuth();
                return;
              }
              if (!membership.hasOrganization) {
                onOpenOrganizationSetup();
                return;
              }
              void handleSaveIntegration();
            }}
            disabled={sessionMode === 'cloud' && membership.hasOrganization ? !canSaveIntegration : false}
            className="inline-flex items-center gap-2 rounded-2xl px-5 py-3 text-[13px] font-bold text-white bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saveBusy ? <RefreshCw size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
            {sessionMode !== 'cloud'
              ? '连接云端'
              : membership.hasOrganization
                ? '验证并保存组织飞书接入'
                : '加入 / 创建组织'}
          </button>
        </div>
      </div>

      <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm space-y-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-[16px] font-bold text-gray-900 flex items-center gap-2">
              <Phone size={17} />
              我的飞书接收手机号
            </h2>
            <p className="text-[12px] text-gray-500 mt-1 leading-relaxed">
              请填写你登录飞书时使用的手机号。软件会按这个手机号匹配你的飞书身份并发送任务提醒；如果第一次填错，后面也可以随时修改。
            </p>
          </div>
          <div className={`text-[11px] font-bold px-3 py-1.5 rounded-full border ${deliveryTone(deliveryProfile.deliveryStatus)}`}>
            {deliveryProfile.deliveryStatusLabel}
          </div>
        </div>

        <input
          value={mobile}
          onChange={(event) => setMobile(event.target.value)}
          placeholder="飞书账号对应手机号"
          className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none disabled:text-gray-400 disabled:bg-gray-100"
          disabled={sessionMode !== 'cloud'}
        />

        <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
          <p className="text-[12px] font-bold text-slate-900 flex items-center gap-2">
            <Users size={14} />
            当前成员：{currentUserName || '当前账号'}
          </p>
          <p className="text-[12px] text-slate-600 mt-2 leading-6">{deliveryHelper}</p>
          {deliveryProfile.lastVerifiedAt ? (
            <p className="text-[11px] text-slate-400 mt-2">
              最近校验：{deliveryProfile.lastVerifiedAt}
              {deliveryProfile.receiveId ? ` · 已匹配 ${deliveryProfile.receiveId}` : ''}
            </p>
          ) : null}
          {deliveryProfile.lastError ? (
            <p className="text-[11px] text-rose-500 mt-2">{deliveryProfile.lastError}</p>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => {
              if (sessionMode !== 'cloud') {
                onOpenCloudAuth();
                return;
              }
              if (!membership.hasOrganization) {
                onOpenOrganizationSetup();
                return;
              }
              if (!integration.enabled) {
                return;
              }
              void handleSaveDeliveryProfile();
            }}
            disabled={
              sessionMode === 'cloud'
                ? !membership.hasOrganization || !integration.enabled || !canSaveDeliveryProfile
                : false
            }
            className="inline-flex items-center gap-2 rounded-2xl px-5 py-3 text-[13px] font-bold text-white bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {savePhoneBusy ? <RefreshCw size={16} className="animate-spin" /> : <ShieldAlert size={16} />}
            {sessionMode !== 'cloud'
              ? '连接云端'
              : !membership.hasOrganization
                ? '加入 / 创建组织'
                : !integration.enabled
                  ? '先完成组织飞书接入'
                  : (deliveryProfile.mobile ? '更新飞书手机号' : '保存飞书手机号')}
          </button>
        </div>
      </div>
    </div>
  );
}
~~~

## `src/renderer/components/settings/OrganizationModelSettingsPanel.tsx`

- 编码: `utf-8`

~~~tsx
import { useEffect, useMemo, useState } from 'react';

import type {
  DepartmentOption,
  EmployeeRecord,
  OrgDepartmentPlanItemSettings,
  OrgDepartmentPlanSettings,
  OrgDepartmentPlanItemStatus,
  OrgDepartmentPlanStatus,
  OrgEmployeeBindingSettings,
  OrgFocusItemSettings,
  OrgFocusPriority,
  OrgFocusStatus,
  OrgModelSettings,
  OrgRoleProcessTemplateSettings,
  OrgRoleLevel,
  OrgRuleActorScope,
  OrgTaskControlLevel,
  OrgTaskEditScope,
  OrgWorkflowTriggerType,
} from '../../../shared/types';

const ROLE_LEVEL_OPTIONS: Array<{ value: OrgRoleLevel; label: string }> = [
  { value: 'organization_lead', label: '机构负责人' },
  { value: 'department_lead', label: '部门负责人' },
  { value: 'supervisor', label: '主管' },
  { value: 'employee', label: '员工' },
];

const TASK_EDIT_SCOPE_OPTIONS: Array<{ value: OrgTaskEditScope; label: string }> = [
  { value: 'self', label: '仅本人' },
  { value: 'manager', label: '直属上级' },
  { value: 'department', label: '部门层' },
  { value: 'organization', label: '机构层' },
];

const RULE_SCOPE_OPTIONS: Array<{ value: OrgRuleActorScope; label: string }> = [
  { value: 'assignee', label: '负责人' },
  { value: 'creator', label: '创建人' },
  { value: 'manager', label: '直属上级' },
  { value: 'department_lead', label: '部门负责人' },
  { value: 'organization_lead', label: '机构负责人' },
];

const CONTROL_LEVEL_OPTIONS: Array<{ value: OrgTaskControlLevel; label: string }> = [
  { value: 'normal', label: '普通' },
  { value: 'leader_control', label: 'leader 控制' },
  { value: 'department_control', label: '部门控制' },
  { value: 'organization_control', label: '机构控制' },
];

const WORKFLOW_TRIGGER_OPTIONS: Array<{ value: OrgWorkflowTriggerType; label: string }> = [
  { value: 'weekly_followup', label: '周会后推进' },
  { value: 'task_created', label: '任务创建后' },
  { value: 'meeting_closed', label: '会议结束后' },
  { value: 'client_update', label: '客户状态更新后' },
  { value: 'manual', label: '手动触发' },
];

const FOCUS_PRIORITY_OPTIONS: Array<{ value: OrgFocusPriority; label: string }> = [
  { value: 'high', label: '高优先级' },
  { value: 'medium', label: '中优先级' },
  { value: 'low', label: '低优先级' },
];

const FOCUS_STATUS_OPTIONS: Array<{ value: OrgFocusStatus; label: string }> = [
  { value: 'active', label: '进行中' },
  { value: 'draft', label: '草稿' },
  { value: 'paused', label: '暂停' },
  { value: 'done', label: '完成' },
];

const PLAN_STATUS_OPTIONS: Array<{ value: OrgDepartmentPlanStatus; label: string }> = [
  { value: 'active', label: '进行中' },
  { value: 'draft', label: '草稿' },
  { value: 'closed', label: '已关闭' },
];

const PLAN_ITEM_STATUS_OPTIONS: Array<{ value: OrgDepartmentPlanItemStatus; label: string }> = [
  { value: 'active', label: '进行中' },
  { value: 'paused', label: '暂停' },
  { value: 'done', label: '已完成' },
  { value: 'dropped', label: '已放弃' },
];

function nextUiId(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function toMultiline(values: string[]) {
  return values.join('\n');
}

function fromMultiline(value: string) {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean);
}

type Props = {
  value: OrgModelSettings;
  departmentCatalog: DepartmentOption[];
  employees: EmployeeRecord[];
  canEdit: boolean;
  isSaving?: boolean;
  forcedTab?: OrgModelTab | null;
  hideTabNavigation?: boolean;
  title?: string;
  helper?: string;
  onChange: (next: OrgModelSettings) => void;
  onSave: () => void;
};

export type OrgModelTab = 'overview' | 'departments' | 'people' | 'rules';

function emptyBindingForUser(user: EmployeeRecord): OrgEmployeeBindingSettings {
  return {
    userId: user.id,
    departmentId: user.departmentId || null,
    primaryRoleId: null,
    managerUserId: null,
    isManager: false,
    projectRoleLabels: [],
    currentFocus: '',
    taskEditScope: 'self',
    canApproveTasks: false,
    canReassignTasks: false,
    canChangeDeadline: false,
    updatedAt: '',
  };
}

export function OrganizationModelSettingsPanel({
  value,
  departmentCatalog,
  employees,
  canEdit,
  isSaving = false,
  forcedTab = null,
  hideTabNavigation = false,
  title = '组织模型层（P0）',
  helper = '先搭“组织关系 + 岗位职责 + 汇报线 + 权限规则”的最小底座，让任务、周计划和周总结能读到真实组织背景。',
  onChange,
  onSave,
}: Props) {
  const [tab, setTab] = useState<OrgModelTab>(forcedTab || 'overview');

  useEffect(() => {
    if (forcedTab) {
      setTab(forcedTab);
    }
  }, [forcedTab]);

  const employeeOptions = useMemo(
    () => [...employees].sort((a, b) => a.fullName.localeCompare(b.fullName, 'zh-Hans-CN')),
    [employees],
  );

  const departmentOptions = useMemo(() => {
    if (value.departments.length > 0) {
      return value.departments.map((item) => ({ id: item.id, name: item.name, color: item.color }));
    }
    return departmentCatalog;
  }, [departmentCatalog, value.departments]);

  const roleOptions = useMemo(() => [...value.roles].sort((a, b) => a.sortOrder - b.sortOrder || a.name.localeCompare(b.name, 'zh-Hans-CN')), [value.roles]);
  const bindingByUserId = useMemo(() => new Map(value.bindings.map((item) => [item.userId, item])), [value.bindings]);

  const updateOrganization = (patch: Partial<OrgModelSettings['organization']>) => {
    onChange({ ...value, organization: { ...value.organization, ...patch } });
  };

  const updateDepartment = (departmentId: string, updater: (current: OrgModelSettings['departments'][number]) => OrgModelSettings['departments'][number]) => {
    onChange({
      ...value,
      departments: value.departments.map((item) => (item.id === departmentId ? updater(item) : item)),
    });
  };

  const updateRole = (roleId: string, updater: (current: OrgModelSettings['roles'][number]) => OrgModelSettings['roles'][number]) => {
    onChange({
      ...value,
      roles: value.roles.map((item) => (item.id === roleId ? updater(item) : item)),
    });
  };

  const ensureBinding = (user: EmployeeRecord) => bindingByUserId.get(user.id) || emptyBindingForUser(user);

  const updateBinding = (user: EmployeeRecord, patch: Partial<OrgEmployeeBindingSettings>) => {
    const existing = bindingByUserId.get(user.id);
    const nextBinding = { ...(existing || emptyBindingForUser(user)), ...patch };
    onChange({
      ...value,
      bindings: existing ? value.bindings.map((item) => (item.userId === user.id ? nextBinding : item)) : [...value.bindings, nextBinding],
    });
  };

  const updateReportingLine = (lineId: string, updater: (current: OrgModelSettings['reportingLines'][number]) => OrgModelSettings['reportingLines'][number]) => {
    onChange({
      ...value,
      reportingLines: value.reportingLines.map((item) => (item.id === lineId ? updater(item) : item)),
    });
  };

  const updateRule = (ruleId: string, updater: (current: OrgModelSettings['taskControlRules'][number]) => OrgModelSettings['taskControlRules'][number]) => {
    onChange({
      ...value,
      taskControlRules: value.taskControlRules.map((item) => (item.id === ruleId ? updater(item) : item)),
    });
  };

  const updateProcessTemplate = (
    templateId: string,
    updater: (current: OrgRoleProcessTemplateSettings) => OrgRoleProcessTemplateSettings,
  ) => {
    onChange({
      ...value,
      roleProcessTemplates: value.roleProcessTemplates.map((item) => (item.id === templateId ? updater(item) : item)),
    });
  };

  const updateFocusItem = (
    focusItemId: string,
    updater: (current: OrgFocusItemSettings) => OrgFocusItemSettings,
  ) => {
    onChange({
      ...value,
      focusItems: value.focusItems.map((item) => (item.id === focusItemId ? updater(item) : item)),
    });
  };

  const updateDepartmentPlan = (
    planId: string,
    updater: (current: OrgDepartmentPlanSettings) => OrgDepartmentPlanSettings,
  ) => {
    onChange({
      ...value,
      departmentPlans: value.departmentPlans.map((item) => (item.id === planId ? updater(item) : item)),
    });
  };

  const updateDepartmentPlanItem = (
    planId: string,
    itemId: string,
    updater: (current: OrgDepartmentPlanItemSettings) => OrgDepartmentPlanItemSettings,
  ) => {
    updateDepartmentPlan(planId, (plan) => ({
      ...plan,
      items: plan.items.map((item) => (item.id === itemId ? updater(item) : item)),
    }));
  };

  const addRole = () => {
    onChange({
      ...value,
      roles: [
        ...value.roles,
        {
          id: nextUiId('role'),
          departmentId: departmentOptions[0]?.id || null,
          name: '',
          level: 'employee',
          managerRoleId: null,
          isManager: false,
          goal: '',
          responsibilities: [],
          shouldAvoid: [],
          collaborationRoleIds: [],
          taskEditScope: 'self',
          canApproveTasks: false,
          canReassignTasks: false,
          canChangeDeadline: false,
          sortOrder: value.roles.length,
          active: true,
          updatedAt: '',
        },
      ],
    });
  };

  const addFocusItem = () => {
    onChange({
      ...value,
      focusItems: [
        ...value.focusItems,
        {
          id: nextUiId('focus'),
          periodKey: '',
          title: '',
          statement: '',
          ownerUserId: null,
          priority: 'medium',
          status: 'draft',
          evidenceKeywords: [],
          updatedAt: '',
        },
      ],
    });
  };

  const addDepartmentPlan = (departmentId: string | null = departmentOptions[0]?.id || null) => {
    onChange({
      ...value,
      departmentPlans: [
        ...value.departmentPlans,
        {
          id: nextUiId('plan'),
          departmentId,
          weekLabel: '',
          ownerUserId: null,
          summary: '',
          majorRisks: [],
          dependencies: [],
          status: 'draft',
          items: [],
          updatedAt: '',
        },
      ],
    });
  };

  const addDepartmentPlanItem = (planId: string) => {
    updateDepartmentPlan(planId, (plan) => ({
      ...plan,
      items: [
        ...plan.items,
        {
          id: nextUiId('plan_item'),
          focusItemId: null,
          title: '',
          statement: '',
          ownerUserId: null,
          status: 'active',
          expectedOutput: '',
          sortOrder: plan.items.length,
          updatedAt: '',
        },
      ],
    }));
  };

  const addReportingLine = () => {
    if (employeeOptions.length < 2) return;
    onChange({
      ...value,
      reportingLines: [
        ...value.reportingLines,
        {
          id: nextUiId('line'),
          managerUserId: employeeOptions[0].id,
          reportUserId: employeeOptions[1].id,
          lineType: 'business',
          approvesTasks: true,
          canAdjustTasks: false,
          canChangeDeadline: false,
          canReassignTasks: false,
          isCrossDepartmentApprover: false,
          active: true,
          updatedAt: '',
        },
      ],
    });
  };

  const addRule = () => {
    onChange({
      ...value,
      taskControlRules: [
        ...value.taskControlRules,
        {
          id: nextUiId('rule'),
          name: '',
          controlLevel: 'normal',
          departmentId: null,
          roleTemplateId: null,
          contentEditableBy: 'assignee',
          deadlineEditableBy: 'manager',
          ownerEditableBy: 'manager',
          cancellableBy: 'manager',
          requireCollabConfirmation: false,
          defaultApproverUserId: null,
          active: true,
          updatedAt: '',
        },
      ],
    });
  };

  const addProcessTemplate = () => {
    onChange({
      ...value,
      roleProcessTemplates: [
        ...value.roleProcessTemplates,
        {
          id: nextUiId('process'),
          roleTemplateId: roleOptions[0]?.id || null,
          name: '',
          triggerType: 'manual',
          triggerCondition: '',
          keySteps: [],
          collaborationStep: '',
          approvalStep: '',
          outputArtifact: '',
          commonBlockers: [],
          active: true,
          updatedAt: '',
        },
      ],
    });
  };

  return (
    <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[16px] font-bold text-gray-900">{title}</h2>
          <p className="text-[12px] text-gray-500 mt-1">{helper}</p>
        </div>
        <button
          type="button"
          className="rounded-2xl bg-[#5B7BFE] px-4 py-2 text-[12px] font-bold text-white shadow-[0_10px_30px_rgba(91,123,254,0.24)] disabled:cursor-not-allowed disabled:opacity-50"
          onClick={onSave}
          disabled={!canEdit || isSaving}
        >
          {isSaving ? '保存中...' : '保存组织模型'}
        </button>
      </div>

      {!hideTabNavigation && <div className="flex flex-wrap gap-2">
        {[
          ['overview', '组织总览'],
          ['departments', '部门与岗位'],
          ['people', '人员配置'],
          ['rules', '流程与权限'],
        ].map(([key, label]) => {
          const active = tab === key;
          return (
            <button
              key={key}
              type="button"
              className={`rounded-full px-4 py-2 text-[12px] font-bold transition ${active ? 'bg-[#111827] text-white' : 'bg-gray-50 text-gray-500 border border-gray-200'}`}
              onClick={() => setTab(key as OrgModelTab)}
            >
              {label}
            </button>
          );
        })}
      </div>}

      {tab === 'overview' && (
        <div className="space-y-5">
          <div className="rounded-[28px] border border-gray-200 bg-gray-50/70 p-5 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <input
                value={value.organization.name}
                onChange={(event) => updateOrganization({ name: event.target.value })}
                className="rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                placeholder="机构名称"
                disabled={!canEdit}
              />
              <select
                value={value.organization.leaderUserId || ''}
                onChange={(event) => updateOrganization({ leaderUserId: event.target.value || null })}
                className="rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                disabled={!canEdit}
              >
                <option value="">请选择机构负责人</option>
                {employeeOptions.map((employee) => (
                  <option key={employee.id} value={employee.id}>
                    {employee.fullName}
                  </option>
                ))}
              </select>
            </div>
            <textarea
              value={value.organization.annualGoal}
              onChange={(event) => updateOrganization({ annualGoal: event.target.value })}
              className="min-h-[84px] w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] leading-6 outline-none resize-none"
              placeholder="年度目标"
              disabled={!canEdit}
            />
            <textarea
              value={toMultiline(value.organization.quarterlyFocus)}
              onChange={(event) => updateOrganization({ quarterlyFocus: fromMultiline(event.target.value) })}
              className="min-h-[96px] w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] leading-6 outline-none resize-none"
              placeholder="当前季度重点，每行一条"
              disabled={!canEdit}
            />
            <div className="space-y-2">
              <p className="text-[12px] font-bold text-gray-700">管理层名单</p>
              <div className="flex flex-wrap gap-2">
                {employeeOptions.map((employee) => {
                  const active = value.organization.managementUserIds.includes(employee.id);
                  return (
                    <button
                      key={`mgmt:${employee.id}`}
                      type="button"
                      disabled={!canEdit}
                      onClick={() =>
                        updateOrganization({
                          managementUserIds: active
                            ? value.organization.managementUserIds.filter((item) => item !== employee.id)
                            : [...value.organization.managementUserIds, employee.id],
                        })
                      }
                      className={`rounded-full px-3 py-1.5 text-[11px] font-bold transition ${active ? 'bg-[#5B7BFE] text-white' : 'bg-white border border-gray-200 text-gray-600'}`}
                    >
                      {employee.fullName}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="rounded-[28px] border border-gray-200 bg-white p-5 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[14px] font-bold text-gray-900">机构季度重点</p>
                <p className="text-[11px] text-gray-500 mt-1">这些重点会作为机构级背景，供任务挂接和 CEO 总结自动对照。</p>
              </div>
              <button type="button" className="rounded-2xl border border-gray-200 px-3 py-2 text-[12px] font-bold text-gray-600" onClick={addFocusItem} disabled={!canEdit}>
                新增重点
              </button>
            </div>
            <div className="space-y-3">
              {value.focusItems.map((focusItem) => (
                <div key={focusItem.id} className="rounded-[22px] border border-gray-200 bg-gray-50 p-4 space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <input
                      value={focusItem.periodKey}
                      onChange={(event) => updateFocusItem(focusItem.id, (current) => ({ ...current, periodKey: event.target.value }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      placeholder="周期，例如 2026-Q1"
                      disabled={!canEdit}
                    />
                    <input
                      value={focusItem.title}
                      onChange={(event) => updateFocusItem(focusItem.id, (current) => ({ ...current, title: event.target.value }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      placeholder="重点标题"
                      disabled={!canEdit}
                    />
                    <select
                      value={focusItem.priority}
                      onChange={(event) => updateFocusItem(focusItem.id, (current) => ({ ...current, priority: event.target.value as OrgFocusPriority }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      {FOCUS_PRIORITY_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                    <select
                      value={focusItem.status}
                      onChange={(event) => updateFocusItem(focusItem.id, (current) => ({ ...current, status: event.target.value as OrgFocusStatus }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      {FOCUS_STATUS_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <select
                      value={focusItem.ownerUserId || ''}
                      onChange={(event) => updateFocusItem(focusItem.id, (current) => ({ ...current, ownerUserId: event.target.value || null }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      <option value="">未指定负责人</option>
                      {employeeOptions.map((employee) => (
                        <option key={employee.id} value={employee.id}>{employee.fullName}</option>
                      ))}
                    </select>
                    <input
                      value={focusItem.statement}
                      onChange={(event) => updateFocusItem(focusItem.id, (current) => ({ ...current, statement: event.target.value }))}
                      className="md:col-span-2 rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      placeholder="一句话说明这条机构重点"
                      disabled={!canEdit}
                    />
                  </div>
                  <textarea
                    value={toMultiline(focusItem.evidenceKeywords)}
                    onChange={(event) => updateFocusItem(focusItem.id, (current) => ({ ...current, evidenceKeywords: fromMultiline(event.target.value) }))}
                    className="min-h-[74px] w-full rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] leading-6 outline-none resize-none"
                    placeholder="证据关键词，每行一条"
                    disabled={!canEdit}
                  />
                </div>
              ))}
              {value.focusItems.length === 0 && (
                <div className="rounded-[22px] border border-dashed border-gray-200 bg-gray-50 px-4 py-8 text-center text-[12px] text-gray-400">
                  还没有机构季度重点。建议先录入本季度最重要的 3-5 条战略主线。
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {tab === 'departments' && (
        <div className="space-y-5">
          {value.departments.map((department) => (
            <div key={department.id} className="rounded-[28px] border border-gray-200 bg-gray-50/70 p-5 space-y-4">
              <div className="flex items-center gap-3">
                <span className="h-3 w-3 rounded-full" style={{ backgroundColor: department.color }} />
                <div>
                  <p className="text-[14px] font-bold text-gray-900">{department.name}</p>
                  <p className="text-[11px] text-gray-500 mt-1">部门使命、季度重点、核心协作部门和岗位模板。</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <select
                  value={department.leaderUserId || ''}
                  onChange={(event) => updateDepartment(department.id, (current) => ({ ...current, leaderUserId: event.target.value || null }))}
                  className="rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                  disabled={!canEdit}
                >
                  <option value="">请选择部门负责人</option>
                  {employeeOptions.map((employee) => (
                    <option key={employee.id} value={employee.id}>
                      {employee.fullName}
                    </option>
                  ))}
                </select>
                <label className="rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium flex items-center justify-between">
                  启用部门
                  <input
                    type="checkbox"
                    checked={department.active}
                    onChange={(event) => updateDepartment(department.id, (current) => ({ ...current, active: event.target.checked }))}
                    disabled={!canEdit}
                  />
                </label>
              </div>

              <textarea
                value={department.mission}
                onChange={(event) => updateDepartment(department.id, (current) => ({ ...current, mission: event.target.value }))}
                className="min-h-[76px] w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] leading-6 outline-none resize-none"
                placeholder="部门使命"
                disabled={!canEdit}
              />
              <textarea
                value={toMultiline(department.quarterlyFocus)}
                onChange={(event) => updateDepartment(department.id, (current) => ({ ...current, quarterlyFocus: fromMultiline(event.target.value) }))}
                className="min-h-[90px] w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] leading-6 outline-none resize-none"
                placeholder="部门季度重点，每行一条"
                disabled={!canEdit}
              />

              <div className="space-y-2">
                <p className="text-[12px] font-bold text-gray-700">核心协作部门</p>
                <div className="flex flex-wrap gap-2">
                  {departmentOptions
                    .filter((option) => option.id !== department.id)
                    .map((option) => {
                      const active = department.collaborationDepartmentIds.includes(option.id);
                      return (
                        <button
                          key={`${department.id}:${option.id}`}
                          type="button"
                          disabled={!canEdit}
                          onClick={() =>
                            updateDepartment(department.id, (current) => ({
                              ...current,
                              collaborationDepartmentIds: active
                                ? current.collaborationDepartmentIds.filter((item) => item !== option.id)
                                : [...current.collaborationDepartmentIds, option.id],
                            }))
                          }
                          className={`rounded-full px-3 py-1.5 text-[11px] font-bold transition ${active ? 'bg-emerald-500 text-white' : 'bg-white border border-gray-200 text-gray-600'}`}
                        >
                          {option.name}
                        </button>
                      );
                    })}
                </div>
              </div>
            </div>
          ))}

          <div className="rounded-[28px] border border-gray-200 bg-white p-5 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[14px] font-bold text-gray-900">部门周计划</p>
                <p className="text-[11px] text-gray-500 mt-1">部门负责人每周维护 3-5 条重点计划，后续任务会自动尝试挂接到这些计划项。</p>
              </div>
              <button type="button" className="rounded-2xl border border-gray-200 px-3 py-2 text-[12px] font-bold text-gray-600" onClick={() => addDepartmentPlan()} disabled={!canEdit}>
                新增部门计划
              </button>
            </div>
            <div className="space-y-4">
              {value.departmentPlans.map((plan) => (
                <div key={plan.id} className="rounded-[22px] border border-gray-200 bg-gray-50 p-4 space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <select
                      value={plan.departmentId || ''}
                      onChange={(event) => updateDepartmentPlan(plan.id, (current) => ({ ...current, departmentId: event.target.value || null }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      <option value="">请选择部门</option>
                      {departmentOptions.map((option) => (
                        <option key={option.id} value={option.id}>{option.name}</option>
                      ))}
                    </select>
                    <input
                      value={plan.weekLabel}
                      onChange={(event) => updateDepartmentPlan(plan.id, (current) => ({ ...current, weekLabel: event.target.value }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      placeholder="周次，例如 2026-W12"
                      disabled={!canEdit}
                    />
                    <select
                      value={plan.ownerUserId || ''}
                      onChange={(event) => updateDepartmentPlan(plan.id, (current) => ({ ...current, ownerUserId: event.target.value || null }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      <option value="">未指定负责人</option>
                      {employeeOptions.map((employee) => (
                        <option key={employee.id} value={employee.id}>{employee.fullName}</option>
                      ))}
                    </select>
                    <select
                      value={plan.status}
                      onChange={(event) => updateDepartmentPlan(plan.id, (current) => ({ ...current, status: event.target.value as OrgDepartmentPlanStatus }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      {PLAN_STATUS_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                  </div>
                  <textarea
                    value={plan.summary}
                    onChange={(event) => updateDepartmentPlan(plan.id, (current) => ({ ...current, summary: event.target.value }))}
                    className="min-h-[74px] w-full rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] leading-6 outline-none resize-none"
                    placeholder="本周部门计划摘要"
                    disabled={!canEdit}
                  />
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <textarea
                      value={toMultiline(plan.majorRisks)}
                      onChange={(event) => updateDepartmentPlan(plan.id, (current) => ({ ...current, majorRisks: fromMultiline(event.target.value) }))}
                      className="min-h-[84px] rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] leading-6 outline-none resize-none"
                      placeholder="主要风险，每行一条"
                      disabled={!canEdit}
                    />
                    <textarea
                      value={toMultiline(plan.dependencies)}
                      onChange={(event) => updateDepartmentPlan(plan.id, (current) => ({ ...current, dependencies: fromMultiline(event.target.value) }))}
                      className="min-h-[84px] rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] leading-6 outline-none resize-none"
                      placeholder="依赖 / 支持需求，每行一条"
                      disabled={!canEdit}
                    />
                  </div>
                  <div className="rounded-[18px] border border-gray-200 bg-white p-3 space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-[12px] font-bold text-gray-800">计划项</p>
                      <button type="button" className="rounded-xl border border-gray-200 px-3 py-1.5 text-[11px] font-bold text-gray-600" onClick={() => addDepartmentPlanItem(plan.id)} disabled={!canEdit}>
                        新增计划项
                      </button>
                    </div>
                    <div className="space-y-3">
                      {plan.items.map((item) => (
                        <div key={item.id} className="rounded-[16px] border border-gray-200 bg-gray-50 p-3 space-y-3">
                          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                            <input
                              value={item.title}
                              onChange={(event) => updateDepartmentPlanItem(plan.id, item.id, (current) => ({ ...current, title: event.target.value }))}
                              className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                              placeholder="计划项标题"
                              disabled={!canEdit}
                            />
                            <select
                              value={item.focusItemId || ''}
                              onChange={(event) => updateDepartmentPlanItem(plan.id, item.id, (current) => ({ ...current, focusItemId: event.target.value || null }))}
                              className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                              disabled={!canEdit}
                            >
                              <option value="">未挂机构重点</option>
                              {value.focusItems.map((focusItem) => (
                                <option key={focusItem.id} value={focusItem.id}>{focusItem.title || focusItem.id}</option>
                              ))}
                            </select>
                            <select
                              value={item.ownerUserId || ''}
                              onChange={(event) => updateDepartmentPlanItem(plan.id, item.id, (current) => ({ ...current, ownerUserId: event.target.value || null }))}
                              className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                              disabled={!canEdit}
                            >
                              <option value="">未指定负责人</option>
                              {employeeOptions.map((employee) => (
                                <option key={employee.id} value={employee.id}>{employee.fullName}</option>
                              ))}
                            </select>
                            <select
                              value={item.status}
                              onChange={(event) => updateDepartmentPlanItem(plan.id, item.id, (current) => ({ ...current, status: event.target.value as OrgDepartmentPlanItemStatus }))}
                              className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                              disabled={!canEdit}
                            >
                              {PLAN_ITEM_STATUS_OPTIONS.map((option) => (
                                <option key={option.value} value={option.value}>{option.label}</option>
                              ))}
                            </select>
                          </div>
                          <input
                            value={item.statement}
                            onChange={(event) => updateDepartmentPlanItem(plan.id, item.id, (current) => ({ ...current, statement: event.target.value }))}
                            className="w-full rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                            placeholder="一句话说明计划项要解决什么"
                            disabled={!canEdit}
                          />
                          <input
                            value={item.expectedOutput}
                            onChange={(event) => updateDepartmentPlanItem(plan.id, item.id, (current) => ({ ...current, expectedOutput: event.target.value }))}
                            className="w-full rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                            placeholder="预期产出"
                            disabled={!canEdit}
                          />
                        </div>
                      ))}
                      {plan.items.length === 0 && (
                        <div className="rounded-[16px] border border-dashed border-gray-200 bg-gray-50 px-4 py-6 text-center text-[12px] text-gray-400">
                          还没有计划项。建议每周保持 3-5 条重点项，并尽量关联到机构季度重点。
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              {value.departmentPlans.length === 0 && (
                <div className="rounded-[22px] border border-dashed border-gray-200 bg-gray-50 px-4 py-8 text-center text-[12px] text-gray-400">
                  还没有部门周计划。保存后，任务会自动尝试挂接到对应部门的计划项。
                </div>
              )}
            </div>
          </div>

          <div className="rounded-[28px] border border-gray-200 bg-white p-5 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[14px] font-bold text-gray-900">岗位模板</p>
                <p className="text-[11px] text-gray-500 mt-1">每个岗位尽量只保留结构化短字段，后面 AI 才能拿它判断职责偏离。</p>
              </div>
              <button type="button" className="rounded-2xl border border-gray-200 px-3 py-2 text-[12px] font-bold text-gray-600" onClick={addRole} disabled={!canEdit}>
                新增岗位
              </button>
            </div>
            <div className="space-y-4">
              {roleOptions.map((role) => (
                <div key={role.id} className="rounded-[22px] border border-gray-200 bg-gray-50 p-4 space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <input
                      value={role.name}
                      onChange={(event) => updateRole(role.id, (current) => ({ ...current, name: event.target.value }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      placeholder="岗位名称"
                      disabled={!canEdit}
                    />
                    <select
                      value={role.departmentId || ''}
                      onChange={(event) => updateRole(role.id, (current) => ({ ...current, departmentId: event.target.value || null }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      <option value="">未绑定部门</option>
                      {departmentOptions.map((option) => (
                        <option key={option.id} value={option.id}>
                          {option.name}
                        </option>
                      ))}
                    </select>
                    <select
                      value={role.level}
                      onChange={(event) => updateRole(role.id, (current) => ({ ...current, level: event.target.value as OrgRoleLevel }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      {ROLE_LEVEL_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    <label className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium flex items-center justify-between">
                      管理岗
                      <input
                        type="checkbox"
                        checked={role.isManager}
                        onChange={(event) => updateRole(role.id, (current) => ({ ...current, isManager: event.target.checked }))}
                        disabled={!canEdit}
                      />
                    </label>
                  </div>
                  <input
                    value={role.goal}
                    onChange={(event) => updateRole(role.id, (current) => ({ ...current, goal: event.target.value }))}
                    className="w-full rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                    placeholder="岗位目标（一句话）"
                    disabled={!canEdit}
                  />
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <textarea
                      value={toMultiline(role.responsibilities)}
                      onChange={(event) => updateRole(role.id, (current) => ({ ...current, responsibilities: fromMultiline(event.target.value) }))}
                      className="min-h-[84px] rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] leading-6 outline-none resize-none"
                      placeholder="主要职责，每行一条"
                      disabled={!canEdit}
                    />
                    <textarea
                      value={toMultiline(role.shouldAvoid)}
                      onChange={(event) => updateRole(role.id, (current) => ({ ...current, shouldAvoid: fromMultiline(event.target.value) }))}
                      className="min-h-[84px] rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] leading-6 outline-none resize-none"
                      placeholder="不该长期承担的事务，每行一条"
                      disabled={!canEdit}
                    />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <select
                      value={role.managerRoleId || ''}
                      onChange={(event) => updateRole(role.id, (current) => ({ ...current, managerRoleId: event.target.value || null }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      <option value="">无上级岗位</option>
                      {roleOptions
                        .filter((option) => option.id !== role.id)
                        .map((option) => (
                          <option key={option.id} value={option.id}>
                            {option.name}
                          </option>
                        ))}
                    </select>
                    <select
                      value={role.taskEditScope}
                      onChange={(event) => updateRole(role.id, (current) => ({ ...current, taskEditScope: event.target.value as OrgTaskEditScope }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      {TASK_EDIT_SCOPE_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    <label className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium flex items-center justify-between">
                      审批任务
                      <input type="checkbox" checked={role.canApproveTasks} onChange={(event) => updateRole(role.id, (current) => ({ ...current, canApproveTasks: event.target.checked }))} disabled={!canEdit} />
                    </label>
                    <label className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium flex items-center justify-between">
                      改负责人 / 改日期
                      <input type="checkbox" checked={role.canReassignTasks || role.canChangeDeadline} onChange={(event) => updateRole(role.id, (current) => ({ ...current, canReassignTasks: event.target.checked, canChangeDeadline: event.target.checked }))} disabled={!canEdit} />
                    </label>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[28px] border border-gray-200 bg-white p-5 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[14px] font-bold text-gray-900">岗位流程模板</p>
                <p className="text-[11px] text-gray-500 mt-1">每个关键岗位先录 2-3 条高频流程，后面 AI 才能判断“卡在流程哪一步”。</p>
              </div>
              <button type="button" className="rounded-2xl border border-gray-200 px-3 py-2 text-[12px] font-bold text-gray-600" onClick={addProcessTemplate} disabled={!canEdit}>
                新增流程
              </button>
            </div>
            <div className="space-y-3">
              {value.roleProcessTemplates.map((template) => (
                <div key={template.id} className="rounded-[22px] border border-gray-200 bg-gray-50 p-4 space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <select
                      value={template.roleTemplateId || ''}
                      onChange={(event) => updateProcessTemplate(template.id, (current) => ({ ...current, roleTemplateId: event.target.value || null }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      <option value="">未绑定岗位</option>
                      {roleOptions.map((role) => (
                        <option key={role.id} value={role.id}>{role.name}</option>
                      ))}
                    </select>
                    <input
                      value={template.name}
                      onChange={(event) => updateProcessTemplate(template.id, (current) => ({ ...current, name: event.target.value }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      placeholder="流程名称"
                      disabled={!canEdit}
                    />
                    <select
                      value={template.triggerType}
                      onChange={(event) => updateProcessTemplate(template.id, (current) => ({ ...current, triggerType: event.target.value as OrgWorkflowTriggerType }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      {WORKFLOW_TRIGGER_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                    <label className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium flex items-center justify-between">
                      启用流程
                      <input
                        type="checkbox"
                        checked={template.active}
                        onChange={(event) => updateProcessTemplate(template.id, (current) => ({ ...current, active: event.target.checked }))}
                        disabled={!canEdit}
                      />
                    </label>
                  </div>
                  <input
                    value={template.triggerCondition}
                    onChange={(event) => updateProcessTemplate(template.id, (current) => ({ ...current, triggerCondition: event.target.value }))}
                    className="w-full rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                    placeholder="触发条件，例如：周会结束后 / 客户会议结束后 / 收到新任务后"
                    disabled={!canEdit}
                  />
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <input
                      value={template.collaborationStep}
                      onChange={(event) => updateProcessTemplate(template.id, (current) => ({ ...current, collaborationStep: event.target.value }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      placeholder="哪一步需要协作"
                      disabled={!canEdit}
                    />
                    <input
                      value={template.approvalStep}
                      onChange={(event) => updateProcessTemplate(template.id, (current) => ({ ...current, approvalStep: event.target.value }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      placeholder="哪一步需要审批"
                      disabled={!canEdit}
                    />
                    <input
                      value={template.outputArtifact}
                      onChange={(event) => updateProcessTemplate(template.id, (current) => ({ ...current, outputArtifact: event.target.value }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      placeholder="产出物"
                      disabled={!canEdit}
                    />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <textarea
                      value={toMultiline(template.keySteps)}
                      onChange={(event) => updateProcessTemplate(template.id, (current) => ({ ...current, keySteps: fromMultiline(event.target.value) }))}
                      className="min-h-[92px] rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] leading-6 outline-none resize-none"
                      placeholder="关键步骤，每行一条"
                      disabled={!canEdit}
                    />
                    <textarea
                      value={toMultiline(template.commonBlockers)}
                      onChange={(event) => updateProcessTemplate(template.id, (current) => ({ ...current, commonBlockers: fromMultiline(event.target.value) }))}
                      className="min-h-[92px] rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] leading-6 outline-none resize-none"
                      placeholder="常见卡点，每行一条"
                      disabled={!canEdit}
                    />
                  </div>
                </div>
              ))}
              {value.roleProcessTemplates.length === 0 && (
                <div className="rounded-[22px] border border-dashed border-gray-200 bg-gray-50 px-4 py-8 text-center text-[12px] text-gray-400">
                  还没有岗位流程模板。建议先给高频岗位录入 2-3 条常见流程。
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {tab === 'people' && (
        <div className="rounded-[28px] border border-gray-200 bg-white p-5 space-y-4">
          <div>
            <p className="text-[14px] font-bold text-gray-900">人员配置</p>
            <p className="text-[11px] text-gray-500 mt-1">一个人绑定一个主岗位，可额外附加项目角色和任务权限覆盖。</p>
          </div>
          <div className="space-y-3">
            {employeeOptions.map((employee) => {
              const binding = ensureBinding(employee);
              const roleCandidates = roleOptions.filter((role) => !binding.departmentId || role.departmentId === binding.departmentId || !role.departmentId);
              return (
                <div key={employee.id} className="rounded-[22px] border border-gray-200 bg-gray-50 p-4 space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-[13px] font-bold text-gray-900">{employee.fullName}</p>
                      <p className="text-[11px] text-gray-500 mt-1">{employee.email}</p>
                    </div>
                    <span className="rounded-full bg-white px-3 py-1 text-[10px] font-bold text-gray-500 border border-gray-200">{employee.primaryRole === 'admin' ? '管理员' : '员工'}</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <select value={binding.departmentId || ''} onChange={(event) => updateBinding(employee, { departmentId: event.target.value || null, primaryRoleId: null })} className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none" disabled={!canEdit}>
                      <option value="">未绑定部门</option>
                      {departmentOptions.map((option) => (
                        <option key={option.id} value={option.id}>
                          {option.name}
                        </option>
                      ))}
                    </select>
                    <select value={binding.primaryRoleId || ''} onChange={(event) => updateBinding(employee, { primaryRoleId: event.target.value || null })} className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none" disabled={!canEdit}>
                      <option value="">未绑定岗位</option>
                      {roleCandidates.map((role) => (
                        <option key={role.id} value={role.id}>
                          {role.name}
                        </option>
                      ))}
                    </select>
                    <select value={binding.managerUserId || ''} onChange={(event) => updateBinding(employee, { managerUserId: event.target.value || null })} className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none" disabled={!canEdit}>
                      <option value="">无直属上级</option>
                      {employeeOptions
                        .filter((candidate) => candidate.id !== employee.id)
                        .map((candidate) => (
                          <option key={candidate.id} value={candidate.id}>
                            {candidate.fullName}
                          </option>
                        ))}
                    </select>
                    <select value={binding.taskEditScope} onChange={(event) => updateBinding(employee, { taskEditScope: event.target.value as OrgTaskEditScope })} className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none" disabled={!canEdit}>
                      {TASK_EDIT_SCOPE_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <input value={binding.currentFocus} onChange={(event) => updateBinding(employee, { currentFocus: event.target.value })} className="w-full rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none" placeholder="当前阶段主责方向" disabled={!canEdit} />
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <label className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium flex items-center justify-between">
                      管理岗
                      <input type="checkbox" checked={binding.isManager} onChange={(event) => updateBinding(employee, { isManager: event.target.checked })} disabled={!canEdit} />
                    </label>
                    <label className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium flex items-center justify-between">
                      审批任务
                      <input type="checkbox" checked={binding.canApproveTasks} onChange={(event) => updateBinding(employee, { canApproveTasks: event.target.checked })} disabled={!canEdit} />
                    </label>
                    <label className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium flex items-center justify-between">
                      改负责人
                      <input type="checkbox" checked={binding.canReassignTasks} onChange={(event) => updateBinding(employee, { canReassignTasks: event.target.checked })} disabled={!canEdit} />
                    </label>
                    <label className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium flex items-center justify-between">
                      改截止日
                      <input type="checkbox" checked={binding.canChangeDeadline} onChange={(event) => updateBinding(employee, { canChangeDeadline: event.target.checked })} disabled={!canEdit} />
                    </label>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {tab === 'rules' && (
        <div className="space-y-5">
          <div className="rounded-[28px] border border-gray-200 bg-white p-5 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[14px] font-bold text-gray-900">汇报线</p>
                <p className="text-[11px] text-gray-500 mt-1">单独结构化出来，后面 AI 才能判断瓶颈是出在谁的节点上。</p>
              </div>
              <button type="button" className="rounded-2xl border border-gray-200 px-3 py-2 text-[12px] font-bold text-gray-600" onClick={addReportingLine} disabled={!canEdit}>
                新增汇报线
              </button>
            </div>
            <div className="space-y-3">
              {value.reportingLines.map((line) => (
                <div key={line.id} className="rounded-[22px] border border-gray-200 bg-gray-50 p-4 space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <select value={line.managerUserId} onChange={(event) => updateReportingLine(line.id, (current) => ({ ...current, managerUserId: event.target.value }))} className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none" disabled={!canEdit}>
                      {employeeOptions.map((employee) => (
                        <option key={employee.id} value={employee.id}>{employee.fullName}</option>
                      ))}
                    </select>
                    <select value={line.reportUserId} onChange={(event) => updateReportingLine(line.id, (current) => ({ ...current, reportUserId: event.target.value }))} className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none" disabled={!canEdit}>
                      {employeeOptions.map((employee) => (
                        <option key={employee.id} value={employee.id}>{employee.fullName}</option>
                      ))}
                    </select>
                    <select value={line.lineType} onChange={(event) => updateReportingLine(line.id, (current) => ({ ...current, lineType: event.target.value as 'business' | 'administrative' }))} className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none" disabled={!canEdit}>
                      <option value="business">业务汇报</option>
                      <option value="administrative">行政汇报</option>
                    </select>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
                    {[
                      ['approvesTasks', '审批任务'],
                      ['canAdjustTasks', '改任务内容'],
                      ['canChangeDeadline', '改截止日'],
                      ['canReassignTasks', '改负责人'],
                      ['isCrossDepartmentApprover', '跨部门确认'],
                    ].map(([key, label]) => (
                      <label key={key} className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium flex items-center justify-between">
                        {label}
                        <input
                          type="checkbox"
                          checked={Boolean(line[key as keyof typeof line])}
                          onChange={(event) => updateReportingLine(line.id, (current) => ({ ...current, [key]: event.target.checked }))}
                          disabled={!canEdit}
                        />
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[28px] border border-gray-200 bg-white p-5 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[14px] font-bold text-gray-900">任务控制规则</p>
                <p className="text-[11px] text-gray-500 mt-1">先明确谁能改内容、改时间、改负责人，而不是一开始就上复杂流程引擎。</p>
              </div>
              <button type="button" className="rounded-2xl border border-gray-200 px-3 py-2 text-[12px] font-bold text-gray-600" onClick={addRule} disabled={!canEdit}>
                新增规则
              </button>
            </div>
            <div className="space-y-3">
              {value.taskControlRules.map((rule) => (
                <div key={rule.id} className="rounded-[22px] border border-gray-200 bg-gray-50 p-4 space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <input value={rule.name} onChange={(event) => updateRule(rule.id, (current) => ({ ...current, name: event.target.value }))} className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none" placeholder="规则名称" disabled={!canEdit} />
                    <select value={rule.controlLevel} onChange={(event) => updateRule(rule.id, (current) => ({ ...current, controlLevel: event.target.value as OrgTaskControlLevel }))} className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none" disabled={!canEdit}>
                      {CONTROL_LEVEL_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                    <select value={rule.departmentId || ''} onChange={(event) => updateRule(rule.id, (current) => ({ ...current, departmentId: event.target.value || null }))} className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none" disabled={!canEdit}>
                      <option value="">全机构</option>
                      {departmentOptions.map((option) => (
                        <option key={option.id} value={option.id}>{option.name}</option>
                      ))}
                    </select>
                    <select value={rule.defaultApproverUserId || ''} onChange={(event) => updateRule(rule.id, (current) => ({ ...current, defaultApproverUserId: event.target.value || null }))} className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none" disabled={!canEdit}>
                      <option value="">无默认审批人</option>
                      {employeeOptions.map((employee) => (
                        <option key={employee.id} value={employee.id}>{employee.fullName}</option>
                      ))}
                    </select>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    {[
                      ['contentEditableBy', '谁可改内容'],
                      ['deadlineEditableBy', '谁可改时间'],
                      ['ownerEditableBy', '谁可改负责人'],
                      ['cancellableBy', '谁可取消任务'],
                    ].map(([key, label]) => (
                      <select
                        key={key}
                        value={rule[key as keyof typeof rule] as string}
                        onChange={(event) => updateRule(rule.id, (current) => ({ ...current, [key]: event.target.value }))}
                        className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                        disabled={!canEdit}
                      >
                        <option value="">{label}</option>
                        {RULE_SCOPE_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>{label}：{option.label}</option>
                        ))}
                      </select>
                    ))}
                  </div>
                  <label className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium flex items-center justify-between">
                    修改任务时需要发起协作确认
                    <input type="checkbox" checked={rule.requireCollabConfirmation} onChange={(event) => updateRule(rule.id, (current) => ({ ...current, requireCollabConfirmation: event.target.checked }))} disabled={!canEdit} />
                  </label>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
~~~

## `src/renderer/components/settings/OrganizationSetupCenter.tsx`

- 编码: `utf-8`

~~~tsx
import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Building2, Check, ChevronLeft, Copy, Plus, Save, Users, X } from 'lucide-react';

import type {
  DepartmentOption,
  EmployeeRecord,
  OrgDepartmentSettings,
  OrgEmployeeBindingSettings,
  OrgModelSettings,
  OrgQuarterKey,
  OrgRoleTemplateSettings,
  OrganizationDnaModule,
} from '../../../shared/types';
import { buildDepartmentInviteCode } from '../../../shared/departmentInvite';

type LinkedSection = 'org_dna' | 'tasks' | 'handbook';

type Props = {
  value: OrgModelSettings;
  organizationDnaModules: OrganizationDnaModule[];
  departmentCatalog: DepartmentOption[];
  employees: EmployeeRecord[];
  canEdit: boolean;
  isSaving?: boolean;
  activeWeekLabel: string;
  initialAdvancedTab?: string | null;
  onChange: (next: OrgModelSettings) => void;
  onSave: (next?: OrgModelSettings) => Promise<void> | void;
  onOpenSection: (section: LinkedSection) => void;
};

type ActiveView = 'tree' | 'codes';

type EditableField = 'name' | 'leadName';

type TreeDepartmentNode = {
  id: string;
  name: string;
  type: 'department';
  leadName: string;
  color: string;
  children: TreePositionNode[];
};

type TreeOrgNode = {
  id: string;
  name: string;
  type: 'org';
  children: TreeDepartmentNode[];
};

type TreePositionNode = {
  id: string;
  name: string;
  type: 'position';
  departmentId: string | null;
};

type LineDefinition = {
  id: string;
  path: string;
};

const DEPARTMENT_COLORS = ['#5B7BFE', '#0EA5E9', '#14B8A6', '#F59E0B', '#EF4444', '#8B5CF6'];

function nextUiId(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function clampPercent(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function buildEmptyQuarterPlan(): OrgDepartmentSettings['quarterPlan'] {
  return {
    year: '',
    quarter: 'Q1' satisfies OrgQuarterKey,
    objective: '',
    deliverables: [],
    successMetrics: [],
    majorRisks: [],
    updatedAt: '',
  };
}

function emptyBinding(userId: string): OrgEmployeeBindingSettings {
  return {
    userId,
    departmentId: null,
    primaryRoleId: null,
    managerUserId: null,
    isManager: false,
    projectRoleLabels: [],
    currentFocus: '',
    taskEditScope: 'self',
    canApproveTasks: false,
    canReassignTasks: false,
    canChangeDeadline: false,
    updatedAt: '',
  };
}

function tint(hexColor: string, suffix = '12') {
  return `${hexColor}${suffix}`;
}

function deriveTree(
  value: OrgModelSettings,
  fallbackOrganizationName: string,
): TreeOrgNode {
  const activeDepartments = value.departments.filter((item) => item.active !== false);
  const activeRoles = value.roles
    .filter((item) => item.active !== false)
    .sort((left, right) => left.sortOrder - right.sortOrder);

  return {
    id: value.organization.organizationId || 'organization-root',
    name: value.organization.name.trim() || fallbackOrganizationName,
    type: 'org',
    children: activeDepartments.map((department) => ({
      id: department.id,
      name: department.name || '未命名部门',
      type: 'department',
      leadName: department.leaderName?.trim() || '待设置',
      color: department.color || DEPARTMENT_COLORS[0],
      children: activeRoles
        .filter((role) => role.departmentId === department.id)
        .map((role) => ({
          id: role.id,
          name: role.name || '未命名岗位',
          type: 'position',
          departmentId: department.id,
        })),
    })),
  };
}

function computeStats(
  value: OrgModelSettings,
  employees: EmployeeRecord[],
) {
  const activeDepartments = value.departments.filter((item) => item.active !== false);
  const activeRoles = value.roles.filter((item) => item.active !== false);
  const activePlans = value.departmentPlans.filter((item) => item.status !== 'closed');
  const activeEmployees = employees.filter((item) => item.accountStatus !== 'disabled');
  const boundMembers = value.bindings.filter((item) => item.primaryRoleId).length;
  const memberCount = Math.max(boundMembers, activeEmployees.filter((item) => item.accountStatus === 'approved' || item.primaryRole === 'admin').length);

  const completenessByDepartment = activeDepartments.map((department) => {
    const roleCount = activeRoles.filter((role) => role.departmentId === department.id).length;
    const planCount = activePlans.filter((plan) => plan.departmentId === department.id).length;
    const memberIds = value.bindings.filter((binding) => binding.departmentId === department.id && binding.primaryRoleId).length;
    const missing = [
      !(department.leaderUserId || department.leaderName?.trim()),
      !department.mission.trim(),
      roleCount === 0,
      memberIds === 0,
      planCount === 0,
    ].filter(Boolean).length;
    return clampPercent(((5 - missing) / 5) * 100);
  });

  const completeness = activeDepartments.length > 0
    ? clampPercent(completenessByDepartment.reduce((sum, item) => sum + item, 0) / activeDepartments.length)
    : 0;

  return [
    { label: '部门', value: `${activeDepartments.length}` },
    { label: '岗位', value: `${activeRoles.length}` },
    { label: '成员', value: `${memberCount}` },
    { label: '计划数', value: `${activePlans.length}` },
    { label: '完整度', value: `${completeness}%` },
  ];
}

function departmentColor(index: number, existing?: string | null) {
  if (existing && existing.trim()) return existing;
  return DEPARTMENT_COLORS[index % DEPARTMENT_COLORS.length];
}

function pickDepartmentLeadRoleId(
  roles: OrgRoleTemplateSettings[],
  departmentId: string,
  fallbackRoleId?: string | null,
) {
  const departmentRoles = roles.filter((role) => role.active !== false && role.departmentId === departmentId);
  const explicitLead = departmentRoles.find((role) => role.level === 'department_lead');
  if (explicitLead) return explicitLead.id;
  const managerRole = departmentRoles.find((role) => role.isManager);
  if (managerRole) return managerRole.id;
  if (fallbackRoleId && departmentRoles.some((role) => role.id === fallbackRoleId)) return fallbackRoleId;
  return fallbackRoleId || null;
}

export function OrganizationSetupCenter({
  value,
  organizationDnaModules,
  departmentCatalog,
  employees,
  canEdit,
  isSaving = false,
  onChange,
  onSave,
}: Props) {
  void organizationDnaModules;
  void departmentCatalog;

  const [activeView, setActiveView] = useState<ActiveView>('tree');
  const [editingNodeId, setEditingNodeId] = useState<string | null>(null);
  const [editingField, setEditingField] = useState<EditableField | null>(null);
  const [editingText, setEditingText] = useState('');
  const [toast, setToast] = useState<string | null>(null);
  const [bulkInviteCopied, setBulkInviteCopied] = useState(false);
  const [lines, setLines] = useState<LineDefinition[]>([]);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const bulkInviteTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const tree = useMemo(
    () => deriveTree(value, '当前组织'),
    [value],
  );
  const stats = useMemo(() => computeStats(value, employees), [employees, value]);
  const activeDepartments = useMemo(() => value.departments.filter((item) => item.active !== false), [value.departments]);
  const activeRoles = useMemo(() => value.roles.filter((item) => item.active !== false), [value.roles]);
  const approvedEmployees = useMemo(
    () => employees.filter((item) => item.accountStatus === 'approved' || item.primaryRole === 'admin'),
    [employees],
  );
  const bindingsByDepartmentId = useMemo(() => {
    const mapping = new Map<string, OrgEmployeeBindingSettings[]>();
    value.bindings.forEach((binding) => {
      if (!binding.departmentId) return;
      const list = mapping.get(binding.departmentId) || [];
      list.push(binding);
      mapping.set(binding.departmentId, list);
    });
    return mapping;
  }, [value.bindings]);

  const employeeById = useMemo(() => new Map(employees.map((item) => [item.id, item])), [employees]);
  const organizationName = value.organization.name.trim() || tree.name || '当前组织';
  const organizationLeader = value.organization.leaderUserId
    ? employeeById.get(value.organization.leaderUserId) || null
    : null;
  const organizationLeaderTitle = organizationLeader?.jobTitle?.trim() || '负责人';
  const organizationLeaderSummary = organizationLeader
    ? `${organizationLeaderTitle} · ${organizationLeader.fullName}`
    : '待绑定负责人';
  const bulkInviteText = useMemo(() => {
    const linesOfText = tree.children.map((department, index) => {
      const inviteCode = buildDepartmentInviteCode(department.id, {
        organizationName,
        departmentName: department.name,
        order: index,
      });
      return `${department.name}：${inviteCode}`;
    });
    return [
      `${organizationName} 各部门邀请码`,
      '大家注册时找到自己部门的邀请码填入即可。',
      ...linesOfText,
    ].join('\n');
  }, [organizationName, tree.children]);

  const showToast = useCallback((message: string) => {
    setToast(message);
    if (toastTimerRef.current) {
      clearTimeout(toastTimerRef.current);
    }
    toastTimerRef.current = setTimeout(() => setToast(null), 2400);
  }, []);

  useEffect(() => () => {
    if (toastTimerRef.current) {
      clearTimeout(toastTimerRef.current);
    }
    if (bulkInviteTimerRef.current) {
      clearTimeout(bulkInviteTimerRef.current);
    }
  }, []);

  const handleCopyAllInvites = useCallback(async () => {
    if (tree.children.length === 0) {
      showToast('还没有部门邀请码可复制');
      return;
    }
    try {
      await navigator.clipboard.writeText(bulkInviteText);
    } catch {
      const textArea = document.createElement('textarea');
      textArea.value = bulkInviteText;
      textArea.style.position = 'absolute';
      textArea.style.left = '-99999px';
      textArea.style.top = '-99999px';
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
    }
    setBulkInviteCopied(true);
    if (bulkInviteTimerRef.current) {
      clearTimeout(bulkInviteTimerRef.current);
    }
    bulkInviteTimerRef.current = window.setTimeout(() => setBulkInviteCopied(false), 1800);
    showToast('已复制全部部门邀请码');
  }, [bulkInviteText, showToast, tree.children.length]);

  const updateDepartment = useCallback((departmentId: string, patch: Partial<OrgDepartmentSettings>) => {
    onChange({
      ...value,
      departments: value.departments.map((item) => (item.id === departmentId ? { ...item, ...patch } : item)),
    });
  }, [onChange, value]);

  const updateOrganization = useCallback((patch: Partial<OrgModelSettings['organization']>) => {
    onChange({
      ...value,
      organization: {
        ...value.organization,
        ...patch,
      },
    });
  }, [onChange, value]);

  const updateRole = useCallback((roleId: string, patch: Partial<OrgRoleTemplateSettings>) => {
    onChange({
      ...value,
      roles: value.roles.map((item) => (item.id === roleId ? { ...item, ...patch } : item)),
    });
  }, [onChange, value]);

  const handleSaveEdit = useCallback(() => {
    const nextValue = editingText.trim();
    if (!editingNodeId || !editingField) {
      setEditingNodeId(null);
      setEditingField(null);
      return;
    }

    if (!nextValue) {
      setEditingNodeId(null);
      setEditingField(null);
      return;
    }

    if (editingNodeId === tree.id && editingField === 'name') {
      updateOrganization({ name: nextValue });
      setEditingNodeId(null);
      setEditingField(null);
      return;
    }

    const targetDepartment = activeDepartments.find((item) => item.id === editingNodeId);
    if (targetDepartment) {
      if (editingField === 'name') {
        updateDepartment(editingNodeId, { name: nextValue });
      } else {
        updateDepartment(editingNodeId, { leaderName: nextValue, leaderUserId: null });
      }
      setEditingNodeId(null);
      setEditingField(null);
      return;
    }

    const targetRole = activeRoles.find((item) => item.id === editingNodeId);
    if (targetRole && editingField === 'name') {
      updateRole(editingNodeId, { name: nextValue });
    }

    setEditingNodeId(null);
    setEditingField(null);
  }, [activeDepartments, activeRoles, editingField, editingNodeId, editingText, tree.id, updateDepartment, updateOrganization, updateRole]);

  const handleKeyDown = useCallback((event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      handleSaveEdit();
    }
    if (event.key === 'Escape') {
      setEditingNodeId(null);
      setEditingField(null);
    }
  }, [handleSaveEdit]);

  const startEditing = useCallback((nodeId: string, field: EditableField, currentText: string) => {
    if (!canEdit) return;
    setEditingNodeId(nodeId);
    setEditingField(field);
    setEditingText(currentText || '');
  }, [canEdit]);

  const handleSelectDepartmentLead = useCallback((departmentId: string, userId: string) => {
    if (!canEdit) return;
    if (userId === '__manual__') {
      const department = activeDepartments.find((item) => item.id === departmentId);
      startEditing(departmentId, 'leadName', department?.leaderName?.trim() || '');
      return;
    }
    if (!userId) {
      updateDepartment(departmentId, {
        leaderUserId: null,
        leaderName: '',
      });
      return;
    }
    const employee = employeeById.get(userId);
    if (!employee) return;
    const previousLeaderUserId = activeDepartments.find((item) => item.id === departmentId)?.leaderUserId || null;
    const existingBinding = value.bindings.find((binding) => binding.userId === employee.id) || emptyBinding(employee.id);
    const nextPrimaryRoleId = pickDepartmentLeadRoleId(value.roles, departmentId, existingBinding.primaryRoleId);
    const nextBindings = value.bindings
      .map((binding) => {
        if (binding.userId === employee.id) {
          return {
            ...binding,
            departmentId,
            primaryRoleId: nextPrimaryRoleId,
            isManager: true,
            managerUserId: value.organization.leaderUserId && value.organization.leaderUserId !== employee.id
              ? value.organization.leaderUserId
              : binding.managerUserId || null,
            taskEditScope: 'department',
            canApproveTasks: true,
            canReassignTasks: true,
            canChangeDeadline: true,
            updatedAt: new Date().toISOString(),
          };
        }
        if (previousLeaderUserId && binding.userId === previousLeaderUserId && previousLeaderUserId !== employee.id && binding.departmentId === departmentId) {
          return {
            ...binding,
            isManager: false,
            taskEditScope: 'self',
            canApproveTasks: false,
            canReassignTasks: false,
            canChangeDeadline: false,
            updatedAt: new Date().toISOString(),
          };
        }
        return binding;
      });
    const bindingExists = value.bindings.some((binding) => binding.userId === employee.id);
    onChange({
      ...value,
      departments: value.departments.map((department) => (
        department.id === departmentId
          ? {
              ...department,
              leaderUserId: employee.id,
              leaderName: employee.fullName,
            }
          : department
      )),
      bindings: bindingExists
        ? nextBindings
        : [
            ...nextBindings,
            {
              ...existingBinding,
              departmentId,
              primaryRoleId: nextPrimaryRoleId,
              isManager: true,
              managerUserId: value.organization.leaderUserId && value.organization.leaderUserId !== employee.id
                ? value.organization.leaderUserId
                : null,
              taskEditScope: 'department',
              canApproveTasks: true,
              canReassignTasks: true,
              canChangeDeadline: true,
              updatedAt: new Date().toISOString(),
            },
          ],
    });
    setEditingNodeId(null);
    setEditingField(null);
  }, [activeDepartments, canEdit, employeeById, onChange, startEditing, value]);

  const handleSelectOrganizationLead = useCallback((userId: string) => {
    if (!canEdit) return;

    const previousLeaderUserId = value.organization.leaderUserId || null;
    if (!userId) {
      onChange({
        ...value,
        organization: {
          ...value.organization,
          leaderUserId: null,
          managementUserIds: value.organization.managementUserIds.filter((id) => id !== previousLeaderUserId),
        },
        bindings: value.bindings.map((binding) => (
          previousLeaderUserId && binding.userId === previousLeaderUserId
            ? {
                ...binding,
                isManager: false,
                taskEditScope: binding.departmentId ? 'department' : 'self',
                canApproveTasks: false,
                canReassignTasks: false,
                canChangeDeadline: false,
                updatedAt: new Date().toISOString(),
              }
            : binding
        )),
      });
      return;
    }

    const employee = employeeById.get(userId);
    if (!employee) return;

    const existingBinding = value.bindings.find((binding) => binding.userId === employee.id) || emptyBinding(employee.id);
    const bindingExists = value.bindings.some((binding) => binding.userId === employee.id);
    const nextBindings = value.bindings
      .map((binding) => {
        if (binding.userId === employee.id) {
          return {
            ...binding,
            isManager: true,
            managerUserId: null,
            taskEditScope: 'organization',
            canApproveTasks: true,
            canReassignTasks: true,
            canChangeDeadline: true,
            updatedAt: new Date().toISOString(),
          };
        }
        if (previousLeaderUserId && binding.userId === previousLeaderUserId && previousLeaderUserId !== employee.id) {
          return {
            ...binding,
            isManager: false,
            taskEditScope: binding.departmentId ? 'department' : 'self',
            canApproveTasks: false,
            canReassignTasks: false,
            canChangeDeadline: false,
            updatedAt: new Date().toISOString(),
          };
        }
        if (binding.userId !== employee.id && binding.isManager && !binding.managerUserId) {
          return {
            ...binding,
            managerUserId: employee.id,
            updatedAt: new Date().toISOString(),
          };
        }
        return binding;
      });

    onChange({
      ...value,
      organization: {
        ...value.organization,
        leaderUserId: employee.id,
        managementUserIds: Array.from(new Set([...value.organization.managementUserIds.filter((id) => id !== previousLeaderUserId), employee.id])),
      },
      bindings: bindingExists
        ? nextBindings
        : [
            ...nextBindings,
            {
              ...existingBinding,
              isManager: true,
              managerUserId: null,
              taskEditScope: 'organization',
              canApproveTasks: true,
              canReassignTasks: true,
              canChangeDeadline: true,
              updatedAt: new Date().toISOString(),
            },
          ],
    });
  }, [canEdit, employeeById, onChange, value]);

  const handleAddDepartment = useCallback(() => {
    if (!canEdit) return;
    const nextIndex = value.departments.length;
    const nextDepartment: OrgDepartmentSettings = {
      id: nextUiId('department'),
      name: `新部门 ${nextIndex + 1}`,
      color: departmentColor(nextIndex),
      leaderUserId: null,
      leaderName: '',
      parentDepartmentId: null,
      mission: '',
      businessContext: '',
      teamContext: '',
      quarterPlan: buildEmptyQuarterPlan(),
      quarterlyFocus: [],
      collaborationDepartmentIds: [],
      active: true,
      updatedAt: '',
    };

    onChange({
      ...value,
      departments: [...value.departments, nextDepartment],
    });

    window.setTimeout(() => {
      startEditing(nextDepartment.id, 'name', nextDepartment.name);
    }, 10);
  }, [canEdit, onChange, startEditing, value]);

  const handleAddRole = useCallback((departmentId: string | null) => {
    if (!canEdit) return;
    const nextRole: OrgRoleTemplateSettings = {
      id: nextUiId('role'),
      departmentId,
      name: '新岗位',
      level: 'employee',
      managerRoleId: null,
      isManager: false,
      goal: '',
      responsibilities: [],
      shouldAvoid: [],
      collaborationRoleIds: [],
      taskEditScope: 'self',
      canApproveTasks: false,
      canReassignTasks: false,
      canChangeDeadline: false,
      sortOrder: value.roles.length,
      active: true,
      updatedAt: '',
    };

    onChange({
      ...value,
      roles: [...value.roles, nextRole],
    });

    window.setTimeout(() => {
      startEditing(nextRole.id, 'name', nextRole.name);
    }, 10);
  }, [canEdit, onChange, startEditing, value]);

  const handleDeleteDepartment = useCallback((departmentId: string) => {
    if (!canEdit) return;
    const hasRoles = value.roles.some((role) => role.active !== false && role.departmentId === departmentId);
    if (hasRoles) {
      showToast('请先删除该部门下的所有岗位');
      return;
    }

    onChange({
      ...value,
      departments: value.departments.map((department) => (
        department.id === departmentId
          ? { ...department, active: false, updatedAt: department.updatedAt || new Date().toISOString() }
          : department
      )),
      bindings: value.bindings.map((binding) => (
        binding.departmentId === departmentId
          ? { ...binding, departmentId: null }
          : binding
      )),
      departmentPlans: value.departmentPlans.map((plan) => (
        plan.departmentId === departmentId
          ? { ...plan, departmentId: null }
          : plan
      )),
    });
  }, [canEdit, onChange, showToast, value]);

  const handleDeleteRole = useCallback((roleId: string) => {
    if (!canEdit) return;

    onChange({
      ...value,
      roles: value.roles.map((role) => (
        role.id === roleId
          ? { ...role, active: false, updatedAt: role.updatedAt || new Date().toISOString() }
          : role
      )),
      bindings: value.bindings.map((binding) => (
        binding.primaryRoleId === roleId
          ? { ...binding, primaryRoleId: null, updatedAt: binding.updatedAt || new Date().toISOString() }
          : binding
      )),
    });
  }, [canEdit, onChange, value]);

  const handleSave = useCallback(() => {
    void onSave(value);
    showToast('组织结构已保存');
  }, [onSave, showToast, value]);

  const drawLines = useCallback(() => {
    if (!containerRef.current || activeView !== 'tree') {
      setLines([]);
      return;
    }

    const container = containerRef.current;
    const containerRect = container.getBoundingClientRect();
    const nextLines: LineDefinition[] = [];

    const buildPath = (startEl: Element | null, endEl: Element | null) => {
      if (!startEl || !endEl) return null;
      const startRect = startEl.getBoundingClientRect();
      const endRect = endEl.getBoundingClientRect();
      const startX = startRect.right - containerRect.left;
      const startY = startRect.top + startRect.height / 2 - containerRect.top;
      const endX = endRect.left - containerRect.left;
      const endY = endRect.top + endRect.height / 2 - containerRect.top;
      const midX = startX + (endX - startX) / 2;
      return `M ${startX} ${startY} L ${midX} ${startY} L ${midX} ${endY} L ${endX} ${endY}`;
    };

    const orgEl = container.querySelector(`#node-${tree.id}`);
    tree.children.forEach((department) => {
      const departmentEl = container.querySelector(`#node-${department.id}`);
      const departmentPath = buildPath(orgEl, departmentEl);
      if (departmentPath) {
        nextLines.push({ id: `${tree.id}-${department.id}`, path: departmentPath });
      }

      department.children.forEach((role) => {
        const roleEl = container.querySelector(`#node-${role.id}`);
        const rolePath = buildPath(departmentEl, roleEl);
        if (rolePath) {
          nextLines.push({ id: `${department.id}-${role.id}`, path: rolePath });
        }
      });

      const addRoleEl = container.querySelector(`#add-btn-${department.id}`);
      const addRolePath = buildPath(departmentEl, addRoleEl);
      if (addRolePath) {
        nextLines.push({ id: `${department.id}-add`, path: addRolePath });
      }
    });

    const addDepartmentEl = container.querySelector(`#add-btn-${tree.id}`);
    const addDepartmentPath = buildPath(orgEl, addDepartmentEl);
    if (addDepartmentPath) {
      nextLines.push({ id: `${tree.id}-add`, path: addDepartmentPath });
    }

    setLines(nextLines);
  }, [activeView, tree]);

  useLayoutEffect(() => {
    drawLines();
    const observer = new ResizeObserver(() => drawLines());
    if (containerRef.current) {
      observer.observe(containerRef.current);
    }
    window.addEventListener('resize', drawLines);
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', drawLines);
    };
  }, [drawLines, editingField, editingNodeId]);

  return (
    <div className="space-y-6">
      {toast ? (
        <div className="fixed top-6 left-1/2 z-50 -translate-x-1/2 rounded-full bg-gray-900/90 px-5 py-2.5 text-[13px] font-medium text-white shadow-lg">
          {toast}
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-5">
        {stats.map((stat) => (
          <div key={stat.label} className="rounded-[28px] border border-gray-100 bg-white px-6 py-5 shadow-sm">
            <p className="text-[13px] font-medium text-gray-400">{stat.label}</p>
            <p className="mt-3 text-[42px] font-bold tracking-tight text-gray-900">{stat.value}</p>
          </div>
        ))}
      </div>

      <div className="overflow-hidden rounded-[32px] border border-[#DCE4FF] bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-gray-100 px-8 py-6">
          <div className="flex items-center gap-3">
            {activeView === 'codes' ? (
              <button
                type="button"
                onClick={() => setActiveView('tree')}
                className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-gray-200 text-gray-500 transition hover:border-[#5B7BFE]/40 hover:text-[#5B7BFE]"
              >
                <ChevronLeft size={18} />
              </button>
            ) : null}
            <div className="inline-flex items-center gap-2 rounded-full border border-gray-100 bg-white px-4 py-2 text-[13px] font-bold text-[#5B7BFE] shadow-sm">
              <Building2 size={14} />
              组织搭建中心
            </div>
          </div>
          <div className="flex items-center gap-3">
            {canEdit ? (
              <button
                type="button"
                onClick={handleSave}
                disabled={isSaving}
                className="inline-flex items-center gap-2 rounded-full bg-[#5B7BFE] px-5 py-3 text-[13px] font-bold text-white shadow-[0_12px_30px_rgba(91,123,254,0.25)] transition hover:bg-[#4A63CF] disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Save size={14} />
                {isSaving ? '保存中' : '保存'}
              </button>
            ) : null}
            {activeView === 'tree' ? (
              <button
                type="button"
                onClick={() => setActiveView('codes')}
                className="rounded-full border border-[#DCE4FF] bg-white px-5 py-3 text-[13px] font-bold text-[#4A63CF] transition hover:border-[#5B7BFE]/40 hover:text-[#5B7BFE]"
              >
                查看邀请码
              </button>
            ) : (
              <button
                type="button"
                onClick={() => void handleCopyAllInvites()}
                className="inline-flex items-center gap-2 rounded-full border border-[#DCE4FF] bg-white px-5 py-3 text-[13px] font-bold text-[#4A63CF] transition hover:border-[#5B7BFE]/40 hover:text-[#5B7BFE]"
              >
                {bulkInviteCopied ? <Check size={14} /> : <Copy size={14} />}
                {bulkInviteCopied ? '已复制全部邀请码' : '一键复制邀请码'}
              </button>
            )}
          </div>
        </div>

        <div ref={containerRef} className="relative overflow-x-auto bg-[#F9FAFB]">
          {activeView === 'tree' ? (
            <div className="relative min-w-max p-12">
              <svg className="pointer-events-none absolute inset-0 h-full w-full">
                {lines.map((line) => (
                  <path
                    key={line.id}
                    d={line.path}
                    fill="none"
                    stroke="#E5E7EB"
                    strokeWidth="1.5"
                    strokeLinejoin="round"
                  />
                ))}
              </svg>

              <div className="relative z-10 flex items-center gap-12">
                <div
                  id={`node-${tree.id}`}
                  className="z-10 flex min-w-[260px] flex-col gap-3 rounded-2xl border-2 border-[#5B7BFE]/30 bg-gradient-to-br from-[#EEF3FF] to-white px-5 py-4 shadow-sm"
                >
                  <div className="flex items-center gap-3">
                    <Building2 className="text-[#5B7BFE]" size={20} />
                    {editingNodeId === tree.id && editingField === 'name' ? (
                      <input
                        autoFocus
                        value={editingText}
                        onChange={(event) => setEditingText(event.target.value)}
                        onBlur={handleSaveEdit}
                        onKeyDown={handleKeyDown}
                        className="w-full border-b border-[#5B7BFE] bg-transparent text-[16px] font-bold text-gray-900 outline-none"
                      />
                    ) : (
                      <button
                        type="button"
                        onClick={() => startEditing(tree.id, 'name', tree.name)}
                        className="text-left text-[16px] font-bold text-gray-900 transition hover:text-[#5B7BFE]"
                      >
                        {tree.name}
                      </button>
                    )}
                  </div>
                  <div className="flex items-center gap-2 pl-8">
                    <span className="text-[11px] font-medium text-gray-400">负责人</span>
                    {approvedEmployees.length > 0 ? (
                      <select
                        value={value.organization.leaderUserId || ''}
                        onChange={(event) => handleSelectOrganizationLead(event.target.value)}
                        className="min-w-[160px] rounded-full border border-[#DCE4FF] bg-white px-3 py-1.5 text-[11px] font-medium text-gray-700 outline-none transition hover:border-[#5B7BFE]/50 focus:border-[#5B7BFE]"
                      >
                        <option value="">待绑定</option>
                        {approvedEmployees.map((employee) => (
                          <option key={employee.id} value={employee.id}>
                            {(employee.jobTitle?.trim() ? `${employee.jobTitle} · ` : '') + employee.fullName}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span className="rounded-full border border-[#DCE4FF] bg-white px-3 py-1.5 text-[11px] font-medium text-gray-700">
                        {organizationLeaderSummary}
                      </span>
                    )}
                  </div>
                  {approvedEmployees.length > 0 && organizationLeader ? (
                    <div className="pl-8 text-[11px] font-medium text-gray-500">
                      {organizationLeaderSummary}
                    </div>
                  ) : null}
                </div>

                <div className="relative flex flex-col gap-6">
                  {tree.children.map((department, index) => {
                    const isEditingDepartmentName = editingNodeId === department.id && editingField === 'name';
                    const isEditingLeadName = editingNodeId === department.id && editingField === 'leadName';
                    const memberCount = bindingsByDepartmentId.get(department.id)?.length || 0;
                    const inviteCode = buildDepartmentInviteCode(department.id, {
                      organizationName,
                      departmentName: department.name,
                      order: index,
                    });
                    return (
                      <div key={department.id} className="flex items-center gap-10">
                        <div
                          id={`node-${department.id}`}
                          className="group relative z-10 flex min-w-[170px] flex-col gap-1.5 rounded-2xl border border-gray-200 bg-white px-4 py-3 shadow-sm transition hover:border-[#5B7BFE]/40"
                          style={{ boxShadow: `0 12px 28px ${tint(department.color, '16')}` }}
                        >
                          {canEdit ? (
                            <button
                              type="button"
                              onClick={() => handleDeleteDepartment(department.id)}
                              className="absolute -right-2 -top-2 rounded-full border border-gray-200 bg-white p-0.5 text-gray-300 opacity-0 shadow-sm transition group-hover:opacity-100 hover:border-rose-200 hover:text-rose-500"
                            >
                              <X size={12} />
                            </button>
                          ) : null}

                          <div className="flex items-center gap-2">
                            <Users className="text-gray-400" size={14} />
                            {isEditingDepartmentName ? (
                              <input
                                autoFocus
                                value={editingText}
                                onChange={(event) => setEditingText(event.target.value)}
                                onBlur={handleSaveEdit}
                                onKeyDown={handleKeyDown}
                                className="w-full border-b border-[#5B7BFE] bg-transparent text-[13px] font-bold text-gray-800 outline-none"
                              />
                            ) : (
                              <button
                                type="button"
                                onClick={() => startEditing(department.id, 'name', department.name)}
                                className="text-left text-[13px] font-bold text-gray-800 transition hover:text-[#5B7BFE]"
                              >
                                {department.name}
                              </button>
                            )}
                          </div>

                          <div className="flex items-center gap-1.5 pl-6">
                            <span className="text-[11px] text-gray-400">负责人</span>
                            {approvedEmployees.length > 0 && !isEditingLeadName ? (
                              <select
                                value={department.leaderUserId || (department.leaderName?.trim() ? '__manual__' : '')}
                                onChange={(event) => handleSelectDepartmentLead(department.id, event.target.value)}
                                className="min-w-[112px] rounded-full border border-gray-200 bg-white px-2.5 py-1 text-[11px] font-medium text-gray-600 outline-none transition hover:border-[#5B7BFE]/40 focus:border-[#5B7BFE]/50"
                              >
                                <option value="">待绑定</option>
                                {approvedEmployees.map((employee) => (
                                  <option key={employee.id} value={employee.id}>
                                    {employee.fullName}
                                  </option>
                                ))}
                                <option value="__manual__">手动填写</option>
                              </select>
                            ) : (
                              <>
                                {isEditingLeadName ? (
                                  <input
                                    autoFocus
                                    value={editingText}
                                    onChange={(event) => setEditingText(event.target.value)}
                                    onBlur={handleSaveEdit}
                                    onKeyDown={handleKeyDown}
                                    className="w-[84px] border-b border-gray-300 bg-transparent text-[11px] text-gray-600 outline-none focus:border-[#5B7BFE]"
                                  />
                                ) : (
                                  <button
                                    type="button"
                                    onClick={() => startEditing(department.id, 'leadName', department.leadName)}
                                    className="min-w-[40px] text-left text-[11px] text-gray-500 transition hover:text-[#5B7BFE]"
                                  >
                                    {department.leadName || '待设置'}
                                  </button>
                                )}
                              </>
                            )}
                          </div>

                          {approvedEmployees.length > 0 && !department.leaderUserId && department.leaderName?.trim() ? (
                            <div className="pl-6 text-[11px] font-medium text-gray-500">
                              手动负责人：{department.leaderName.trim()}
                            </div>
                          ) : null}

                          <div className="mt-2 flex items-center gap-2 pl-6">
                            <span
                              className="rounded-full px-2.5 py-1 text-[10px] font-bold"
                              style={{ backgroundColor: tint(department.color), color: department.color }}
                            >
                              邀请码 {inviteCode}
                            </span>
                            <span className="rounded-full bg-gray-100 px-2.5 py-1 text-[10px] font-bold text-gray-500">
                              {memberCount} 人
                            </span>
                          </div>
                        </div>

                        <div className="relative flex flex-col gap-3">
                          {department.children.map((role) => {
                            const isEditingRoleName = editingNodeId === role.id && editingField === 'name';
                            return (
                              <div
                                id={`node-${role.id}`}
                                key={role.id}
                                className="group relative z-10 min-w-[120px] rounded-xl border border-gray-100 bg-gray-50/90 px-3 py-2 transition hover:border-gray-200"
                              >
                                {canEdit ? (
                                  <button
                                    type="button"
                                    onClick={() => handleDeleteRole(role.id)}
                                    className="absolute -right-1.5 -top-1.5 rounded-full border border-gray-200 bg-white p-0.5 text-gray-300 opacity-0 shadow-sm transition group-hover:opacity-100 hover:border-rose-200 hover:text-rose-500"
                                  >
                                    <X size={10} />
                                  </button>
                                ) : null}

                                {isEditingRoleName ? (
                                  <input
                                    autoFocus
                                    value={editingText}
                                    onChange={(event) => setEditingText(event.target.value)}
                                    onBlur={handleSaveEdit}
                                    onKeyDown={handleKeyDown}
                                    className="w-full border-b border-gray-300 bg-transparent text-center text-[12px] font-medium text-gray-700 outline-none focus:border-[#5B7BFE]"
                                  />
                                ) : (
                                  <button
                                    type="button"
                                    onClick={() => startEditing(role.id, 'name', role.name)}
                                    className="w-full text-center text-[12px] font-medium text-gray-600 transition hover:text-[#5B7BFE]"
                                  >
                                    {role.name}
                                  </button>
                                )}
                              </div>
                            );
                          })}

                          {canEdit ? (
                            <button
                              id={`add-btn-${department.id}`}
                              type="button"
                              onClick={() => handleAddRole(department.id)}
                              className="z-10 inline-flex min-w-[120px] items-center justify-center gap-1 rounded-xl border border-dashed border-gray-200 bg-white/70 px-3 py-2 text-[12px] text-gray-400 transition hover:border-[#5B7BFE]/40 hover:bg-[#5B7BFE]/5"
                            >
                              <Plus size={12} />
                              添加岗位
                            </button>
                          ) : null}
                        </div>
                      </div>
                    );
                  })}

                  {canEdit ? (
                    <button
                      id={`add-btn-${tree.id}`}
                      type="button"
                      onClick={handleAddDepartment}
                      className="z-10 inline-flex min-w-[150px] items-center justify-center gap-1.5 rounded-xl border border-dashed border-gray-300 bg-white/70 px-4 py-3 text-[13px] font-medium text-gray-400 transition hover:border-[#5B7BFE]/60 hover:bg-[#5B7BFE]/5"
                    >
                      <Plus size={14} />
                      添加部门
                    </button>
                  ) : null}
                </div>
              </div>
            </div>
          ) : (
            <div className="p-8">
              <div className="mx-auto grid max-w-5xl grid-cols-1 gap-5 md:grid-cols-2">
                {tree.children.map((department, index) => {
                  const inviteCode = buildDepartmentInviteCode(department.id, {
                    organizationName,
                    departmentName: department.name,
                    order: index,
                  });
                  const joinedCount = bindingsByDepartmentId.get(department.id)?.length || 0;
                  const positions = department.children.map((item) => item.name).join('、') || '暂无岗位';
                  return (
                    <InviteCard
                      key={department.id}
                      departmentName={department.name}
                      leadName={department.leadName}
                      inviteCode={inviteCode}
                      positions={positions}
                      joinedCount={joinedCount}
                      color={department.color}
                    />
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

type InviteCardProps = {
  departmentName: string;
  leadName: string;
  inviteCode: string;
  positions: string;
  joinedCount: number;
  color: string;
};

function InviteCard({
  departmentName,
  leadName,
  inviteCode,
  positions,
  joinedCount,
  color,
}: InviteCardProps) {
  return (
    <div className="flex h-full flex-col rounded-2xl border border-gray-100 bg-white p-6 shadow-sm transition hover:shadow-md">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-[17px] font-bold text-gray-900">{departmentName}</h3>
          <p className="mt-1 text-[12px] text-gray-500">{leadName || '待设置负责人'}</p>
        </div>
        <div className="rounded-full bg-gray-100 px-3 py-1 text-[11px] font-bold text-gray-500">
          已加入 {joinedCount} 人
        </div>
      </div>

      <div className="mt-auto rounded-xl border px-4 py-4" style={{ backgroundColor: tint(color, '08'), borderColor: tint(color, '18') }}>
        <div className="mb-2 text-[11px] font-bold uppercase tracking-[0.18em]" style={{ color }}>
          邀请码
        </div>
        <div className="text-[22px] font-bold tracking-[0.16em]" style={{ color }}>
          {inviteCode}
        </div>
      </div>

      <div className="mt-4 border-t border-gray-100 pt-4 text-[12px] text-gray-500">
        {positions}
      </div>
    </div>
  );
}
~~~

## `src/renderer/components/settings/OrganizationTreeCanvas.tsx`

- 编码: `utf-8`

~~~tsx
import { useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowRightLeft,
  BriefcaseBusiness,
  Building2,
  CheckCircle2,
  FileText,
  FolderKanban,
  GripVertical,
  LayoutGrid,
  PanelRightOpen,
  Plus,
  Sparkles,
  UserPlus,
  UserRound,
  Users,
  Workflow,
} from 'lucide-react';

import type {
  DepartmentOption,
  EmployeeRecord,
  OrgDepartmentSettings,
  OrgEmployeeBindingSettings,
  OrgModelSettings,
  OrgRoleLevel,
  OrgRoleTemplateSettings,
  OrgTaskControlRuleSettings,
} from '../../../shared/types';

type Props = {
  value: OrgModelSettings;
  departmentCatalog: DepartmentOption[];
  employees: EmployeeRecord[];
  canEdit: boolean;
  onChange: (next: OrgModelSettings) => void;
};

type ViewMode = 'card' | 'collab';

type SelectedNode =
  | { type: 'organization' }
  | { type: 'department'; id: string }
  | { type: 'role'; id: string }
  | { type: 'member'; id: string };

type DragPayload =
  | { type: 'department'; id: string }
  | { type: 'role'; id: string }
  | { type: 'member'; id: string };

type DepartmentMeta = {
  node: OrgDepartmentSettings;
  roleIds: string[];
  memberIds: string[];
  planCount: number;
  completeness: number;
  missing: string[];
  ownerName: string;
  relatedProjects: string[];
  statusLabel: string;
};

type RoleMeta = {
  node: OrgRoleTemplateSettings;
  memberIds: string[];
  processCount: number;
  templateCount: number;
  completeness: number;
  missing: string[];
  descriptionStatus: string;
  processStatus: string;
  templateStatus: string;
  relatedProjects: string[];
};

type MemberMeta = {
  node: EmployeeRecord;
  binding: OrgEmployeeBindingSettings;
  roleName: string;
  departmentName: string;
  projectCount: number;
  workloadLabel: string;
  relatedProjects: string[];
};

const ROLE_LEVEL_OPTIONS: Array<{ value: OrgRoleLevel; label: string }> = [
  { value: 'organization_lead', label: '机构负责人' },
  { value: 'department_lead', label: '部门负责人' },
  { value: 'supervisor', label: '主管' },
  { value: 'employee', label: '员工' },
];

const VIEW_OPTIONS: Array<{ value: ViewMode; label: string; icon: typeof LayoutGrid }> = [
  { value: 'card', label: '卡片', icon: LayoutGrid },
  { value: 'collab', label: '协作关系', icon: ArrowRightLeft },
];

const DEPARTMENT_COLORS = ['#5B7BFE', '#0EA5E9', '#14B8A6', '#F59E0B', '#EF4444', '#8B5CF6'];

function nextUiId(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function toMultiline(values: string[]) {
  return values.join('\n');
}

function fromMultiline(value: string) {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean);
}

function tint(hexColor: string, suffix = '18') {
  return `${hexColor}${suffix}`;
}

function moveBefore<T>(items: T[], fromIndex: number, toIndex: number) {
  if (fromIndex === -1 || toIndex === -1 || fromIndex === toIndex) {
    return items;
  }
  const next = [...items];
  const [item] = next.splice(fromIndex, 1);
  next.splice(toIndex, 0, item);
  return next;
}

function clampPercent(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function pickWorkload(projectCount: number, isManager: boolean, hasFocus: boolean) {
  const score = projectCount + (isManager ? 2 : 0) + (hasFocus ? 1 : 0);
  if (score >= 5) return '高';
  if (score >= 3) return '中';
  return '轻';
}

function completionTone(percent: number) {
  if (percent >= 80) return 'text-emerald-700 bg-emerald-50 border-emerald-100';
  if (percent >= 55) return 'text-amber-700 bg-amber-50 border-amber-100';
  return 'text-slate-600 bg-slate-100 border-slate-200';
}

export function OrganizationTreeCanvas({ value, departmentCatalog, employees, canEdit, onChange }: Props) {
  const [viewMode, setViewMode] = useState<ViewMode>('card');
  const [selectedNode, setSelectedNode] = useState<SelectedNode>({ type: 'organization' });
  const [dragHint, setDragHint] = useState<string | null>(null);
  const [memberDraftUserId, setMemberDraftUserId] = useState('');

  const employeeById = useMemo(() => new Map(employees.map((item) => [item.id, item])), [employees]);
  const roleById = useMemo(() => new Map(value.roles.map((item) => [item.id, item])), [value.roles]);
  const bindingByUserId = useMemo(() => new Map(value.bindings.map((item) => [item.userId, item])), [value.bindings]);
  const activeDepartments = useMemo(() => value.departments.filter((item) => item.active !== false), [value.departments]);
  const activeRoles = useMemo(() => value.roles.filter((item) => item.active !== false), [value.roles]);
  const activeEmployees = useMemo(
    () => employees.filter((item) => item.accountStatus !== 'disabled'),
    [employees],
  );
  const activePlans = useMemo(
    () => value.departmentPlans.filter((item) => item.status !== 'closed'),
    [value.departmentPlans],
  );

  const departmentOptions = useMemo(() => {
    if (activeDepartments.length > 0) {
      return activeDepartments.map((item) => ({ id: item.id, name: item.name, color: item.color }));
    }
    return departmentCatalog;
  }, [activeDepartments, departmentCatalog]);

  const rulesByRoleId = useMemo(() => {
    const mapping = new Map<string, OrgTaskControlRuleSettings[]>();
    value.taskControlRules
      .filter((item) => item.active !== false && item.roleTemplateId)
      .forEach((rule) => {
        const key = rule.roleTemplateId as string;
        const list = mapping.get(key) || [];
        list.push(rule);
        mapping.set(key, list);
      });
    return mapping;
  }, [value.taskControlRules]);

  const processByRoleId = useMemo(() => {
    const mapping = new Map<string, OrgModelSettings['roleProcessTemplates']>();
    value.roleProcessTemplates
      .filter((item) => item.active !== false && item.roleTemplateId)
      .forEach((template) => {
        const key = template.roleTemplateId as string;
        const list = mapping.get(key) || [];
        list.push(template);
        mapping.set(key, list);
      });
    return mapping;
  }, [value.roleProcessTemplates]);

  const relatedProjectsByDepartment = useMemo(() => {
    const mapping = new Map<string, string[]>();
    value.bindings.forEach((binding) => {
      if (!binding.departmentId || binding.projectRoleLabels.length === 0) return;
      const existing = new Set(mapping.get(binding.departmentId) || []);
      binding.projectRoleLabels.forEach((label) => existing.add(label));
      mapping.set(binding.departmentId, Array.from(existing));
    });
    return mapping;
  }, [value.bindings]);

  const departmentMetaMap = useMemo(() => {
    const mapping = new Map<string, DepartmentMeta>();
    activeDepartments.forEach((department) => {
      const roleIds = activeRoles.filter((role) => role.departmentId === department.id).map((role) => role.id);
      const memberIds = value.bindings
        .filter((binding) => binding.departmentId === department.id && employeeById.has(binding.userId))
        .map((binding) => binding.userId);
      const planCount = activePlans.filter((plan) => plan.departmentId === department.id).length;
      const missing: string[] = [];
      if (!(department.leaderUserId || department.leaderName?.trim())) missing.push('待绑定负责人');
      if (!department.mission.trim()) missing.push('待补部门使命');
      if (roleIds.length === 0) missing.push('待补岗位模板');
      if (memberIds.length === 0) missing.push('待补成员归属');
      if (planCount === 0) missing.push('待补部门计划');
      const completeness = clampPercent(((5 - missing.length) / 5) * 100);
      mapping.set(department.id, {
        node: department,
        roleIds,
        memberIds,
        planCount,
        completeness,
        missing,
        ownerName:
          department.leaderName?.trim() ||
          (department.leaderUserId ? employeeById.get(department.leaderUserId)?.fullName || '已绑定负责人' : '待绑定'),
        relatedProjects: relatedProjectsByDepartment.get(department.id) || [],
        statusLabel: department.active === false ? '停用' : completeness >= 80 ? '稳定' : completeness >= 55 ? '搭建中' : '待补全',
      });
    });
    return mapping;
  }, [activeDepartments, activePlans, activeRoles, employeeById, relatedProjectsByDepartment, value.bindings]);

  const roleMetaMap = useMemo(() => {
    const mapping = new Map<string, RoleMeta>();
    activeRoles.forEach((role) => {
      const memberIds = value.bindings
        .filter((binding) => binding.primaryRoleId === role.id && employeeById.has(binding.userId))
        .map((binding) => binding.userId);
      const processCount = (processByRoleId.get(role.id) || []).length;
      const templateCount = (rulesByRoleId.get(role.id) || []).length;
      const missing: string[] = [];
      if (!role.goal.trim() && role.responsibilities.length === 0) missing.push('待补岗位说明');
      if (processCount === 0) missing.push('待补流程模板');
      if (templateCount === 0) missing.push('待补任务模板');
      if (memberIds.length === 0) missing.push('待绑定成员');
      const completeness = clampPercent(((4 - missing.length) / 4) * 100);
      const relatedProjects = Array.from(
        new Set(
          memberIds.flatMap((userId) => bindingByUserId.get(userId)?.projectRoleLabels || []),
        ),
      );
      mapping.set(role.id, {
        node: role,
        memberIds,
        processCount,
        templateCount,
        completeness,
        missing,
        descriptionStatus: role.goal.trim() || role.responsibilities.length > 0 ? '已补说明' : '待补说明',
        processStatus: processCount > 0 ? `${processCount} 个流程` : '待补流程',
        templateStatus: templateCount > 0 ? `${templateCount} 个模板` : '待补模板',
        relatedProjects,
      });
    });
    return mapping;
  }, [activeRoles, bindingByUserId, employeeById, processByRoleId, rulesByRoleId, value.bindings]);

  const memberMetaMap = useMemo(() => {
    const mapping = new Map<string, MemberMeta>();
    activeEmployees.forEach((employee) => {
      const binding = bindingByUserId.get(employee.id);
      if (!binding) return;
      const roleName = binding.primaryRoleId ? roleById.get(binding.primaryRoleId)?.name || '未命名岗位' : '未绑定岗位';
      const departmentName = binding.departmentId
        ? departmentOptions.find((option) => option.id === binding.departmentId)?.name || '未命名部门'
        : '未绑定部门';
      const projectCount = binding.projectRoleLabels.length;
      mapping.set(employee.id, {
        node: employee,
        binding,
        roleName,
        departmentName,
        projectCount,
        workloadLabel: pickWorkload(projectCount, binding.isManager, Boolean(binding.currentFocus.trim())),
        relatedProjects: binding.projectRoleLabels,
      });
    });
    return mapping;
  }, [activeEmployees, bindingByUserId, departmentOptions, roleById]);

  const overallCompleteness = useMemo(() => {
    if (activeDepartments.length === 0) return 0;
    const total = activeDepartments.reduce((sum, department) => sum + (departmentMetaMap.get(department.id)?.completeness || 0), 0);
    return clampPercent(total / activeDepartments.length);
  }, [activeDepartments, departmentMetaMap]);

  const unboundEmployees = useMemo(
    () =>
      activeEmployees.filter((employee) => {
        const binding = bindingByUserId.get(employee.id);
        return !binding || !binding.primaryRoleId;
      }),
    [activeEmployees, bindingByUserId],
  );

  const addDepartment = () => {
    const nextIndex = value.departments.length;
    const color = DEPARTMENT_COLORS[nextIndex % DEPARTMENT_COLORS.length];
    onChange({
      ...value,
      departments: [
        ...value.departments,
        {
          id: nextUiId('department'),
          name: `新部门 ${nextIndex + 1}`,
          color,
          leaderUserId: null,
          leaderName: '',
          parentDepartmentId: null,
          mission: '',
          businessContext: '',
          teamContext: '',
          quarterPlan: {
            year: '',
            quarter: 'Q1',
            objective: '',
            deliverables: [],
            successMetrics: [],
            majorRisks: [],
            updatedAt: '',
          },
          quarterlyFocus: [],
          collaborationDepartmentIds: [],
          active: true,
          updatedAt: '',
        },
      ],
    });
  };

  const addRole = (departmentId?: string | null) => {
    onChange({
      ...value,
      roles: [
        ...value.roles,
        {
          id: nextUiId('role'),
          departmentId: departmentId || activeDepartments[0]?.id || null,
          name: '',
          level: 'employee',
          managerRoleId: null,
          isManager: false,
          goal: '',
          responsibilities: [],
          shouldAvoid: [],
          collaborationRoleIds: [],
          taskEditScope: 'self',
          canApproveTasks: false,
          canReassignTasks: false,
          canChangeDeadline: false,
          sortOrder: value.roles.length,
          active: true,
          updatedAt: '',
        },
      ],
    });
  };

  const updateDepartment = (departmentId: string, patch: Partial<OrgDepartmentSettings>) => {
    onChange({
      ...value,
      departments: value.departments.map((item) => (item.id === departmentId ? { ...item, ...patch } : item)),
    });
  };

  const updateRole = (roleId: string, patch: Partial<OrgRoleTemplateSettings>) => {
    onChange({
      ...value,
      roles: value.roles.map((item) => (item.id === roleId ? { ...item, ...patch } : item)),
    });
  };

  const updateBinding = (userId: string, patch: Partial<OrgEmployeeBindingSettings>) => {
    const existing = bindingByUserId.get(userId);
    const nextBinding: OrgEmployeeBindingSettings = {
      userId,
      departmentId: null,
      primaryRoleId: null,
      managerUserId: null,
      isManager: false,
      projectRoleLabels: [],
      currentFocus: '',
      taskEditScope: 'self',
      canApproveTasks: false,
      canReassignTasks: false,
      canChangeDeadline: false,
      updatedAt: '',
      ...(existing || {}),
      ...patch,
    };
    onChange({
      ...value,
      bindings: existing
        ? value.bindings.map((item) => (item.userId === userId ? nextBinding : item))
        : [...value.bindings, nextBinding],
    });
  };

  const bindMemberToRole = (userId: string, roleId: string) => {
    const role = roleById.get(roleId);
    if (!role) return;
    updateBinding(userId, {
      primaryRoleId: roleId,
      departmentId: role.departmentId || null,
      isManager: role.isManager,
    });
  };

  const addMember = (roleId: string) => {
    const targetUserId = memberDraftUserId || unboundEmployees[0]?.id;
    if (!targetUserId) return;
    bindMemberToRole(targetUserId, roleId);
    setMemberDraftUserId('');
  };

  const createProcessTemplateForRole = (roleId: string) => {
    onChange({
      ...value,
      roleProcessTemplates: [
        ...value.roleProcessTemplates,
        {
          id: nextUiId('process'),
          roleTemplateId: roleId,
          name: `${roleById.get(roleId)?.name || '岗位'}标准流程`,
          triggerType: 'manual',
          triggerCondition: '',
          keySteps: [],
          collaborationStep: '',
          approvalStep: '',
          outputArtifact: '',
          commonBlockers: [],
          active: true,
          updatedAt: '',
        },
      ],
    });
  };

  const createRuleTemplateForRole = (roleId: string) => {
    const role = roleById.get(roleId);
    onChange({
      ...value,
      taskControlRules: [
        ...value.taskControlRules,
        {
          id: nextUiId('rule'),
          name: `${role?.name || '岗位'}任务模板`,
          controlLevel: role?.isManager ? 'department_control' : 'normal',
          departmentId: role?.departmentId || null,
          roleTemplateId: roleId,
          contentEditableBy: role?.isManager ? 'department_lead' : 'assignee',
          deadlineEditableBy: role?.isManager ? 'department_lead' : 'manager',
          ownerEditableBy: 'manager',
          cancellableBy: 'manager',
          requireCollabConfirmation: false,
          defaultApproverUserId: null,
          active: true,
          updatedAt: '',
        },
      ],
    });
  };

  const writeDragPayload = (event: React.DragEvent, payload: DragPayload) => {
    event.dataTransfer.setData('application/x-org-node', JSON.stringify(payload));
    event.dataTransfer.effectAllowed = 'move';
  };

  const readDragPayload = (event: React.DragEvent): DragPayload | null => {
    const raw = event.dataTransfer.getData('application/x-org-node');
    if (!raw) return null;
    try {
      return JSON.parse(raw) as DragPayload;
    } catch {
      return null;
    }
  };

  const reorderDepartments = (sourceId: string, targetId: string) => {
    const fromIndex = value.departments.findIndex((item) => item.id === sourceId);
    const toIndex = value.departments.findIndex((item) => item.id === targetId);
    onChange({ ...value, departments: moveBefore(value.departments, fromIndex, toIndex) });
  };

  const moveRoleToDepartment = (roleId: string, departmentId: string) => {
    const nextOrder = Math.max(
      0,
      ...value.roles.filter((item) => item.departmentId === departmentId).map((item) => item.sortOrder),
    );
    updateRole(roleId, { departmentId, sortOrder: nextOrder + 1 });
  };

  const moveMemberToRole = (userId: string, roleId: string) => {
    bindMemberToRole(userId, roleId);
  };

  const handleDepartmentDrop = (event: React.DragEvent, departmentId: string) => {
    event.preventDefault();
    const payload = readDragPayload(event);
    setDragHint(null);
    if (!payload) return;
    if (payload.type === 'department' && payload.id !== departmentId) {
      reorderDepartments(payload.id, departmentId);
    }
    if (payload.type === 'role') {
      moveRoleToDepartment(payload.id, departmentId);
    }
  };

  const handleRoleDrop = (event: React.DragEvent, roleId: string) => {
    event.preventDefault();
    const payload = readDragPayload(event);
    setDragHint(null);
    if (!payload) return;
    if (payload.type === 'member') {
      moveMemberToRole(payload.id, roleId);
    }
  };

  const selectedDepartmentMeta =
    selectedNode.type === 'department' ? departmentMetaMap.get(selectedNode.id) || null : null;
  const selectedRoleMeta = selectedNode.type === 'role' ? roleMetaMap.get(selectedNode.id) || null : null;
  const selectedMemberMeta = selectedNode.type === 'member' ? memberMetaMap.get(selectedNode.id) || null : null;

  return (
    <div className="rounded-[32px] border border-gray-100 bg-white shadow-sm overflow-hidden">
      <div className="border-b border-gray-100 bg-[linear-gradient(135deg,rgba(91,123,254,0.08),rgba(255,255,255,0.96)_40%,rgba(14,165,233,0.06))] px-6 py-6">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-white/80 px-3 py-1 text-[11px] font-bold text-[#5B7BFE] shadow-sm">
              <Sparkles size={12} />
              AI 可读的组织建模画布
            </div>
            <h3 className="mt-4 text-[22px] font-bold tracking-tight text-gray-900">组织建模画布</h3>
            <p className="mt-2 max-w-3xl text-[13px] leading-6 text-gray-500">
              把组织、部门、岗位、成员建成结构化底盘。项目暂时不入画布，先在右侧详情里作为关联项目展示，后续 AI 会直接读取这份层级模型。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {VIEW_OPTIONS.map((option) => {
              const Icon = option.icon;
              const active = viewMode === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setViewMode(option.value)}
                  className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-[12px] font-bold transition ${
                    active ? 'bg-[#5B7BFE] text-white shadow-[0_10px_24px_rgba(91,123,254,0.24)]' : 'border border-gray-200 bg-white text-gray-600'
                  }`}
                >
                  <Icon size={14} />
                  {option.label}
                </button>
              );
            })}
            <button
              type="button"
              onClick={addDepartment}
              disabled={!canEdit}
              className="inline-flex items-center gap-2 rounded-full border border-[#DCE4FF] bg-white px-4 py-2 text-[12px] font-bold text-[#4A63CF] shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Plus size={14} />
              新增部门
            </button>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
          {[
            { label: '部门', value: `${activeDepartments.length}` },
            { label: '岗位', value: `${activeRoles.length}` },
            { label: '成员', value: `${value.bindings.filter((item) => item.primaryRoleId).length}` },
            { label: '计划数', value: `${activePlans.length}` },
            { label: '完整度', value: `${overallCompleteness}%` },
            { label: '缺口', value: `${activeDepartments.reduce((sum, department) => sum + (departmentMetaMap.get(department.id)?.missing.length || 0), 0)}` },
          ].map((stat) => (
            <div key={stat.label} className="rounded-[22px] border border-white/80 bg-white/80 px-4 py-4 shadow-sm">
              <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-gray-400">{stat.label}</p>
              <p className="mt-2 text-[24px] font-bold tracking-tight text-gray-900">{stat.value}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 border-r border-gray-100 bg-[#FBFCFF] p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="text-[12px] leading-6 text-gray-500">
              {viewMode === 'card' ? '卡片视图用于快速盘点结构与缺口。' : '协作关系视图预留给后续跨部门网络图。'}
            </div>
            {dragHint ? (
              <span className="rounded-full bg-blue-50 px-3 py-1.5 text-[11px] font-bold text-[#5B7BFE]">{dragHint}</span>
            ) : (
              <span className="rounded-full bg-gray-100 px-3 py-1.5 text-[11px] font-bold text-gray-500">结构化节点字段已启用</span>
            )}
          </div>

          <button
            type="button"
            onClick={() => setSelectedNode({ type: 'organization' })}
            className={`w-full rounded-[28px] border px-5 py-5 text-left shadow-sm transition ${
              selectedNode.type === 'organization' ? 'border-[#B9CAFF] bg-white' : 'border-gray-200 bg-white'
            }`}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="inline-flex items-center gap-2 rounded-full bg-blue-50 px-3 py-1.5 text-[11px] font-bold text-[#4A63CF]">
                  <Building2 size={12} />
                  组织
                </div>
                <h4 className="mt-3 text-[20px] font-bold tracking-tight text-gray-900">
                  {value.organization.name.trim() || '当前组织'}
                </h4>
                <p className="mt-2 text-[13px] leading-6 text-gray-500">
                  {value.organization.annualGoal.trim() || '待补组织目标、今年计划与项目意图，后续任务识别会按这层背景理解。'}
                </p>
              </div>
              <span className={`rounded-full border px-3 py-1 text-[11px] font-bold ${completionTone(overallCompleteness)}`}>
                {overallCompleteness}% 完整
              </span>
            </div>
          </button>

          {viewMode === 'collab' ? (
            <div className="mt-6 rounded-[28px] border border-dashed border-gray-200 bg-white px-6 py-12 text-center">
              <ArrowRightLeft size={24} className="mx-auto text-gray-300" />
              <p className="mt-4 text-[16px] font-bold text-gray-900">协作关系视图预留中</p>
              <p className="mt-2 text-[12px] leading-6 text-gray-500">
                下一步会把跨部门依赖、负责人关系和协作频次拉成关系网。当前先在卡片视图和详情抽屉里完成结构建模。
              </p>
            </div>
          ) : (
            <div className="mt-6 grid grid-cols-1 gap-4 2xl:grid-cols-2">
              {activeDepartments.map((department) => {
                const meta = departmentMetaMap.get(department.id);
                if (!meta) return null;
                return (
                  <button
                    key={department.id}
                    type="button"
                    onClick={() => setSelectedNode({ type: 'department', id: department.id })}
                    draggable={canEdit}
                    onDragStart={(event) => writeDragPayload(event, { type: 'department', id: department.id })}
                    onDragOver={(event) => {
                      event.preventDefault();
                      setDragHint('松手即可把部门排到这里');
                    }}
                    onDrop={(event) => handleDepartmentDrop(event, department.id)}
                    onDragLeave={() => setDragHint(null)}
                    className={`rounded-[28px] border bg-white p-5 text-left shadow-sm transition ${
                      selectedNode.type === 'department' && selectedNode.id === department.id
                        ? 'border-[#B9CAFF]'
                        : 'border-gray-200 hover:border-blue-200'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div
                          className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-[10px] font-bold"
                          style={{ backgroundColor: tint(department.color), color: department.color }}
                        >
                          <GripVertical size={12} />
                          {department.name}
                        </div>
                        <p className="mt-3 text-[14px] font-bold text-gray-900">{meta.ownerName}</p>
                        <p className="mt-1 text-[12px] leading-6 text-gray-500">
                          {department.mission.trim() || '待补部门使命、负责人与本周计划。'}
                        </p>
                      </div>
                      <span className={`rounded-full border px-3 py-1 text-[11px] font-bold ${completionTone(meta.completeness)}`}>
                        {meta.completeness}%
                      </span>
                    </div>
                    <div className="mt-4 grid grid-cols-4 gap-3 text-center">
                      {[
                        ['岗位', meta.roleIds.length],
                        ['成员', meta.memberIds.length],
                        ['计划', meta.planCount],
                        ['缺口', meta.missing.length],
                      ].map(([label, count]) => (
                        <div key={label} className="rounded-2xl bg-gray-50 px-3 py-3">
                          <p className="text-[11px] text-gray-500">{label}</p>
                          <p className="mt-1 text-[16px] font-bold text-gray-900">{count}</p>
                        </div>
                      ))}
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <span className={`rounded-full border px-2.5 py-1 text-[10px] font-bold ${completionTone(meta.completeness)}`}>
                        {meta.statusLabel}
                      </span>
                      {meta.missing.slice(0, 2).map((item) => (
                        <span key={item} className="rounded-full bg-amber-50 px-2.5 py-1 text-[10px] font-bold text-amber-700">
                          {item}
                        </span>
                      ))}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <aside className="border-t border-gray-100 bg-white xl:border-t-0">
          <div className="sticky top-0 flex h-full flex-col">
            <div className="border-b border-gray-100 px-5 py-4">
              <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">
                <PanelRightOpen size={13} />
                右侧详情抽屉
              </div>
              <p className="mt-2 text-[13px] leading-6 text-gray-500">
                点击任意节点即可编辑字段、补流程、补模板、绑定负责人，并查看关联项目。
              </p>
            </div>

            <div className="flex-1 overflow-y-auto px-5 py-5">
              {selectedNode.type === 'organization' ? (
                <div className="space-y-5">
                  <DrawerHeader
                    icon={Building2}
                    title={value.organization.name.trim() || '当前组织'}
                    subtitle="组织节点"
                    tone="blue"
                  />
                  <DrawerTextarea
                    label="组织名称"
                    value={value.organization.name}
                    disabled={!canEdit}
                    placeholder="组织名称"
                    onChange={(next) =>
                      onChange({ ...value, organization: { ...value.organization, name: next } })
                    }
                  />
                  <DrawerTextarea
                    label="年度目标"
                    value={value.organization.annualGoal}
                    disabled={!canEdit}
                    placeholder="年度目标"
                    multiline
                    onChange={(next) =>
                      onChange({ ...value, organization: { ...value.organization, annualGoal: next } })
                    }
                  />
                  <DrawerTextarea
                    label="季度重点"
                    value={toMultiline(value.organization.quarterlyFocus)}
                    disabled={!canEdit}
                    placeholder="每行一条季度重点"
                    multiline
                    onChange={(next) =>
                      onChange({
                        ...value,
                        organization: { ...value.organization, quarterlyFocus: fromMultiline(next) },
                      })
                    }
                  />
                  <label className="space-y-2">
                    <span className="text-[12px] font-bold text-gray-700">组织负责人</span>
                    <select
                      value={value.organization.leaderUserId || ''}
                      onChange={(event) =>
                        onChange({
                          ...value,
                          organization: {
                            ...value.organization,
                            leaderUserId: event.target.value || null,
                            managementUserIds: event.target.value
                              ? Array.from(new Set([...value.organization.managementUserIds, event.target.value]))
                              : value.organization.managementUserIds,
                          },
                        })
                      }
                      disabled={!canEdit}
                      className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                    >
                      <option value="">请选择负责人</option>
                      {activeEmployees.map((employee) => (
                        <option key={employee.id} value={employee.id}>
                          {employee.fullName}
                        </option>
                      ))}
                    </select>
                  </label>
                  <DrawerInfoBlock
                    title="组织模型完整度"
                    helper="组织根节点主要负责承接名称、目标和负责人。部门以下结构会继续细化岗位、成员、流程与计划。"
                    items={[
                      value.organization.name.trim() ? '组织名称已补齐' : '待补组织名称',
                      value.organization.leaderUserId ? '负责人已绑定' : '待绑定负责人',
                      value.organization.annualGoal.trim() || value.organization.quarterlyFocus.length > 0 ? '目标语境已补齐' : '待补年度目标 / 季度重点',
                    ]}
                  />
                </div>
              ) : null}

              {selectedDepartmentMeta ? (
                <div className="space-y-5">
                  <DrawerHeader
                    icon={Building2}
                    title={selectedDepartmentMeta.node.name}
                    subtitle="部门节点"
                    tone="emerald"
                  />
                  <DrawerTextarea
                    label="部门名称"
                    value={selectedDepartmentMeta.node.name}
                    disabled={!canEdit}
                    placeholder="部门名称"
                    onChange={(next) => updateDepartment(selectedDepartmentMeta.node.id, { name: next })}
                  />
                  <label className="space-y-2">
                    <span className="text-[12px] font-bold text-gray-700">负责人</span>
                    <select
                      value={selectedDepartmentMeta.node.leaderUserId || ''}
                      onChange={(event) =>
                        updateDepartment(selectedDepartmentMeta.node.id, {
                          leaderUserId: event.target.value || null,
                          leaderName: event.target.value ? employeeById.get(event.target.value)?.fullName || '' : '',
                        })
                      }
                      disabled={!canEdit}
                      className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                    >
                      <option value="">请选择负责人</option>
                      {activeEmployees.map((employee) => (
                        <option key={employee.id} value={employee.id}>
                          {employee.fullName}
                        </option>
                      ))}
                    </select>
                  </label>
                  <DrawerTextarea
                    label="部门使命"
                    value={selectedDepartmentMeta.node.mission}
                    disabled={!canEdit}
                    placeholder="部门使命与业务定位"
                    multiline
                    onChange={(next) => updateDepartment(selectedDepartmentMeta.node.id, { mission: next })}
                  />
                  <DrawerTextarea
                    label="季度重点"
                    value={toMultiline(selectedDepartmentMeta.node.quarterlyFocus)}
                    disabled={!canEdit}
                    placeholder="每行一条重点"
                    multiline
                    onChange={(next) =>
                      updateDepartment(selectedDepartmentMeta.node.id, { quarterlyFocus: fromMultiline(next) })
                    }
                  />
                  <div className="grid grid-cols-2 gap-3">
                    <InfoMetricCard label="岗位数" value={`${selectedDepartmentMeta.roleIds.length}`} />
                    <InfoMetricCard label="成员数" value={`${selectedDepartmentMeta.memberIds.length}`} />
                    <InfoMetricCard label="计划数" value={`${selectedDepartmentMeta.planCount}`} />
                    <InfoMetricCard label="完整度" value={`${selectedDepartmentMeta.completeness}%`} />
                  </div>
                  <DrawerActionRow
                    actions={[
                      {
                        label: '新增岗位',
                        icon: Plus,
                        onClick: () => addRole(selectedDepartmentMeta.node.id),
                        disabled: !canEdit,
                      },
                    ]}
                  />
                  <DrawerInfoBlock
                    title="缺失项提示"
                    helper="部门节点会优先检查负责人、使命、岗位、成员与计划覆盖。"
                    items={
                      selectedDepartmentMeta.missing.length > 0
                        ? selectedDepartmentMeta.missing
                        : ['该部门的负责人、岗位、成员与计划已经基本齐全']
                    }
                  />
                  <DrawerInfoBlock
                    title="关联项目"
                    helper="项目暂不入树，先在这里聚合展示部门当前已绑定的项目标签。"
                    items={
                      selectedDepartmentMeta.relatedProjects.length > 0
                        ? selectedDepartmentMeta.relatedProjects
                        : ['当前暂无关联项目']
                    }
                    icon={FolderKanban}
                  />
                </div>
              ) : null}

              {selectedRoleMeta ? (
                <div className="space-y-5">
                  <DrawerHeader
                    icon={BriefcaseBusiness}
                    title={selectedRoleMeta.node.name || '未命名岗位'}
                    subtitle="岗位节点"
                    tone="violet"
                  />
                  <DrawerTextarea
                    label="岗位名称"
                    value={selectedRoleMeta.node.name}
                    disabled={!canEdit}
                    placeholder="岗位名称"
                    onChange={(next) => updateRole(selectedRoleMeta.node.id, { name: next })}
                  />
                  <div className="grid grid-cols-2 gap-3">
                    <label className="space-y-2">
                      <span className="text-[12px] font-bold text-gray-700">归属部门</span>
                      <select
                        value={selectedRoleMeta.node.departmentId || ''}
                        onChange={(event) => updateRole(selectedRoleMeta.node.id, { departmentId: event.target.value || null })}
                        disabled={!canEdit}
                        className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                      >
                        <option value="">未绑定部门</option>
                        {departmentOptions.map((department) => (
                          <option key={department.id} value={department.id}>
                            {department.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="space-y-2">
                      <span className="text-[12px] font-bold text-gray-700">岗位级别</span>
                      <select
                        value={selectedRoleMeta.node.level}
                        onChange={(event) => updateRole(selectedRoleMeta.node.id, { level: event.target.value as OrgRoleLevel })}
                        disabled={!canEdit}
                        className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                      >
                        {ROLE_LEVEL_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <DrawerTextarea
                    label="岗位目标"
                    value={selectedRoleMeta.node.goal}
                    disabled={!canEdit}
                    placeholder="一句话说明岗位目标"
                    onChange={(next) => updateRole(selectedRoleMeta.node.id, { goal: next })}
                  />
                  <DrawerTextarea
                    label="岗位职责"
                    value={toMultiline(selectedRoleMeta.node.responsibilities)}
                    disabled={!canEdit}
                    placeholder="每行一条岗位职责"
                    multiline
                    onChange={(next) => updateRole(selectedRoleMeta.node.id, { responsibilities: fromMultiline(next) })}
                  />
                  <DrawerTextarea
                    label="不该长期承担的事务"
                    value={toMultiline(selectedRoleMeta.node.shouldAvoid)}
                    disabled={!canEdit}
                    placeholder="每行一条"
                    multiline
                    onChange={(next) => updateRole(selectedRoleMeta.node.id, { shouldAvoid: fromMultiline(next) })}
                  />
                  <div className="grid grid-cols-3 gap-3">
                    <InfoMetricCard label="成员数" value={`${selectedRoleMeta.memberIds.length}`} />
                    <InfoMetricCard label="流程状态" value={selectedRoleMeta.processStatus} />
                    <InfoMetricCard label="模板状态" value={selectedRoleMeta.templateStatus} />
                  </div>
                  <DrawerActionRow
                    actions={[
                      {
                        label: '补流程',
                        icon: Workflow,
                        onClick: () => createProcessTemplateForRole(selectedRoleMeta.node.id),
                        disabled: !canEdit,
                      },
                      {
                        label: '补模板',
                        icon: FileText,
                        onClick: () => createRuleTemplateForRole(selectedRoleMeta.node.id),
                        disabled: !canEdit,
                      },
                      {
                        label: '新增成员',
                        icon: UserPlus,
                        onClick: () => addMember(selectedRoleMeta.node.id),
                        disabled: !canEdit || unboundEmployees.length === 0,
                      },
                    ]}
                  />
                  <label className="space-y-2">
                    <span className="text-[12px] font-bold text-gray-700">绑定成员</span>
                    <select
                      value={memberDraftUserId}
                      onChange={(event) => setMemberDraftUserId(event.target.value)}
                      disabled={!canEdit}
                      className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                    >
                      <option value="">选择未绑定成员</option>
                      {unboundEmployees.map((employee) => (
                        <option key={employee.id} value={employee.id}>
                          {employee.fullName}
                        </option>
                      ))}
                    </select>
                  </label>
                  <DrawerInfoBlock
                    title="缺失项提示"
                    helper="岗位节点主要看说明、流程模板、任务模板和成员覆盖。"
                    items={selectedRoleMeta.missing.length > 0 ? selectedRoleMeta.missing : ['该岗位的说明、流程和模板都已补齐']}
                  />
                  <DrawerInfoBlock
                    title="关联项目"
                    helper="这里先展示与该岗位成员绑定的项目标签。"
                    items={selectedRoleMeta.relatedProjects.length > 0 ? selectedRoleMeta.relatedProjects : ['当前暂无关联项目']}
                    icon={FolderKanban}
                  />
                </div>
              ) : null}

              {selectedMemberMeta ? (
                <div className="space-y-5">
                  <DrawerHeader
                    icon={Users}
                    title={selectedMemberMeta.node.fullName}
                    subtitle="成员节点"
                    tone="amber"
                  />
                  <div className="grid grid-cols-2 gap-3">
                    <InfoMetricCard label="当前岗位" value={selectedMemberMeta.roleName} />
                    <InfoMetricCard label="任务负荷" value={selectedMemberMeta.workloadLabel} />
                    <InfoMetricCard label="项目数" value={`${selectedMemberMeta.projectCount}`} />
                    <InfoMetricCard label="部门" value={selectedMemberMeta.departmentName} />
                  </div>
                  <label className="space-y-2">
                    <span className="text-[12px] font-bold text-gray-700">岗位归属</span>
                    <select
                      value={selectedMemberMeta.binding.primaryRoleId || ''}
                      onChange={(event) => {
                        const roleId = event.target.value || null;
                        const role = roleId ? roleById.get(roleId) : null;
                        updateBinding(selectedMemberMeta.node.id, {
                          primaryRoleId: roleId,
                          departmentId: role?.departmentId || null,
                        });
                      }}
                      disabled={!canEdit}
                      className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                    >
                      <option value="">未绑定岗位</option>
                      {activeRoles.map((role) => (
                        <option key={role.id} value={role.id}>
                          {role.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-2">
                    <span className="text-[12px] font-bold text-gray-700">直属上级</span>
                    <select
                      value={selectedMemberMeta.binding.managerUserId || ''}
                      onChange={(event) => updateBinding(selectedMemberMeta.node.id, { managerUserId: event.target.value || null })}
                      disabled={!canEdit}
                      className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                    >
                      <option value="">未指定上级</option>
                      {activeEmployees
                        .filter((employee) => employee.id !== selectedMemberMeta.node.id)
                        .map((employee) => (
                          <option key={employee.id} value={employee.id}>
                            {employee.fullName}
                          </option>
                        ))}
                    </select>
                  </label>
                  <DrawerTextarea
                    label="当前重心"
                    value={selectedMemberMeta.binding.currentFocus}
                    disabled={!canEdit}
                    placeholder="当前主责方向"
                    onChange={(next) => updateBinding(selectedMemberMeta.node.id, { currentFocus: next })}
                  />
                  <DrawerTextarea
                    label="关联项目"
                    value={toMultiline(selectedMemberMeta.binding.projectRoleLabels)}
                    disabled={!canEdit}
                    placeholder="每行一个项目标签"
                    multiline
                    onChange={(next) => updateBinding(selectedMemberMeta.node.id, { projectRoleLabels: fromMultiline(next) })}
                  />
                  <DrawerInfoBlock
                    title="节点提示"
                    helper="成员节点先看岗位归属、任务负荷和项目数量。后续 AI 会基于这些字段判断成员是否超载、是否需要协作补位。"
                    items={[
                      selectedMemberMeta.binding.primaryRoleId ? '岗位已绑定' : '待绑定岗位',
                      selectedMemberMeta.binding.managerUserId ? '直属上级已绑定' : '待绑定直属上级',
                      selectedMemberMeta.projectCount > 0 ? `已关联 ${selectedMemberMeta.projectCount} 个项目` : '当前暂无关联项目',
                    ]}
                  />
                </div>
              ) : null}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function DepartmentStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-white px-3 py-3 shadow-sm">
      <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-gray-400">{label}</p>
      <p className="mt-1 text-[13px] font-bold text-gray-900">{value}</p>
    </div>
  );
}

function InfoMetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[20px] border border-gray-200 bg-gray-50 px-4 py-3">
      <p className="text-[11px] font-medium text-gray-500">{label}</p>
      <p className="mt-1 text-[13px] font-bold text-gray-900">{value}</p>
    </div>
  );
}

function DrawerTextarea({
  label,
  value,
  placeholder,
  disabled,
  multiline = false,
  onChange,
}: {
  label: string;
  value: string;
  placeholder: string;
  disabled: boolean;
  multiline?: boolean;
  onChange: (next: string) => void;
}) {
  return (
    <label className="space-y-2">
      <span className="text-[12px] font-bold text-gray-700">{label}</span>
      {multiline ? (
        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          className="min-h-[104px] w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] leading-6 outline-none resize-none"
        />
      ) : (
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium outline-none"
        />
      )}
    </label>
  );
}

function DrawerHeader({
  icon: Icon,
  title,
  subtitle,
  tone,
}: {
  icon: typeof Building2;
  title: string;
  subtitle: string;
  tone: 'blue' | 'emerald' | 'violet' | 'amber';
}) {
  const toneClass =
    tone === 'emerald'
      ? 'bg-emerald-50 text-emerald-600'
      : tone === 'violet'
      ? 'bg-violet-50 text-violet-600'
      : tone === 'amber'
      ? 'bg-amber-50 text-amber-600'
      : 'bg-blue-50 text-[#5B7BFE]';
  return (
    <div className="rounded-[24px] border border-gray-100 bg-gray-50/70 p-4">
      <div className={`inline-flex h-11 w-11 items-center justify-center rounded-2xl shadow-sm ${toneClass}`}>
        <Icon size={18} />
      </div>
      <p className="mt-3 text-[11px] font-bold uppercase tracking-[0.16em] text-gray-400">{subtitle}</p>
      <h4 className="mt-1 text-[20px] font-bold tracking-tight text-gray-900">{title}</h4>
    </div>
  );
}

function DrawerInfoBlock({
  title,
  helper,
  items,
  icon: Icon = AlertTriangle,
}: {
  title: string;
  helper: string;
  items: string[];
  icon?: typeof AlertTriangle;
}) {
  return (
    <div className="rounded-[24px] border border-gray-200 bg-white p-4">
      <div className="flex items-start gap-3">
        <div className="inline-flex h-9 w-9 items-center justify-center rounded-2xl bg-gray-50 text-gray-500">
          <Icon size={16} />
        </div>
        <div>
          <h5 className="text-[13px] font-bold text-gray-900">{title}</h5>
          <p className="mt-1 text-[12px] leading-6 text-gray-500">{helper}</p>
        </div>
      </div>
      <div className="mt-4 space-y-2">
        {items.map((item) => (
          <div key={item} className="flex items-start gap-2 rounded-2xl bg-gray-50 px-3 py-3 text-[12px] text-gray-700">
            {item.startsWith('待') || item.startsWith('当前暂无') ? (
              <AlertTriangle size={14} className="mt-0.5 shrink-0 text-amber-500" />
            ) : (
              <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-emerald-500" />
            )}
            <span>{item}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function DrawerActionRow({
  actions,
}: {
  actions: Array<{ label: string; icon: typeof Plus; onClick: () => void; disabled?: boolean }>;
}) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {actions.map((action) => {
        const Icon = action.icon;
        return (
          <button
            key={action.label}
            type="button"
            onClick={action.onClick}
            disabled={action.disabled}
            className="inline-flex items-center justify-center gap-2 rounded-2xl border border-[#DCE4FF] bg-white px-4 py-3 text-[12px] font-bold text-[#4A63CF] shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Icon size={14} />
            {action.label}
          </button>
        );
      })}
    </div>
  );
}
~~~

## `src/renderer/components/settings/ReviewGovernanceSettingsPanel.tsx`

- 编码: `utf-8`

~~~tsx
import type { ReviewDepartmentConfig, ReviewDepartmentMember, ReviewGovernanceSettings } from '../../../shared/types';

const GOVERNANCE_COLORS = ['#5B7BFE', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#14B8A6'];

type ReviewGovernanceSettingsPanelProps = {
  value: ReviewGovernanceSettings;
  canEdit: boolean;
  availableMembers: ReviewDepartmentMember[];
  isSaving?: boolean;
  onChange: (next: ReviewGovernanceSettings) => void;
  onSave: () => void;
};

function dedupeMembers(members: ReviewDepartmentMember[]) {
  const seen = new Set<string>();
  const next: ReviewDepartmentMember[] = [];
  members.forEach((member) => {
    const fullName = member.fullName.trim();
    if (!fullName) return;
    const key = fullName.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    next.push({ ...member, fullName });
  });
  return next;
}

function parseMembers(text: string, availableMembers: ReviewDepartmentMember[]) {
  const byName = new Map(availableMembers.map((member) => [member.fullName.trim().toLowerCase(), member]));
  const names = text
    .split(/[\n,，、]/)
    .map((item) => item.trim())
    .filter(Boolean);
  return dedupeMembers(
    names.map((name) => {
      const matched = byName.get(name.toLowerCase());
      return matched ? { ...matched } : { id: '', fullName: name };
    }),
  );
}

function toggleMember(members: ReviewDepartmentMember[], candidate: ReviewDepartmentMember) {
  const key = candidate.fullName.trim().toLowerCase();
  const exists = members.some((member) => member.fullName.trim().toLowerCase() === key);
  if (exists) {
    return members.filter((member) => member.fullName.trim().toLowerCase() !== key);
  }
  return dedupeMembers([...members, candidate]);
}

export function ReviewGovernanceSettingsPanel({
  value,
  canEdit,
  availableMembers,
  isSaving = false,
  onChange,
  onSave,
}: ReviewGovernanceSettingsPanelProps) {
  const updateDepartment = (index: number, updater: (current: ReviewDepartmentConfig) => ReviewDepartmentConfig) => {
    onChange({
      ...value,
      departments: value.departments.map((department, departmentIndex) => (departmentIndex === index ? updater(department) : department)),
    });
  };

  return (
    <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[16px] font-bold text-gray-900">周复盘聚合治理</h2>
          <p className="text-[12px] text-gray-500 mt-1">部门目录已固定为四个：咨询策略部、科技发展部、信息数据部、客户服务部。这里维护部门负责人、月度 DNA 和本周重点计划，成员归属默认跟随邀请码加入的部门。</p>
        </div>
        <button
          type="button"
          className="rounded-2xl bg-[#5B7BFE] px-4 py-2 text-[12px] font-bold text-white shadow-[0_10px_30px_rgba(91,123,254,0.24)] disabled:cursor-not-allowed disabled:opacity-50"
          onClick={onSave}
          disabled={!canEdit || isSaving}
        >
          {isSaving ? '保存中...' : '保存治理设置'}
        </button>
      </div>

      <div className="rounded-[24px] border border-blue-100 bg-blue-50/70 px-4 py-3 text-[12px] leading-6 text-[#4256C5]">
        普通同事不能新增部门，只能从机构已有四部门中选择自己的所属部门。CEO 在这里维护四部门的负责人、月度 DNA 和本周重点计划，周复盘部门聚合会直接使用这套配置。
      </div>

      <div className="space-y-4">
        {value.departments.map((department, index) => (
          <div key={department.id} className="rounded-[28px] border border-gray-200 bg-gray-50/70 p-5 space-y-4">
            <div className="flex items-center gap-3">
              <span className="h-3 w-3 rounded-full" style={{ backgroundColor: department.color || GOVERNANCE_COLORS[index % GOVERNANCE_COLORS.length] }} />
              <div>
                <p className="text-[14px] font-bold text-gray-900">{department.name || `部门 ${index + 1}`}</p>
                <p className="mt-1 text-[11px] text-gray-500">固定部门目录，不支持新增、删除或改名。</p>
              </div>
            </div>

            <textarea
              value={department.monthlyDna}
              onChange={(event) => updateDepartment(index, (current) => ({ ...current, monthlyDna: event.target.value }))}
              placeholder="填写这个部门本月主要做什么、为什么做、什么算偏离计划。"
              className="min-h-[96px] w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] leading-6 outline-none resize-none"
              disabled={!canEdit}
            />

            <textarea
              value={department.weeklyFocus}
              onChange={(event) => updateDepartment(index, (current) => ({ ...current, weeklyFocus: event.target.value }))}
              placeholder="填写这个部门本周最重要的 3-5 条重点计划、关键动作或必须收口的事项。"
              className="min-h-[88px] w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] leading-6 outline-none resize-none"
              disabled={!canEdit}
            />

            <div className="space-y-3 rounded-[24px] border border-gray-200 bg-white p-4">
              <div>
                <p className="text-[12px] font-bold text-gray-900">部门负责人</p>
                <p className="mt-1 text-[11px] leading-5 text-gray-500">这里配置的人可以在周复盘里看到“我的总结 + 本部门总结”。</p>
              </div>
              <textarea
                value={department.leaders.map((member) => member.fullName).join('、')}
                onChange={(event) => updateDepartment(index, (current) => ({ ...current, leaders: parseMembers(event.target.value, availableMembers) }))}
                placeholder="部门负责人，支持逗号、顿号或换行分隔。"
                className="min-h-[72px] w-full rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[13px] leading-6 outline-none resize-none"
                disabled={!canEdit}
              />
              {availableMembers.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {availableMembers.map((member) => {
                    const active = department.leaders.some((item) => item.fullName.trim().toLowerCase() === member.fullName.trim().toLowerCase());
                    return (
                      <button
                        key={`leader:${department.id}:${member.id}:${member.fullName}`}
                        type="button"
                        className={`rounded-full px-3 py-1.5 text-[11px] font-bold transition ${
                          active ? 'bg-emerald-500 text-white' : 'bg-gray-50 text-gray-600 border border-gray-200'
                        }`}
                        onClick={() => updateDepartment(index, (current) => ({ ...current, leaders: toggleMember(current.leaders, member) }))}
                        disabled={!canEdit}
                      >
                        {member.fullName}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="space-y-3 rounded-[24px] border border-gray-200 bg-white p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[12px] font-bold text-gray-900">部门成员</p>
                  <p className="mt-1 text-[11px] leading-5 text-gray-500">成员归属默认跟随邀请码加入的部门，不在这里手工输入。</p>
                </div>
                <span className="rounded-full bg-gray-100 px-3 py-1 text-[11px] font-bold text-gray-600">{department.members.length} 人</span>
              </div>
              {department.members.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {department.members.map((member) => (
                    <span key={`${department.id}:${member.id}:${member.fullName}`} className="rounded-full border border-gray-200 bg-gray-50 px-3 py-1.5 text-[11px] font-medium text-gray-700">
                      {member.fullName}
                    </span>
                  ))}
                </div>
              ) : (
                <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50 px-4 py-3 text-[12px] leading-6 text-gray-500">
                  当前还没有员工归属到这个部门。请先邀请成员通过对应部门的邀请码加入。
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {value.departments.length === 0 && (
        <div className="rounded-3xl border border-dashed border-gray-200 bg-gray-50 px-5 py-6 text-[13px] leading-6 text-gray-500">
          还没有加载到部门治理配置。请先检查当前机构部门目录是否可用。
        </div>
      )}
    </div>
  );
}
~~~

## `src/renderer/components/settings/SystemLogPanel.tsx`

- 编码: `utf-8`

~~~tsx
import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  Calendar,
  ClipboardCopy,
  Download,
  Filter,
  Info,
  Loader2,
  RefreshCw,
  Search,
  Send,
  X,
} from 'lucide-react';
import { getSystemLogs, exportSystemLogs, type SystemLogEntry, type SystemLogsResponse } from '../../lib/api';

const LEVEL_OPTIONS = ['', 'ERROR', 'WARN', 'INFO', 'DEBUG'] as const;
const SOURCE_OPTIONS = ['', 'api', 'activity', 'system'] as const;

function levelIcon(level: string) {
  if (level === 'ERROR') return <AlertCircle size={12} className="text-red-500" />;
  if (level === 'WARN') return <AlertTriangle size={12} className="text-amber-500" />;
  return <Info size={12} className="text-slate-400" />;
}

function levelBg(level: string) {
  if (level === 'ERROR') return 'bg-red-50 border-red-100';
  if (level === 'WARN') return 'bg-amber-50 border-amber-100';
  return 'bg-white border-slate-100';
}

function formatTs(ts: string) {
  if (!ts) return '';
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts.slice(0, 19);
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function SystemLogPanel() {
  const [logs, setLogs] = useState<SystemLogEntry[]>([]);
  const [dates, setDates] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  // Filters
  const today = new Date().toISOString().slice(0, 10);
  const [startDate, setStartDate] = useState(today);
  const [endDate, setEndDate] = useState(today);
  const [level, setLevel] = useState('');
  const [source, setSource] = useState('');
  const [keyword, setKeyword] = useState('');

  // Export states
  const [isExporting, setIsExporting] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copyMessage, setCopyMessage] = useState('');

  const loadLogs = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await getSystemLogs({
        startDate: startDate || undefined,
        endDate: endDate || undefined,
        level: level || undefined,
        source: source || undefined,
        keyword: keyword || undefined,
        limit: 500,
      });
      setLogs(res.entries);
      setDates(res.dates);
    } catch {
      setLogs([]);
    } finally {
      setIsLoading(false);
    }
  }, [startDate, endDate, level, source, keyword]);

  useEffect(() => {
    void loadLogs();
  }, []);

  const handleExport = async (mode: 'today' | 'range') => {
    setIsExporting(true);
    try {
      const params = mode === 'today'
        ? { startDate: today, endDate: today }
        : { startDate, endDate, level: level || undefined, keyword: keyword || undefined };
      const md = await exportSystemLogs(params);
      const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `yiyu-logs-${mode === 'today' ? today : `${startDate}-${endDate}`}.md`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('导出日志失败', err);
    } finally {
      setIsExporting(false);
    }
  };

  const handleCopyForSupport = async () => {
    setCopied(false);
    setCopyMessage('');
    try {
      const md = await exportSystemLogs({ startDate: today, endDate: today, level: 'ERROR' });
      if (!md || !md.trim()) {
        setCopyMessage('今天没有错误日志，无需复制。');
        setTimeout(() => setCopyMessage(''), 4000);
        return;
      }
      await navigator.clipboard.writeText(md);
      setCopied(true);
      setCopyMessage('已复制到剪贴板，可以直接粘贴给技术支持。');
      setTimeout(() => { setCopied(false); setCopyMessage(''); }, 5000);
    } catch {
      setCopyMessage('复制失败，请手动导出后复制。');
      setTimeout(() => setCopyMessage(''), 4000);
    }
  };

  const errorCount = logs.filter((l) => l.level === 'ERROR').length;
  const warnCount = logs.filter((l) => l.level === 'WARN').length;

  return (
    <div className="space-y-5">
      {/* Stats bar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-50 border border-slate-100 text-[12px] font-semibold text-slate-500">
          共 {logs.length} 条
        </div>
        {errorCount > 0 && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-red-50 border border-red-100 text-[12px] font-semibold text-red-600">
            <AlertCircle size={12} /> {errorCount} 个错误
          </div>
        )}
        {warnCount > 0 && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-amber-50 border border-amber-100 text-[12px] font-semibold text-amber-600">
            <AlertTriangle size={12} /> {warnCount} 个警告
          </div>
        )}
        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            onClick={() => void loadLogs()}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-slate-200 text-[12px] font-medium text-slate-500 hover:bg-slate-50 transition-colors"
          >
            <RefreshCw size={12} className={isLoading ? 'animate-spin' : ''} /> 刷新
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 items-center">
        <div className="flex items-center gap-1.5">
          <Calendar size={12} className="text-slate-400" />
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="border border-slate-200 rounded-lg px-2.5 py-1.5 text-[12px] text-slate-700 bg-white outline-none focus:border-blue-300"
          />
          <span className="text-[11px] text-slate-400">至</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="border border-slate-200 rounded-lg px-2.5 py-1.5 text-[12px] text-slate-700 bg-white outline-none focus:border-blue-300"
          />
        </div>
        <select
          value={level}
          onChange={(e) => setLevel(e.target.value)}
          className="border border-slate-200 rounded-lg px-2.5 py-1.5 text-[12px] text-slate-700 bg-white outline-none"
        >
          <option value="">全部级别</option>
          <option value="ERROR">ERROR</option>
          <option value="WARN">WARN</option>
          <option value="INFO">INFO</option>
        </select>
        <select
          value={source}
          onChange={(e) => setSource(e.target.value)}
          className="border border-slate-200 rounded-lg px-2.5 py-1.5 text-[12px] text-slate-700 bg-white outline-none"
        >
          <option value="">全部来源</option>
          <option value="api">API 请求</option>
          <option value="activity">业务操作</option>
          <option value="system">系统事件</option>
        </select>
        <div className="relative flex-1 min-w-[160px]">
          <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="搜索关键词..."
            className="w-full border border-slate-200 rounded-lg pl-7 pr-2.5 py-1.5 text-[12px] text-slate-700 bg-white outline-none focus:border-blue-300"
          />
        </div>
        <button
          type="button"
          onClick={() => void loadLogs()}
          className="px-4 py-1.5 rounded-lg bg-[#335CFE] text-white text-[12px] font-medium hover:bg-[#2C50E0] transition-colors"
        >
          查询
        </button>
      </div>

      {/* Export buttons */}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => void handleExport('today')}
          disabled={isExporting}
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl border border-slate-200 text-[12px] font-medium text-slate-600 hover:bg-slate-50 transition-colors disabled:opacity-50"
        >
          <Download size={14} /> 导出今天的日志
        </button>
        <button
          type="button"
          onClick={() => void handleExport('range')}
          disabled={isExporting}
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl border border-slate-200 text-[12px] font-medium text-slate-600 hover:bg-slate-50 transition-colors disabled:opacity-50"
        >
          <Download size={14} /> 导出选定范围
        </button>
        <button
          type="button"
          onClick={() => void handleCopyForSupport()}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-xl border text-[12px] font-medium transition-colors ${
            copied
              ? 'border-emerald-300 bg-emerald-50 text-emerald-700'
              : 'border-blue-200 bg-blue-50 text-blue-600 hover:bg-blue-100'
          }`}
        >
          {copied ? <><ClipboardCopy size={14} /> 已复制到剪贴板 — 可直接粘贴</> : <><Send size={14} /> 一键复制错误日志（提交给官方）</>}
        </button>
      </div>

      {copyMessage && (
        <div className={`flex items-center gap-2 px-4 py-3 rounded-2xl text-[13px] font-medium ${
          copied
            ? 'border border-emerald-200 bg-emerald-50 text-emerald-700'
            : 'border border-amber-200 bg-amber-50 text-amber-700'
        }`}>
          {copied ? <ClipboardCopy size={14} /> : <AlertTriangle size={14} />}
          {copyMessage}
        </div>
      )}

      {/* Log list */}
      <div className="space-y-1.5 max-h-[60vh] overflow-y-auto">
        {isLoading && logs.length === 0 ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 size={20} className="text-slate-300 animate-spin" />
          </div>
        ) : logs.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-[13px] text-slate-400">暂无日志数据</p>
            <p className="text-[11px] text-slate-300 mt-1">使用软件后日志会自动记录</p>
          </div>
        ) : (
          logs.map((entry, idx) => {
            const isExpanded = expandedIdx === idx;
            const hasDetail = entry.traceback || entry.error || entry.detail || entry.duration_ms;

            return (
              <div
                key={idx}
                className={`rounded-[14px] border px-4 py-2.5 cursor-pointer transition-colors ${levelBg(entry.level)} ${isExpanded ? 'shadow-sm' : ''}`}
                onClick={() => setExpandedIdx(isExpanded ? null : idx)}
              >
                <div className="flex items-center gap-2">
                  {levelIcon(entry.level)}
                  <span className="text-[10px] font-mono text-slate-400 shrink-0">{formatTs(entry.ts)}</span>
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                    entry.level === 'ERROR' ? 'bg-red-100 text-red-700' : entry.level === 'WARN' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-500'
                  }`}>
                    {entry.level}
                  </span>
                  <span className="text-[10px] font-medium text-slate-400">{entry.source}</span>
                  <span className="text-[12px] font-medium text-slate-700 truncate flex-1">{entry.message}</span>
                  {entry.duration_ms != null && (
                    <span className="text-[10px] font-mono text-slate-400 shrink-0">{entry.duration_ms}ms</span>
                  )}
                  {entry.user && (
                    <span className="text-[10px] font-medium text-slate-400 shrink-0">{entry.user}</span>
                  )}
                </div>

                {isExpanded && hasDetail && (
                  <div className="mt-3 pt-3 border-t border-slate-100 space-y-2">
                    {entry.error && (
                      <div>
                        <span className="text-[10px] font-bold text-red-600 uppercase">错误信息</span>
                        <p className="text-[12px] text-red-700 font-mono mt-1 bg-red-50 rounded-lg p-2">{entry.error}</p>
                      </div>
                    )}
                    {entry.traceback && (
                      <div>
                        <span className="text-[10px] font-bold text-slate-500 uppercase">调用栈</span>
                        <pre className="text-[10px] text-slate-600 font-mono mt-1 bg-slate-50 rounded-lg p-2 overflow-x-auto max-h-[200px] overflow-y-auto whitespace-pre-wrap">
                          {entry.traceback}
                        </pre>
                      </div>
                    )}
                    {entry.path && (
                      <div className="flex flex-wrap gap-3 text-[11px] text-slate-500">
                        <span>请求：<code className="font-mono">{entry.method} {entry.path}</code></span>
                        <span>状态码：<code className="font-mono">{entry.status}</code></span>
                        {entry.duration_ms != null && <span>耗时：<code className="font-mono">{entry.duration_ms}ms</code></span>}
                      </div>
                    )}
                    {entry.detail && (
                      <div>
                        <span className="text-[10px] font-bold text-slate-500 uppercase">详情</span>
                        <pre className="text-[10px] text-slate-600 font-mono mt-1 bg-slate-50 rounded-lg p-2 overflow-x-auto">
                          {JSON.stringify(entry.detail, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

export default SystemLogPanel;
~~~

## `src/renderer/components/settings/UpdateSettingsPanel.tsx`

- 编码: `utf-8`

~~~tsx
import { FolderOpen, RefreshCw, Rocket } from 'lucide-react';
import type { DesktopAppInfo } from '../../../shared/types';

type UpdateSettingsPanelProps = {
  appInfo: DesktopAppInfo | null;
  onOpenPlan: () => void;
  onOpenArtifacts: () => void;
  onRevealPath: (targetPath: string) => void;
};

function phaseLabel(phase: DesktopAppInfo['updaterPhase']) {
  switch (phase) {
    case 'planning':
      return 'P0 规划完成';
    case 'preparing_release':
      return 'P1 打包底座收口中';
    case 'ready_for_feed':
      return 'P2 更新源待接入';
    case 'ready_for_in_app_update':
      return 'P3 可进入应用内更新开发';
    default:
      return '阶段未定义';
  }
}

export function UpdateSettingsPanel({ appInfo, onOpenPlan, onOpenArtifacts, onRevealPath }: UpdateSettingsPanelProps) {
  return (
    <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[16px] font-bold text-gray-900">版本与更新</h2>
          <p className="text-[12px] text-gray-500 mt-1">
            当前先按官网分发版推进。第一次从官网下载安装，后续版本通过软件内更新能力完成下载与安装。
          </p>
        </div>
        <span className="rounded-full bg-blue-50 px-3 py-1.5 text-[11px] font-bold text-[#335CFF]">
          {appInfo ? phaseLabel(appInfo.updaterPhase) : '正在读取桌面信息'}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-[24px] border border-gray-200 bg-gray-50 px-4 py-4">
          <p className="text-[11px] font-bold text-gray-500 uppercase tracking-[0.16em]">当前版本</p>
          <p className="mt-3 text-[18px] font-bold text-gray-900">{appInfo?.appVersion || '读取中…'}</p>
          <p className="mt-2 text-[12px] text-gray-500">
            {appInfo ? `${appInfo.platform} · ${appInfo.arch}` : '等待主进程返回版本信息'}
          </p>
        </div>
        <div className="rounded-[24px] border border-gray-200 bg-gray-50 px-4 py-4">
          <p className="text-[11px] font-bold text-gray-500 uppercase tracking-[0.16em]">当前形态</p>
          <p className="mt-3 text-[18px] font-bold text-gray-900">{appInfo?.isPackaged ? '打包态' : '开发态'}</p>
          <p className="mt-2 text-[12px] text-gray-500">
            {appInfo ? `默认渠道：${appInfo.updateChannel}` : '尚未进入正式分发状态'}
          </p>
        </div>
        <div className="rounded-[24px] border border-gray-200 bg-gray-50 px-4 py-4">
          <p className="text-[11px] font-bold text-gray-500 uppercase tracking-[0.16em]">当前更新能力</p>
          <p className="mt-3 text-[18px] font-bold text-gray-900">规划与入口已落</p>
          <p className="mt-2 text-[12px] text-gray-500">下一步先收口签名、公证、更新源，再接自动下载。</p>
        </div>
      </div>

      <div className="rounded-[28px] border border-blue-100 bg-blue-50/70 px-5 py-4 text-[12px] leading-6 text-[#4256C5]">
        这版先把“官网分发 + 应用内更新”的路线固定下来。真正的自动更新按钮会在签名、公证和官网更新源准备完成后再接入，避免在错误的底座上做表面功能。
      </div>

      <div className={`rounded-[28px] border px-5 py-4 text-[12px] leading-6 ${appInfo?.installStatus === 'warning' ? 'border-amber-200 bg-amber-50 text-amber-800' : 'border-emerald-200 bg-emerald-50 text-emerald-800'}`}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.16em]">安装入口自检</p>
            <p className="mt-2 font-semibold">
              {appInfo?.installWarning || '当前只检测到单一入口，装错包风险较低。'}
            </p>
            {appInfo?.appBundlePath && (
              <div className="mt-3 rounded-2xl bg-white/80 px-3 py-3 text-[11px] text-slate-600">
                <p className="font-bold text-slate-800">当前运行包</p>
                <p className="mt-1 break-all">{appInfo.appBundlePath}</p>
              </div>
            )}
            {appInfo?.recommendedInstallPath && (
              <div className="mt-3 rounded-2xl bg-white/80 px-3 py-3 text-[11px] text-slate-600">
                <p className="font-bold text-slate-800">唯一建议安装入口</p>
                <p className="mt-1 break-all">{appInfo.recommendedInstallPath}</p>
                <p className="mt-2 text-[11px] text-slate-500">日常只从这个路径启动，避免继续误开历史包或临时构建包。</p>
              </div>
            )}
          </div>
          {appInfo?.appBundlePath && (
            <button
              type="button"
              className="rounded-2xl border border-current/20 bg-white/80 px-3 py-2 text-[11px] font-bold hover:bg-white"
              onClick={() => onRevealPath(appInfo.appBundlePath)}
            >
              定位当前包
            </button>
          )}
        </div>

        {appInfo && appInfo.detectedAppPaths.length > 1 && (
          <div className="mt-4 space-y-2">
            <p className="text-[11px] font-bold uppercase tracking-[0.16em]">检测到的相关安装包</p>
            <div className="space-y-2">
              {appInfo.detectedAppPaths.map((targetPath) => {
                const isCurrent = targetPath === appInfo.appBundlePath;
                const isLegacy = appInfo.legacyAppPaths.includes(targetPath);
                return (
                  <div key={targetPath} className="flex items-center justify-between gap-3 rounded-2xl bg-white/80 px-3 py-3 text-[11px]">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-bold text-slate-800">{isCurrent ? '当前运行包' : isLegacy ? '旧入口' : '重复安装包'}</span>
                        {isLegacy && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-700">建议清理</span>}
                      </div>
                      <p className="mt-1 break-all text-slate-600">{targetPath}</p>
                    </div>
                    <button
                      type="button"
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[11px] font-bold text-gray-700 hover:bg-gray-50"
                      onClick={() => onRevealPath(targetPath)}
                    >
                      在 Finder 中显示
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-2xl bg-[#5B7BFE] px-5 py-3 text-[13px] font-bold text-white shadow-sm hover:bg-[#4a6be6]"
          onClick={onOpenPlan}
        >
          <Rocket size={15} />
          查看完整计划
        </button>
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-5 py-3 text-[13px] font-bold text-gray-700 shadow-sm hover:bg-gray-50"
          onClick={onOpenArtifacts}
        >
          <FolderOpen size={15} />
          打开构建产物目录
        </button>
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-5 py-3 text-[13px] font-bold text-gray-400 shadow-sm cursor-not-allowed"
          disabled
        >
          <RefreshCw size={15} />
          检查更新（待接入）
        </button>
      </div>
    </div>
  );
}
~~~

## `src/renderer/components/strategic_accompaniment/StrategicBrainView.tsx`

- 编码: `utf-8`

~~~tsx
import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  BrainCircuit, Sparkles, FileText, CheckCircle, MessageCircle,
  GitBranch, BookOpen, Award, Layers, ChevronDown,
  AlertCircle, ClipboardList, Check, Folder, Target, FolderTree,
  Activity, Bot, Clock, User, PenLine, Calendar,
  ArrowLeft, AlertTriangle, ChevronRight, XCircle,
  Users, Flag, AlertOctagon, HelpCircle, CornerDownRight
} from 'lucide-react';
import {
  getBrainDashboard,
  getStrategicCockpit,
  getStrategicThoughts,
  reviewStrategicThought,
  type BrainDashboard,
  type BrainPulse,
  type BrainClientData,
  type StrategicThought,
} from '../../lib/api';
import type { GrowthContextLink, Task, StrategicCockpitSnapshot } from '../../../shared/types';
import { StrategicLearningListPanel, type StrategicLearningTaskPayload } from './StrategicLearningListPanel';

const TABS = [
  { id: 'pulse', label: '大脑脉搏' },
  { id: 'thoughts', label: '思考与研判' },
  { id: 'clients', label: '项目认知' },
  { id: 'learning', label: '学习清单' }
];

const PULSE_METRICS_1 = [
  { icon: BrainCircuit, label: '组织记忆', value: '1,847' },
  { icon: FileText, label: '资料归档', value: '390' },
  { icon: CheckCircle, label: '任务追踪', value: '19' },
  { icon: MessageCircle, label: 'AI 对话', value: '549' },
];

const PULSE_METRICS_2 = [
  { icon: GitBranch, label: '事件线', value: '8' },
  { icon: BookOpen, label: '知识画像', value: '19' },
  { icon: Award, label: '成长徽章', value: '4' },
  { icon: Layers, label: '经验沉淀', value: '5' },
];

export type ThoughtTaskPayload = {
  suggestion: string;
  ceoComment: string;
  thoughtLine: string;
  clientId: string;
  dueDate: string;
  thoughtId?: string;
  sources?: StrategicThought['sources'];
  evidenceCount?: number;
  confidence?: number | null;
  clientName?: string;
};

// --- Helpers ---

const getConfColor = (conf?: number) => {
  if (conf === undefined) return '#94a3b8';
  if (conf >= 70) return '#3b82f6';
  if (conf >= 50) return '#f59e0b';
  return '#ef4444';
};

const getConfBg = (conf?: number) => {
  if (conf === undefined) return 'bg-slate-100 text-slate-500';
  if (conf >= 70) return 'bg-blue-50 text-blue-600';
  if (conf >= 50) return 'bg-amber-50 text-amber-600';
  return 'bg-red-50 text-red-600';
};

const INTERNAL_KEY_SET = new Set([
  'client_overview',
  'org_overview',
  'project_overview',
  'main_contradiction',
  'core_breakthrough',
  'pending_material',
  'pending_decision',
]);

const INTERNAL_KEY_REGEX = /^[a-z]+(?:_[a-z0-9]+)+$/;

function _isInternalKeyText(value: string | null | undefined): boolean {
  const normalized = (value || '').trim().toLowerCase();
  if (!normalized) return false;
  return INTERNAL_KEY_SET.has(normalized) || INTERNAL_KEY_REGEX.test(normalized);
}

function _normalizeTextForUI(value: string | null | undefined): string {
  const text = (value || '').trim();
  if (!text) return '';
  const compact = text.replace(/\s+/g, ' ');
  if (_isInternalKeyText(compact)) return '系统发现一条待确认判断。';
  return compact;
}

function _buildThoughtLineHint(thought: StrategicThought): string {
  if (thought.status === 'confirmed') return '已由人工确认';
  if (thought.status === 'task_created') return '已转入任务跟进';
  if (thought.status === 'waiting_evidence') return '资料不足，暂不构成正式判断';
  return '系统候选，需人工确认';
}

function useClickOutside(ref: React.RefObject<HTMLElement | null>, handler: (event: MouseEvent) => void) {
  useEffect(() => {
    const listener = (event: MouseEvent) => {
      if (!ref.current || ref.current.contains(event.target as Node)) return;
      handler(event);
    };
    document.addEventListener("mousedown", listener);
    return () => document.removeEventListener("mousedown", listener);
  }, [ref, handler]);
}

// --- Detail View Components ---

function DetailHeader({
  clientName,
  stageLabel,
  readinessScore,
  onBack,
}: {
  clientName: string;
  stageLabel: string;
  readinessScore: number | null;
  onBack: () => void;
}) {
  return (
    <header className="sticky top-0 left-0 right-0 bg-white/90 backdrop-blur-xl border-b border-slate-200/60 z-50 px-6 sm:px-8 py-4 flex items-center justify-between shadow-sm">
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={onBack}
          className="w-8 h-8 rounded-full border border-slate-200 flex items-center justify-center hover:bg-slate-50 transition-colors"
        >
          <ArrowLeft size={16} className="text-slate-600" />
        </button>
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold text-slate-800">{clientName}</h1>
          <span className="bg-slate-100 border border-slate-200 text-slate-600 text-[11px] font-bold px-2.5 py-1 rounded-lg">
            {stageLabel || '待判断'}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <div className={`px-3 py-1.5 rounded-full text-[12px] font-bold flex items-center gap-1.5 ${getConfBg(readinessScore ?? undefined)}`}>
          <Activity size={14} className="opacity-80" />
          Readiness {readinessScore ?? '--'}%
        </div>
      </div>
    </header>
  );
}

function DimensionGrid({ snapshot }: { snapshot: StrategicCockpitSnapshot }) {
  const dimensions = [
    { name: '战略线', value: `${snapshot.strategicLines.length} 条`, status: snapshot.strategicLines.length > 0 ? 'ready' : 'missing' },
    { name: '待拍板事项', value: `${snapshot.pendingDecisions.length} 项`, status: snapshot.pendingDecisions.length > 0 ? 'weak' : 'ready' },
    { name: '待补材料', value: `${snapshot.pendingMaterials.length} 项`, status: snapshot.pendingMaterials.length > 0 ? 'missing' : 'ready' },
    { name: '关键事实', value: `${snapshot.evidencePreview.keyFacts.length} 条`, status: snapshot.evidencePreview.keyFacts.length > 0 ? 'ready' : 'weak' },
    { name: '风险提醒', value: `${snapshot.evidencePreview.keyWarnings.length} 条`, status: snapshot.evidencePreview.keyWarnings.length > 0 ? 'weak' : 'ready' },
    { name: '线索卡片', value: `${snapshot.evidencePreview.cards.length} 张`, status: snapshot.evidencePreview.cards.length > 0 ? 'ready' : 'missing' },
  ];
  const readyCount = dimensions.filter((d) => d.status === 'ready').length;
  return (
    <div className="mt-8">
      <div className="flex items-baseline justify-between mb-4 px-1">
        <h2 className="text-[15px] font-bold text-slate-800">认知维度</h2>
        <span className="text-[12px] font-bold text-blue-600">就绪 {readyCount}/{dimensions.length}</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-2.5">
        {dimensions.map((dim, i) => {
          const isReady = dim.status === 'ready';
          const isWeak = dim.status === 'weak';
          return (
            <div key={i} className="bg-white rounded-[16px] border border-slate-100 p-3.5 min-h-[80px] shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
              <div className="flex items-start gap-2 mb-2">
                {isReady && <CheckCircle size={12} className="text-emerald-500 mt-0.5 shrink-0" />}
                {isWeak && <AlertTriangle size={12} className="text-amber-500 mt-0.5 shrink-0" />}
                {!isReady && !isWeak && <XCircle size={12} className="text-red-500 mt-0.5 shrink-0" />}
                <span className={`text-[12px] font-bold ${isReady || isWeak ? 'text-slate-800' : 'text-slate-400'}`}>
                  {dim.name}
                </span>
              </div>
              <div className="flex items-center gap-1.5 pl-5">
                {isReady && <span className="text-[11px] font-semibold text-slate-500">{dim.value}</span>}
                {isWeak && (
                  <>
                    <span className="text-[11px] font-semibold text-slate-500">{dim.value}</span>
                    <span className="bg-orange-50 text-orange-600 text-[9px] font-bold px-1.5 py-0.5 rounded-full">薄弱</span>
                  </>
                )}
                {!isReady && !isWeak && (
                  <span className="bg-red-50 text-red-600 text-[9px] font-bold px-1.5 py-0.5 rounded-full">未就绪</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ProjectDetailView({ clientId, onBack }: { clientId: string; onBack: () => void }) {
  const [snapshot, setSnapshot] = useState<StrategicCockpitSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);
    getStrategicCockpit(clientId)
      .then((result) => {
        if (!mounted) return;
        setSnapshot(result);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : '加载失败');
        setSnapshot(null);
      })
      .finally(() => {
        if (!mounted) return;
        setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [clientId]);

  if (loading) {
    return (
      <div className="animate-in fade-in duration-300">
        <DetailHeader clientName="项目认知" stageLabel="加载中" readinessScore={null} onBack={onBack} />
        <div className="max-w-full mx-auto px-6 py-8 pb-24 text-[13px] text-slate-500">正在加载项目认知详情...</div>
      </div>
    );
  }

  if (error || !snapshot) {
    return (
      <div className="animate-in fade-in duration-300">
        <DetailHeader clientName="项目认知" stageLabel="资料不足" readinessScore={null} onBack={onBack} />
        <div className="max-w-full mx-auto px-6 py-8 pb-24">
          <div className="rounded-2xl border border-amber-100 bg-amber-50 px-5 py-4">
            <p className="text-[14px] font-bold text-amber-700">这个项目的认知详情还没有生成</p>
            <p className="text-[13px] mt-2 text-amber-700/80">建议先补充资料或生成战略驾驶舱。{error ? `（${error}）` : ''}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-in fade-in duration-300">
      <DetailHeader
        clientName={snapshot.clientName}
        stageLabel={snapshot.stageLabel}
        readinessScore={snapshot.readiness?.score ?? null}
        onBack={onBack}
      />
      <div className="max-w-full mx-auto px-6 py-8 pb-24">
        <section
          className="rounded-[28px] border border-blue-100 p-6 sm:p-8 relative"
          style={{
            backgroundImage: 'radial-gradient(circle at top left, rgba(51,92,254,0.04), transparent 40%), linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)',
            boxShadow: '0 10px 40px -10px rgba(51,92,254,0.06)'
          }}
        >
          <div className="inline-flex items-center gap-1.5 bg-blue-50/80 border border-blue-100/80 rounded-full px-3.5 py-1.5 mb-6 shadow-sm">
            <BrainCircuit size={14} className="text-blue-600" />
            <span className="text-[12px] font-bold text-blue-600 tracking-wide">系统对项目的当前认知</span>
          </div>
          <div className="space-y-6 text-[13px] text-slate-700">
            <div>
              <h3 className="text-[13px] font-bold text-slate-800 mb-2 flex items-center gap-1.5">
                <Target size={14} className="text-blue-500" /> 本周核心判断
              </h3>
              <p className="pl-5 leading-[1.9]">
                {_normalizeTextForUI(snapshot.headline.mainContradiction.value) || '当前暂无稳定判断，请先补证。'}
              </p>
            </div>
            <div>
              <h3 className="text-[13px] font-bold text-slate-800 mb-2 flex items-center gap-1.5">
                <Flag size={14} className="text-blue-500" /> 核心突破口
              </h3>
              <p className="pl-5 leading-[1.9]">
                {_normalizeTextForUI(snapshot.headline.coreBreakthrough.value) || '当前暂无可执行突破口。'}
              </p>
            </div>
            <div>
              <h3 className="text-[13px] font-bold text-slate-800 mb-2 flex items-center gap-1.5">
                <AlertOctagon size={14} className="text-blue-500" /> 资料缺口
              </h3>
              {snapshot.readiness.gaps.length ? (
                <ul className="pl-8 list-disc leading-[1.9]">
                  {snapshot.readiness.gaps.slice(0, 5).map((gap, idx) => (
                    <li key={`${gap}-${idx}`}>{_normalizeTextForUI(gap)}</li>
                  ))}
                </ul>
              ) : (
                <p className="pl-5 leading-[1.9] text-slate-500">当前未识别到明显资料缺口。</p>
              )}
            </div>
          </div>
        </section>

        <DimensionGrid snapshot={snapshot} />

        <section className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-[20px] border border-slate-200 bg-white p-5">
            <h3 className="text-[14px] font-bold text-slate-800 mb-3">战略线索</h3>
            {snapshot.strategicLines.length ? (
              <div className="space-y-2">
                {snapshot.strategicLines.slice(0, 4).map((line) => (
                  <div key={line.id} className="rounded-xl bg-slate-50 px-3 py-2">
                    <p className="text-[12px] font-semibold text-slate-700">{_normalizeTextForUI(line.title)}</p>
                    <p className="text-[12px] text-slate-500 mt-1">{_normalizeTextForUI(line.nextStep)}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[12px] text-slate-500">暂无战略线索，建议先补会议或事件线材料。</p>
            )}
          </div>
          <div className="rounded-[20px] border border-slate-200 bg-white p-5">
            <h3 className="text-[14px] font-bold text-slate-800 mb-3">待处理事项</h3>
            <div className="space-y-3">
              <div>
                <p className="text-[12px] font-semibold text-slate-600 mb-1">待拍板</p>
                {snapshot.pendingDecisions.length ? (
                  <ul className="pl-5 list-disc text-[12px] text-slate-500 leading-[1.8]">
                    {snapshot.pendingDecisions.slice(0, 3).map((item, idx) => (
                      <li key={`${item.title}-${idx}`}>{_normalizeTextForUI(item.title)}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[12px] text-slate-400">暂无待拍板事项。</p>
                )}
              </div>
              <div>
                <p className="text-[12px] font-semibold text-slate-600 mb-1">待补材料</p>
                {snapshot.pendingMaterials.length ? (
                  <ul className="pl-5 list-disc text-[12px] text-slate-500 leading-[1.8]">
                    {snapshot.pendingMaterials.slice(0, 3).map((item, idx) => (
                      <li key={`${item.title}-${idx}`}>{_normalizeTextForUI(item.title)}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[12px] text-slate-400">暂无待补材料。</p>
                )}
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}


// ================= TAB CONTENT =================

function PulseTab({ pulse }: { pulse: BrainPulse | null }) {
  const p = pulse;
  const metrics1 = [
    { icon: BrainCircuit, label: '组织记忆', value: p ? p.memoryCount.toLocaleString() : '...' },
    { icon: FileText, label: '资料归档', value: p ? p.docCount.toLocaleString() : '...' },
    { icon: CheckCircle, label: '任务追踪', value: p ? p.taskCount.toLocaleString() : '...' },
    { icon: MessageCircle, label: 'AI 对话', value: p ? p.chatCount.toLocaleString() : '...' },
  ];
  const metrics2 = [
    { icon: GitBranch, label: '事件线', value: p ? p.eventLineCount.toLocaleString() : '...' },
    { icon: BookOpen, label: '知识画像', value: p ? p.dnaCount.toLocaleString() : '...' },
    { icon: Award, label: '成长徽章', value: p ? p.badgeCount.toLocaleString() : '...' },
    { icon: Layers, label: '经验沉淀', value: p ? p.handbookCount.toLocaleString() : '...' },
  ];

  return (
    <div className="space-y-6">
      <div className="rounded-[32px] border border-blue-100 p-8 bg-white" style={{ backgroundImage: 'radial-gradient(circle at 10% 10%, rgba(59, 130, 246, 0.08), transparent 50%), linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)', boxShadow: '0 20px 40px -15px rgba(15,23,42,0.05)' }}>
        <div className="flex items-start justify-between mb-8">
          <div className="flex items-center gap-5">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-100/50 flex items-center justify-center shadow-inner">
              <BrainCircuit size={32} className="text-blue-600" strokeWidth={1.5} />
            </div>
            <div>
              <div className="text-[22px] font-bold text-slate-800 tracking-tight flex items-baseline gap-2">
                已陪伴 <span className="tabular-nums text-2xl text-blue-600">{p ? p.daysAccompanied : '...'}</span> 天
              </div>
              <div className="text-[12px] font-medium text-slate-400 mt-1 flex items-center gap-1.5">
                <Clock size={12} /> {p ? `${p.reviewCount} 次复盘 · ${p.meetingCount} 场会议` : '加载中...'}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1.5 bg-emerald-50 text-emerald-600 px-4 py-2 rounded-full border border-emerald-100/50 shadow-sm">
            <Sparkles size={14} />
            <span className="text-[12px] font-semibold">本周 +{p ? p.weeklyNewFacts : '...'} 条新记忆</span>
          </div>
        </div>
        <div className="space-y-4">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {metrics1.map((m, i) => (
              <div key={i} className="bg-white/80 border border-slate-100 rounded-[20px] p-5 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-center gap-2">
                  <m.icon size={16} className="text-blue-500" />
                  <span className="text-[11px] font-semibold text-slate-400 tracking-wide uppercase">{m.label}</span>
                </div>
                <div className="text-[24px] font-bold text-slate-800 tracking-tight mt-2 tabular-nums">{m.value}</div>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {metrics2.map((m, i) => (
              <div key={i} className="bg-white/80 border border-slate-100 rounded-[20px] p-5 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-center gap-2">
                  <m.icon size={16} className="text-indigo-400" />
                  <span className="text-[11px] font-semibold text-slate-400 tracking-wide uppercase">{m.label}</span>
                </div>
                <div className="text-[24px] font-bold text-slate-800 tracking-tight mt-2 tabular-nums">{m.value}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

const getThoughtStatusMeta = (thought: StrategicThought): { text: string; className: string } => {
  if (thought.status === 'confirmed') return { text: '已确认', className: 'bg-emerald-50 text-emerald-600 border border-emerald-100' };
  if (thought.status === 'task_created') return { text: '已转任务', className: 'bg-blue-50 text-blue-600 border border-blue-100' };
  if (thought.status === 'waiting_evidence') return { text: '等待补证', className: 'bg-amber-50 text-amber-600 border border-amber-100' };
  if (thought.isSystem || thought.scope === 'system') return { text: '系统观察', className: 'bg-slate-100 text-slate-500 border border-slate-200' };
  return { text: '系统候选', className: 'bg-indigo-50 text-indigo-600 border border-indigo-100' };
};

function ThoughtCard({
  thought,
  onCreateTask,
  onReview,
}: {
  thought: StrategicThought;
  onCreateTask?: (payload: ThoughtTaskPayload) => void;
  onReview: (thoughtId: string, action: 'confirm' | 'dismiss', note: string) => Promise<void>;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [reviewText, setReviewText] = useState(thought.review?.note || '');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const statusMeta = getThoughtStatusMeta(thought);
  const sourceChips = thought.sources
    .flatMap((item) => [item.label, item.detail ? _normalizeTextForUI(item.detail) : ''])
    .filter((item) => item && !_isInternalKeyText(item))
    .slice(0, 2);
  const normalizedLine = _normalizeTextForUI(thought.line) || '系统发现一条待确认判断';
  const normalizedObservation = _normalizeTextForUI(thought.observation) || '系统发现一条待确认判断。';
  const normalizedSuggestion = _normalizeTextForUI(thought.suggestion) || '建议先补线索，再确认判断。';
  const showConfidence = thought.status !== 'waiting_evidence' && thought.confidence !== null && thought.confidence !== undefined && thought.confidenceLevel !== 'none';

  const handleConfirm = async () => {
    setIsSubmitting(true);
    try {
      await onReview(thought.id, 'confirm', reviewText.trim());
      setIsEditing(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDismiss = async () => {
    setIsSubmitting(true);
    try {
      await onReview(thought.id, 'dismiss', reviewText.trim());
      setIsEditing(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCreateTask = () => {
    const today = new Date();
    const endOfWeek = new Date(today);
    endOfWeek.setDate(today.getDate() + (7 - today.getDay()));
    const dueDate = thought.dueDateHint === '本周' ? endOfWeek.toISOString().slice(0, 10) : '';
    onCreateTask?.({
      suggestion: normalizedSuggestion,
      ceoComment: reviewText.trim(),
      thoughtLine: normalizedLine,
      clientId: thought.clientId || '',
      dueDate,
      thoughtId: thought.id,
      sources: thought.sources,
      evidenceCount: thought.evidenceCount,
      confidence: thought.confidence ?? null,
      clientName: thought.clientName,
    });
  };

  return (
    <div className="break-inside-avoid bg-white rounded-[24px] border border-slate-100 p-6 shadow-[0_2px_10px_rgba(0,0,0,0.02)] relative hover:shadow-[0_8px_30px_rgba(0,0,0,0.04)] transition-all duration-300">
      <div className="flex items-start justify-between mb-5 gap-4">
        <div className="flex items-start gap-2">
          {!thought.isSystem && showConfidence && (
            <div className="w-2 h-2 rounded-full mt-1.5" style={{ backgroundColor: getConfColor(thought.confidence ?? undefined) }} />
          )}
          <div>
            <span className={`text-[13px] font-bold ${thought.isSystem ? 'text-slate-600' : 'text-slate-800'}`}>{normalizedLine}</span>
            {thought.clientName && thought.clientName !== '系统观察' && (
              <p className="text-[11px] text-slate-400 mt-1">{thought.clientName}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {showConfidence && (
            <div className={`px-2.5 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider ${getConfBg(thought.confidence ?? undefined)}`}>
              {`Conf ${thought.confidence}%`}
            </div>
          )}
          <div className={`px-2.5 py-1 rounded-lg text-[10px] font-bold tracking-wide ${statusMeta.className}`}>
            {statusMeta.text}
          </div>
        </div>
      </div>
      <div className="mb-4">
        <span className="inline-block text-[10px] font-bold text-slate-400 tracking-[0.5px] uppercase mb-2">系统看到</span>
        <p className="text-[13px] leading-[1.9] text-slate-600 font-medium">{normalizedObservation}</p>
      </div>
      <div>
        <span className="inline-block text-[10px] font-bold text-blue-600 tracking-[0.5px] uppercase mb-2">建议下一步</span>
        <p className="text-[13px] leading-[1.9] text-slate-700 font-medium">{normalizedSuggestion}</p>
      </div>

      <div className="mt-6 pt-4 border-t border-slate-50 space-y-3">
        {(thought.review?.note || reviewText) && (
          <div className="bg-slate-50 rounded-[14px] px-4 py-3">
            <div className="text-[11px] font-semibold text-slate-500 mb-1">
              {thought.review?.status === 'confirmed' ? '我的已确认判断' : '我的备注'}
            </div>
            <div className="text-[12px] leading-[1.7] text-slate-700">{thought.review?.note || reviewText}</div>
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          {sourceChips.map((chip, idx) => (
            <span key={`${chip}-${idx}`} className="px-2.5 py-1 rounded-md text-[10px] font-bold bg-slate-50 text-slate-500 border border-slate-100">
              {chip}
            </span>
          ))}
          {thought.tags.slice(0, 3).map((tag, idx) => (
            <span key={`${tag}-${idx}`} className="px-2.5 py-1 rounded-md text-[10px] font-bold bg-slate-50 text-slate-400 border border-slate-100">
              {tag}
            </span>
          ))}
          <span className="px-2.5 py-1 rounded-md text-[10px] font-bold bg-blue-50 text-blue-500 border border-blue-100">
            {`${thought.evidenceCount} 条线索`}
          </span>
        </div>

        <p className="text-[11px] text-slate-400">{_buildThoughtLineHint(thought)}</p>

        {isEditing ? (
          <div className="bg-slate-50 rounded-[18px] p-4">
            <textarea
              className="w-full min-h-[72px] border border-slate-200 rounded-[14px] p-3 text-[13px] text-slate-700 bg-white resize-y outline-none focus:border-blue-300 focus:ring-1 focus:ring-blue-100"
              placeholder="写下你的判断..."
              value={reviewText}
              onChange={(e) => setReviewText(e.target.value)}
              autoFocus
            />
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                onClick={handleDismiss}
                disabled={isSubmitting}
                className="text-[11px] font-bold px-3 py-1.5 rounded-full border border-rose-200 bg-rose-50 text-rose-600 hover:bg-rose-100 transition-colors disabled:opacity-60"
              >
                忽略
              </button>
              <button
                type="button"
                onClick={handleCreateTask}
                className="text-[11px] font-bold px-3 py-1.5 rounded-full border border-blue-200 bg-blue-50 text-blue-600 hover:bg-blue-100 transition-colors"
              >
                转为任务
              </button>
              <button
                type="button"
                onClick={handleConfirm}
                disabled={isSubmitting}
                className="ml-auto bg-blue-600 text-white rounded-full px-5 py-1.5 text-[12px] font-bold hover:bg-blue-700 transition-colors disabled:opacity-60"
              >
                确认
              </button>
            </div>
          </div>
        ) : (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setIsEditing(true)}
              className="flex-1 flex items-center gap-2 bg-transparent border border-slate-200 text-slate-500 rounded-[16px] px-4 py-2.5 text-[12px] font-semibold text-left hover:border-blue-300 hover:text-slate-700 transition-colors"
            >
              <PenLine size={14} className="text-slate-400" />
              写下我的判断...
            </button>
            <button
              type="button"
              onClick={handleCreateTask}
              className="flex items-center gap-1.5 border border-blue-200 bg-blue-50 text-blue-600 rounded-[16px] px-4 py-2.5 text-[12px] font-bold hover:bg-blue-100 transition-colors shrink-0"
            >
              <ClipboardList size={14} />
              转为任务
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function ThoughtsTab({
  thoughts,
  loading,
  error,
  selectedClientId,
  onReview,
  onCreateTask,
  onRetry,
}: {
  thoughts: StrategicThought[];
  loading: boolean;
  error: string | null;
  selectedClientId: string | null;
  onReview: (thoughtId: string, action: 'confirm' | 'dismiss', note: string) => Promise<void>;
  onCreateTask?: (payload: ThoughtTaskPayload) => void;
  onRetry: () => void;
}) {
  if (loading) {
    return (
      <div className="bg-white border border-slate-100 rounded-[20px] px-5 py-6 text-[13px] text-slate-500">
        正在加载思考与研判...
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white border border-red-100 rounded-[20px] px-5 py-6">
        <p className="text-[13px] font-semibold text-red-500">研判加载失败</p>
        <p className="text-[12px] text-slate-500 mt-1">{error}</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 text-[12px] font-bold px-3 py-1.5 rounded-full border border-red-200 bg-red-50 text-red-600 hover:bg-red-100"
        >
          重试
        </button>
      </div>
    );
  }

  if (!thoughts.length) {
    return (
      <div className="bg-white border border-slate-100 rounded-[20px] px-5 py-6 text-[13px] leading-7 text-slate-500">
        {selectedClientId
          ? '这个客户目前还没有足够信号生成研判。建议先补充客户资料、会议记录或事件线。'
          : '当前还没有足够信号生成研判。可以先补充会议、复盘、事件线或客户资料。'}
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 rounded-2xl border border-blue-100 bg-blue-50 px-4 py-3 text-[12px] text-blue-700">
        这里展示系统候选研判，需人工确认后才进入正式判断。
      </div>
      <div className="columns-1 md:columns-2 gap-5 space-y-5">
        {thoughts.map((thought) => (
          <ThoughtCard key={thought.id} thought={thought} onCreateTask={onCreateTask} onReview={onReview} />
        ))}
      </div>
    </div>
  );
}

function ClientsTab({ onOpenDetail, clients }: { onOpenDetail: (clientId: string) => void; clients: BrainClientData[] }) {
  const sorted = [...clients].sort((a, b) => b.confidence - a.confidence);
  return (
    <div>
      <div className="flex items-center justify-between mb-6 px-2">
        <h2 className="text-[15px] font-bold text-slate-800 flex items-center gap-2">
          <FolderTree size={18} className="text-indigo-500" /> 项目认知图谱
        </h2>
        <span className="text-[12px] font-medium text-slate-400">目前收录 {clients.length} 个项目空间</span>
      </div>
      <div className="columns-1 md:columns-2 gap-5 space-y-5">
        {sorted.map((client, i) => (
          <div
            key={i}
            onClick={() => onOpenDetail(client.id)}
            className="break-inside-avoid bg-white rounded-[24px] border border-slate-100 p-6 shadow-[0_2px_10px_rgba(0,0,0,0.02)] hover:shadow-[0_8px_30px_rgba(0,0,0,0.05)] hover:border-blue-200 transition-all duration-300 cursor-pointer group"
          >
            <div className="flex flex-col mb-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-[16px] font-bold text-slate-800 group-hover:text-blue-600 transition-colors">{client.name}</h3>
                <span className="bg-slate-50 border border-slate-100 text-slate-500 text-[11px] font-bold px-2.5 py-1 rounded-lg">
                  {client.stage}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <div className="h-1.5 bg-slate-100 rounded-full w-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-1000 ease-out"
                    style={{ width: `${client.confidence}%`, backgroundColor: getConfColor(client.confidence) }}
                  />
                </div>
                <span className="text-[12px] font-bold tabular-nums w-8 text-right" style={{ color: getConfColor(client.confidence) }}>
                  {client.confidence}%
                </span>
              </div>
            </div>
            {client.intro ? (
              <p className="text-[13px] leading-[1.8] text-slate-600 font-medium mb-5 line-clamp-3">
                {client.intro}
              </p>
            ) : (
              <p className="text-[13px] leading-[1.8] text-slate-400 italic mb-5">
                系统对这个项目的了解还很初步
              </p>
            )}
            <div className="flex flex-wrap gap-x-4 gap-y-2 mb-4 pt-4 border-t border-slate-50">
              {[
                { icon: Folder, label: `${client.docs} 文档` },
                { icon: FileText, label: `${client.dna} 篇 DNA` },
                { icon: Activity, label: `${client.eventLines} 事件线` },
                { icon: BrainCircuit, label: `${client.memoryFacts} 条记忆` },
              ].map((metric, idx) => (
                <span key={idx} className="text-[11px] font-bold text-slate-400 flex items-center gap-1.5">
                  <metric.icon size={12} className="text-slate-300" />
                  {metric.label}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ================= MAIN EXPORT =================

export type StrategicBrainViewProps = {
  clients?: Array<{ id: string; name: string }>;
  tasks?: Task[];
  currentClientId?: string | null;
  onClientChange?: (clientId: string) => void;
  onCreateTaskFromThought?: (payload: ThoughtTaskPayload) => void;
  onCreateTaskFromLearning?: (payload: StrategicLearningTaskPayload) => Promise<void> | void;
  onTasksReload?: () => Promise<unknown> | void;
  onNavigate?: (tab: string) => void;
  onOpenContext?: (context: GrowthContextLink) => void;
  flash?: (level: 'success' | 'error' | 'info', message: string) => void;
};

export function StrategicBrainView({
  tasks,
  currentClientId,
  onClientChange,
  onCreateTaskFromThought,
  onCreateTaskFromLearning,
  onTasksReload,
  onNavigate,
  onOpenContext,
  flash,
}: StrategicBrainViewProps) {
  const [selectedClientId, setSelectedClientId] = useState<string | null>(currentClientId ?? null);
  const [activeTab, setActiveTab] = useState('pulse');
  const [viewState, setViewState] = useState<{ type: 'tabs'; detailId: null } | { type: 'detail'; detailId: string }>({ type: 'tabs', detailId: null });
  const [isOpen, setIsOpen] = useState(false);
  const [dashboard, setDashboard] = useState<BrainDashboard | null>(null);
  const [thoughts, setThoughts] = useState<StrategicThought[]>([]);
  const [thoughtsLoading, setThoughtsLoading] = useState(false);
  const [thoughtsError, setThoughtsError] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  useClickOutside(dropdownRef, () => setIsOpen(false));

  useEffect(() => {
    getBrainDashboard()
      .then(setDashboard)
      .catch(() => setDashboard(null));
  }, []);

  useEffect(() => {
    setSelectedClientId(currentClientId ?? null);
  }, [currentClientId]);

  const loadThoughts = useCallback(async () => {
    setThoughtsLoading(true);
    setThoughtsError(null);
    try {
      const response = await getStrategicThoughts({ clientId: selectedClientId, limit: 24 });
      setThoughts(response.items || []);
    } catch (error) {
      setThoughtsError(error instanceof Error ? error.message : '未知错误');
      setThoughts([]);
    } finally {
      setThoughtsLoading(false);
    }
  }, [selectedClientId]);

  useEffect(() => {
    void loadThoughts();
  }, [loadThoughts]);

  const handleThoughtReview = useCallback(
    async (thoughtId: string, action: 'confirm' | 'dismiss', note: string) => {
      await reviewStrategicThought(thoughtId, { action, note, createJudgment: action === 'confirm' });
      await loadThoughts();
    },
    [loadThoughts],
  );

  const clientOptions = [{ id: null as string | null, name: '全部客户' }, ...(dashboard?.clients ?? [])];
  const selectedClientLabel = clientOptions.find((item) => item.id === selectedClientId)?.name || '全部客户';

  if (viewState.type === 'detail') {
    return (
      <div className="h-full flex flex-col bg-white/50 overflow-y-auto">
        <ProjectDetailView clientId={viewState.detailId} onBack={() => setViewState({ type: 'tabs', detailId: null })} />
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-[#F9FAFB] overflow-hidden font-sans">
      {/* Header */}
      <div className="bg-[#F9FAFB]/80 backdrop-blur-xl border-b border-slate-200/60 pt-5 pb-4 px-6 flex flex-col gap-4 shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-[18px] font-semibold tracking-tight text-slate-900 flex items-center gap-2">
              战略陪伴
            </h1>
            <p className="text-[11px] font-medium text-slate-400 mt-0.5">AI 陪伴组织成长 · 越用越懂你</p>
          </div>
          <div className="relative" ref={dropdownRef}>
            <button
              type="button"
              onClick={() => setIsOpen(!isOpen)}
              className="flex items-center gap-2 bg-white border border-slate-200 shadow-sm rounded-full px-4 py-2 hover:bg-slate-50 transition-all duration-200"
            >
              <div className="w-5 h-5 rounded-full bg-blue-100 flex items-center justify-center">
                <User size={12} className="text-blue-600" />
              </div>
              <span className="text-[13px] font-semibold text-slate-700">{selectedClientLabel}</span>
              <ChevronDown size={14} className="text-slate-400" />
            </button>
            {isOpen && (
              <div className="absolute right-0 mt-2 w-56 bg-white border border-slate-100 rounded-2xl shadow-xl py-1.5 z-50 overflow-hidden">
                {clientOptions.map((client) => (
                  <button
                    key={client.id || 'all'}
                    type="button"
                    className={`w-full text-left px-4 py-2.5 text-[13px] font-medium transition-colors hover:bg-slate-50 ${selectedClientId === client.id ? 'text-blue-600 bg-blue-50/50' : 'text-slate-600'}`}
                    onClick={() => {
                      setSelectedClientId(client.id);
                      if (client.id) onClientChange?.(client.id);
                      setIsOpen(false);
                    }}
                  >
                    {client.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
        <div className="flex bg-slate-100/80 p-1 rounded-2xl w-fit">
          {TABS.map(tab => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-1.5 rounded-2xl text-[13px] font-medium transition-all duration-200 ${
                activeTab === tab.id
                  ? 'bg-white text-[#5B7BFE] shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-5">
        <div className="max-w-full mx-auto">
          {activeTab === 'pulse' && <PulseTab pulse={dashboard?.pulse ?? null} />}
          {activeTab === 'thoughts' && (
            <ThoughtsTab
              thoughts={thoughts}
              loading={thoughtsLoading}
              error={thoughtsError}
              selectedClientId={selectedClientId}
              onReview={handleThoughtReview}
              onCreateTask={onCreateTaskFromThought}
              onRetry={() => void loadThoughts()}
            />
          )}
          {activeTab === 'clients' && <ClientsTab clients={dashboard?.clients ?? []} onOpenDetail={(clientId) => setViewState({ type: 'detail', detailId: clientId })} />}
          {activeTab === 'learning' && (
            <StrategicLearningListPanel
              currentClientId={selectedClientId}
              currentClientName={selectedClientLabel === '全部客户' ? null : selectedClientLabel}
              clients={dashboard?.clients || []}
              tasks={tasks}
              onTasksReload={onTasksReload}
              onNavigate={onNavigate}
              onOpenContext={onOpenContext}
              onCreateTaskFromLearning={onCreateTaskFromLearning}
              flash={flash}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default StrategicBrainView;
~~~

## `src/renderer/components/strategic_accompaniment/StrategicLearningListPanel.tsx`

- 编码: `utf-8`

~~~tsx
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
~~~

## `src/renderer/components/tasks/AgentExecutionPanel.tsx`

- 编码: `utf-8`

~~~tsx
import React, { useEffect, useMemo, useState } from 'react';

import type { Task } from '../../../shared/types';
import { getAgentExecutionTasks } from '../../lib/api';

type AgentExecutionPanelProps = {
  weekLabel: string;
  title: string;
  subtitle: string;
  departmentName?: string | null;
};

type DisplayStatus = 'todo' | 'doing' | 'done' | 'blocked';

const displayStatusClassMap: Record<DisplayStatus, string> = {
  todo: 'bg-slate-100 text-slate-700',
  doing: 'bg-blue-50 text-blue-700',
  done: 'bg-emerald-50 text-emerald-700',
  blocked: 'bg-rose-50 text-rose-700',
};

const displayStatusLabelMap: Record<DisplayStatus, string> = {
  todo: '待推进',
  doing: '进行中',
  done: '已完成',
  blocked: '阻塞中',
};

function resolveDepartmentName(task: Task) {
  const departmentTag = task.tags.find((tag) => tag.name.trim().endsWith('部'));
  if (departmentTag) return departmentTag.name;
  if (task.sourceId?.includes('strategy_design') || task.ownerName === '庆华') return '咨询策略部';
  if (task.sourceId?.includes('tech_development') || task.ownerName === '佳乐') return '科技发展部';
  if (task.sourceId?.includes('info_data') || task.ownerName === '大周') return '信息数据部';
  return '机器人部门';
}

function resolveDisplayStatus(task: Task): DisplayStatus {
  const matched = task.note?.match(/状态：([^\n]+)/);
  const planStatus = matched?.[1]?.trim().toLowerCase() || '';
  if (planStatus === 'blocked') return 'blocked';
  if (planStatus === 'done') return 'done';
  if (planStatus === 'doing') return 'doing';
  if (planStatus === 'planned') return 'todo';
  if (task.status === 'done') return 'done';
  if (task.status === 'doing') return 'doing';
  return 'todo';
}

function formatDateLabel(value?: string | null) {
  if (!value) return '未设置';
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return value.slice(5);
  }
  const iso = value.slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(iso) ? iso.slice(5) : value;
}

function buildNoteHighlights(task: Task) {
  return (task.note || '')
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith('状态：') && !line.startsWith('部门：'))
    .slice(0, 3);
}

export function AgentExecutionPanel({ weekLabel, title, subtitle, departmentName }: AgentExecutionPanelProps) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let disposed = false;
    setLoading(true);
    setError(null);
    void getAgentExecutionTasks(weekLabel, departmentName || undefined)
      .then((response) => {
        if (disposed) return;
        setTasks(response);
      })
      .catch((err) => {
        if (disposed) return;
        setError(err instanceof Error ? err.message : '机器人执行层加载失败');
        setTasks([]);
      })
      .finally(() => {
        if (!disposed) {
          setLoading(false);
        }
      });
    return () => {
      disposed = true;
    };
  }, [departmentName, reloadToken, weekLabel]);

  const groupedTasks = useMemo(() => {
    const grouped = new Map<string, Task[]>();
    tasks.forEach((task) => {
      const key = resolveDepartmentName(task);
      const bucket = grouped.get(key);
      if (bucket) {
        bucket.push(task);
      } else {
        grouped.set(key, [task]);
      }
    });
    return Array.from(grouped.entries()).map(([name, items]) => ({
      name,
      items: items.slice().sort((left, right) => right.updatedAt.localeCompare(left.updatedAt)),
    }));
  }, [tasks]);

  const statusCounts = useMemo(() => {
    const counts: Record<DisplayStatus, number> = { todo: 0, doing: 0, done: 0, blocked: 0 };
    tasks.forEach((task) => {
      counts[resolveDisplayStatus(task)] += 1;
    });
    return counts;
  }, [tasks]);

  return (
    <div className="rounded-3xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h3 className="text-[16px] font-bold text-gray-900">{title}</h3>
          <p className="mt-1 text-[12px] leading-6 text-gray-500">{subtitle}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="rounded-full bg-slate-100 px-3 py-1.5 text-[11px] font-bold text-slate-700">{tasks.length} 条正式任务</span>
          {(['done', 'doing', 'blocked', 'todo'] as DisplayStatus[]).map((status) => (
            <span key={status} className={`rounded-full px-3 py-1.5 text-[11px] font-bold ${displayStatusClassMap[status]}`}>
              {displayStatusLabelMap[status]} {statusCounts[status]}
            </span>
          ))}
        </div>
      </div>

      {loading && <div className="mt-4 rounded-2xl bg-slate-50 px-4 py-3 text-[13px] text-slate-500">正在同步机器人本周正式任务...</div>}

      {!loading && error && (
        <div className="mt-4 rounded-2xl border border-rose-100 bg-rose-50 px-4 py-3 text-[13px] text-rose-700">
          <div>{error}</div>
          <button
            type="button"
            className="mt-3 rounded-xl border border-rose-200 bg-white px-3 py-1.5 text-[12px] font-bold text-rose-700"
            onClick={() => setReloadToken((value) => value + 1)}
          >
            重试加载
          </button>
        </div>
      )}

      {!loading && !error && tasks.length === 0 && (
        <div className="mt-4 rounded-2xl bg-slate-50 px-4 py-3 text-[13px] leading-6 text-slate-600">
          当前周没有可展示的机器人正式任务。这通常表示该部门本周还没有形成可同步的执行项，或者该部门目前没有机器人执行单元。
        </div>
      )}

      {!loading && !error && tasks.length > 0 && (
        <div className="mt-4 space-y-4">
          {groupedTasks.map((group) => (
            <div key={group.name} className="space-y-3">
              {!departmentName && (
                <div className="flex items-center justify-between">
                  <h4 className="text-[13px] font-bold text-gray-900">{group.name}</h4>
                  <span className="rounded-full bg-gray-100 px-3 py-1 text-[11px] font-bold text-gray-600">{group.items.length} 条</span>
                </div>
              )}
              <div className="space-y-3">
                {group.items.map((task) => {
                  const displayStatus = resolveDisplayStatus(task);
                  const highlights = buildNoteHighlights(task);
                  return (
                    <div key={task.id} className="rounded-2xl border border-gray-100 bg-slate-50/60 p-4">
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-[14px] font-bold text-gray-900">{task.title}</p>
                            <span className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${displayStatusClassMap[displayStatus]}`}>
                              {displayStatusLabelMap[displayStatus]}
                            </span>
                          </div>
                          <p className="mt-1 text-[12px] text-gray-500">
                            {group.name} · {task.ownerName} · 截止 {formatDateLabel(task.ddl)} · 更新于 {formatDateLabel(task.updatedAt)}
                          </p>
                          <p className="mt-3 text-[13px] leading-6 text-gray-700">{task.desc}</p>
                        </div>
                      </div>

                      {highlights.length > 0 && (
                        <div className="mt-3 grid gap-2">
                          {highlights.map((line) => (
                            <div key={line} className="rounded-2xl bg-white px-3 py-2 text-[12px] leading-5 text-gray-600">
                              {line}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
~~~

## `src/renderer/components/tasks/AgentSimulationCalendarView.tsx`

- 编码: `utf-8`

~~~tsx
import React, { useMemo } from 'react';
import { CalendarClock, ChevronLeft, ChevronRight, Sparkles } from 'lucide-react';

import type { AgentWeeklyDigest, AgentWeeklyPlan, AgentWeeklyPlanPayload, AgentWorklog } from '../../../shared/types';
import { buildCalendarCells, formatMonthTitle } from '../../../shared/calendar';
import { AgentWeeklyPlanEditor } from './AgentWeeklyPlanEditor';

type AgentSimulationCalendarViewProps = {
  agentWorklogs: AgentWorklog[];
  weeklyDigests: AgentWeeklyDigest[];
  weeklyPlans: AgentWeeklyPlan[];
  onSavePlan: (payload: AgentWeeklyPlanPayload) => Promise<void>;
  calendarDate: Date;
  selectedDay: number;
  onSelectDay: (day: number) => void;
  onSelectDate: (date: Date) => void;
  onShiftMonth: (delta: number) => void;
  onGoToToday: () => void;
};

const AGENT_ORDER: Record<AgentWorklog['agentKey'], number> = {
  strategy_design: 0,
  info_data: 1,
  tech_development: 2,
};

function sourceLabel(sourceType: AgentWorklog['sourceType']) {
  if (sourceType === 'activity_log') return '战略动作';
  if (sourceType === 'topic_capture') return '情报处理';
  return '系统同步';
}

function formatDateLabel(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

export function AgentSimulationCalendarView({
  agentWorklogs,
  weeklyDigests,
  weeklyPlans,
  onSavePlan,
  calendarDate,
  selectedDay,
  onSelectDay,
  onSelectDate,
  onShiftMonth,
  onGoToToday,
}: AgentSimulationCalendarViewProps) {
  const calendarCells = useMemo(() => buildCalendarCells(calendarDate), [calendarDate]);
  const selectedDate = useMemo(
    () => new Date(calendarDate.getFullYear(), calendarDate.getMonth(), selectedDay),
    [calendarDate, selectedDay],
  );

  const logsByDay = useMemo(() => {
    const mapping = new Map<number, AgentWorklog[]>();
    agentWorklogs.forEach((log) => {
      const date = new Date(log.date);
      if (Number.isNaN(date.getTime())) return;
      if (date.getFullYear() !== calendarDate.getFullYear() || date.getMonth() !== calendarDate.getMonth()) return;
      const current = mapping.get(date.getDate()) || [];
      current.push(log);
      mapping.set(date.getDate(), current);
    });
    mapping.forEach((items, day) => {
      mapping.set(
        day,
        [...items].sort((left, right) => AGENT_ORDER[left.agentKey] - AGENT_ORDER[right.agentKey]),
      );
    });
    return mapping;
  }, [agentWorklogs, calendarDate]);

  const selectedDayLogs = useMemo(
    () => logsByDay.get(selectedDay) || [],
    [logsByDay, selectedDay],
  );

  const monthStats = useMemo(() => ({
    activeDays: logsByDay.size,
    totalLogs: agentWorklogs.length,
    activeDepartments: new Set(agentWorklogs.map((item) => item.departmentName)).size,
  }), [agentWorklogs, logsByDay.size]);

  return (
    <div className="w-full min-w-0 grid grid-cols-1 xl:grid-cols-[minmax(0,1.35fr)_minmax(360px,0.95fr)] gap-6 items-start">
      <div className="min-w-0 w-full bg-white border border-gray-200 rounded-[32px] shadow-sm overflow-hidden">
        <div className="px-6 lg:px-8 py-6 border-b border-gray-100 space-y-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-3">
                <h2 className="text-[20px] lg:text-[24px] font-bold text-gray-900">{formatMonthTitle(calendarDate)}</h2>
                <span className="text-[11px] font-bold text-[#5B7BFE] bg-blue-50 px-3 py-1 rounded-full">仅 CEO 可见</span>
              </div>
              <div className="flex flex-wrap gap-2 text-[11px] font-semibold">
                <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-600">{monthStats.activeDays} 天有机器人工作痕迹</span>
                <span className="rounded-full bg-emerald-50 px-3 py-1 text-emerald-700">{monthStats.activeDepartments} 个单人部门</span>
                <span className="rounded-full bg-amber-50 px-3 py-1 text-amber-700">{monthStats.totalLogs} 条模拟日程</span>
              </div>
            </div>

            <div className="flex items-center gap-2 self-start lg:self-auto">
              <button
                type="button"
                className="h-11 w-11 rounded-2xl border border-gray-200 text-gray-500 hover:text-[#5B7BFE] hover:border-blue-100 transition-colors"
                onClick={() => onShiftMonth(-1)}
              >
                <ChevronLeft size={18} className="mx-auto" />
              </button>
              <button
                type="button"
                className="h-11 px-4 rounded-2xl border border-gray-200 bg-white text-[13px] font-bold text-gray-700 hover:text-[#5B7BFE] hover:border-blue-100 transition-colors"
                onClick={onGoToToday}
              >
                今天
              </button>
              <button
                type="button"
                className="h-11 w-11 rounded-2xl border border-gray-200 text-gray-500 hover:text-[#5B7BFE] hover:border-blue-100 transition-colors"
                onClick={() => onShiftMonth(1)}
              >
                <ChevronRight size={18} className="mx-auto" />
              </button>
            </div>
          </div>

          <div className="rounded-[28px] border border-blue-100 bg-[linear-gradient(135deg,rgba(239,246,255,0.9),rgba(255,255,255,1))] px-5 py-4">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 h-9 w-9 shrink-0 rounded-2xl bg-white text-[#5B7BFE] shadow-sm flex items-center justify-center">
                <Sparkles size={16} />
              </div>
              <div>
                <p className="text-[14px] font-bold text-gray-900">机器人模拟日程</p>
                <p className="mt-1 text-[12px] leading-6 text-gray-600">
                  这里不把庆华、大周、佳乐当成真实员工，而是把他们每天的真实工作痕迹折算成单人部门的模拟日程，方便 CEO 看组织日常运转。
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="p-6 lg:p-8">
          <div className="grid grid-cols-7 gap-3 text-[12px] font-bold text-gray-400 mb-3">
            {['周一', '周二', '周三', '周四', '周五', '周六', '周日'].map((label) => (
              <div key={label} className="px-2">{label}</div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-3">
            {calendarCells.map((cell, index) => {
              const cellLogs = cell.day ? logsByDay.get(cell.day) || [] : [];
              const isSelected = cell.day === selectedDay;
              return (
                <button
                  key={`${cell.day ?? 'blank'}-${index}`}
                  type="button"
                  disabled={!cell.day}
                  onClick={() => {
                    if (!cell.date || !cell.day) return;
                    onSelectDate(cell.date);
                    onSelectDay(cell.day);
                  }}
                  className={`min-h-[126px] rounded-[24px] border p-3 text-left transition-all ${
                    cell.day
                      ? isSelected
                        ? 'border-[#5B7BFE] bg-blue-50/70 shadow-[0_10px_26px_rgba(91,123,254,0.12)]'
                        : 'border-gray-200 bg-white hover:border-blue-100 hover:bg-blue-50/30'
                      : 'border-transparent bg-gray-50/50'
                  }`}
                >
                  {cell.day ? (
                    <div className="h-full flex flex-col">
                      <div className="flex items-center justify-between">
                        <span className={`text-[14px] font-bold ${isSelected ? 'text-[#5B7BFE]' : 'text-gray-900'}`}>{cell.day}</span>
                        {cellLogs.length > 0 && (
                          <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-bold text-gray-500">
                            {cellLogs.length} 条
                          </span>
                        )}
                      </div>
                      <div className="mt-3 space-y-2">
                        {cellLogs.slice(0, 3).map((log) => (
                          <div key={log.id} className="rounded-2xl px-2.5 py-2 text-[10px] font-bold leading-5" style={{ backgroundColor: `${log.color}14`, color: log.color }}>
                            {log.departmentName}
                          </div>
                        ))}
                        {cellLogs.length === 0 && (
                          <div className="rounded-2xl border border-dashed border-gray-200 px-2.5 py-3 text-[10px] text-gray-300">
                            暂无排程
                          </div>
                        )}
                      </div>
                    </div>
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div className="space-y-5">
        <div className="bg-white border border-gray-200 rounded-[32px] shadow-sm overflow-hidden">
          <div className="px-6 py-5 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <CalendarClock size={17} className="text-[#5B7BFE]" />
              <h3 className="text-[17px] font-bold text-gray-900">{formatDateLabel(selectedDate)} 模拟日程</h3>
            </div>
            <p className="mt-1 text-[12px] leading-6 text-gray-500">按当天真实工作痕迹折算出的部门日程块，不进入正式员工任务考核。</p>
          </div>
          <div className="p-5 space-y-4">
            {selectedDayLogs.length > 0 ? (
              selectedDayLogs.map((log) => (
                <div key={log.id} className="rounded-[28px] border border-gray-200 bg-gray-50/60 p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="h-3 w-3 rounded-full" style={{ backgroundColor: log.color }} />
                    <p className="text-[14px] font-bold text-gray-900">{log.departmentName}</p>
                    <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-gray-500 shadow-sm">{log.agentName}</span>
                    <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-gray-500 shadow-sm">{sourceLabel(log.sourceType)}</span>
                  </div>
                  <p className="mt-3 text-[13px] font-bold text-gray-900">{log.title}</p>
                  <p className="mt-2 text-[12px] leading-6 text-gray-600">{log.summary}</p>
                  {log.detailLines.length > 0 && (
                    <div className="mt-3 space-y-2">
                      {log.detailLines.map((item) => (
                        <div key={item} className="rounded-2xl bg-white px-4 py-3 text-[12px] leading-6 text-gray-700 shadow-sm">
                          {item}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div className="rounded-[28px] border border-dashed border-gray-200 bg-gray-50/60 px-6 py-10 text-center text-[12px] leading-6 text-gray-400">
                这一天还没有采集到机器人部门的工作痕迹，所以不会生成模拟日程块。
              </div>
            )}
          </div>
        </div>

        {weeklyPlans.length > 0 ? (
          <AgentWeeklyPlanEditor plans={weeklyPlans} onSavePlan={onSavePlan} />
        ) : weeklyDigests.length > 0 ? (
          <div className="bg-white border border-gray-200 rounded-[32px] shadow-sm overflow-hidden">
            <div className="px-6 py-5 border-b border-gray-100">
              <h3 className="text-[17px] font-bold text-gray-900">本周部门摘要</h3>
              <p className="mt-1 text-[12px] leading-6 text-gray-500">当前计划层还没生成时，先展示这周三个部门的真实摘要。</p>
            </div>
            <div className="p-5 space-y-4">
              {weeklyDigests.map((digest) => (
                <div key={`${digest.agentKey}:${digest.weekLabel}`} className="rounded-[28px] border border-gray-200 bg-gray-50/60 p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="h-3 w-3 rounded-full" style={{ backgroundColor: digest.color }} />
                    <p className="text-[14px] font-bold text-gray-900">{digest.departmentName}</p>
                    <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-gray-500 shadow-sm">{digest.agentName}</span>
                  </div>
                  <p className="mt-3 text-[12px] leading-6 text-gray-600">{digest.summary}</p>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="bg-white border border-gray-200 rounded-[32px] shadow-sm overflow-hidden">
            <div className="px-6 py-5 border-b border-gray-100">
              <h3 className="text-[17px] font-bold text-gray-900">本周部门计划</h3>
              <p className="mt-1 text-[12px] leading-6 text-gray-500">当前这一周还没有足够的真实痕迹来推演部门周计划。</p>
            </div>
            <div className="p-5">
              <div className="rounded-[28px] border border-dashed border-gray-200 bg-gray-50/60 px-6 py-10 text-center text-[12px] leading-6 text-gray-400">
                先补更多真实工作痕迹，再生成三个单人部门的周计划。
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
~~~

## `src/renderer/components/tasks/AgentWeeklyDigestPanel.tsx`

- 编码: `utf-8`

~~~tsx
import type { AgentWeeklyDigest } from '../../../shared/types';

type AgentWeeklyDigestPanelProps = {
  digests: AgentWeeklyDigest[];
  title?: string;
  subtitle?: string;
};

function sourceLabel(sourceType: unknown) {
  if (sourceType === 'activity_log') return '战略动作';
  if (sourceType === 'topic_capture') return '情报处理';
  if (sourceType === 'workspace_sync') return '系统同步';
  return '真实日志';
}

export function AgentWeeklyDigestPanel({
  digests,
  title = '三个部门本周摘要',
  subtitle = '把庆华、大周、佳乐的当周真实工作痕迹收敛成 CEO 可读的部门周摘要，用来补足“组织本周到底在运转什么”这一层。',
}: AgentWeeklyDigestPanelProps) {
  if (digests.length === 0) return null;

  return (
    <div className="bg-white border border-gray-200 rounded-3xl shadow-sm overflow-hidden">
      <div className="px-6 py-5 border-b border-gray-100 bg-[linear-gradient(135deg,rgba(248,250,252,0.92),rgba(255,255,255,1))]">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-[18px] font-bold text-gray-900">{title}</h2>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-[10px] font-bold tracking-[0.08em] text-slate-600">
            真实日志聚合
          </span>
        </div>
        <p className="mt-1 text-[12px] leading-6 text-gray-600">
          {subtitle}
        </p>
      </div>

      <div className="grid gap-5 p-6 xl:grid-cols-3">
        {digests.map((digest) => (
          <div key={`${digest.agentKey}:${digest.weekLabel}`} className="rounded-[28px] border border-gray-200 bg-gray-50/60 p-5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="h-3 w-3 rounded-full" style={{ backgroundColor: digest.color }} />
              <p className="text-[15px] font-bold text-gray-900">{digest.departmentName}</p>
              <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-gray-500 shadow-sm">{digest.agentName}</span>
            </div>

            <div className="mt-3 flex flex-wrap gap-2">
              <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-gray-500 shadow-sm">{digest.weekLabel}</span>
              <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-gray-500 shadow-sm">{digest.evidenceCount} 条日志</span>
              <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-gray-500 shadow-sm">
                {sourceLabel(digest.sourcePolicy?.sourceType)}
              </span>
            </div>

            <p className="mt-4 text-[13px] leading-6 text-gray-700">{digest.summary}</p>

            {digest.focusItems.length > 0 && (
              <div className="mt-4 space-y-2">
                <p className="text-[12px] font-bold text-gray-900">下周延续重点</p>
                {digest.focusItems.map((item) => (
                  <div key={item} className="rounded-2xl bg-white px-4 py-3 text-[12px] leading-6 text-slate-700 shadow-sm">
                    {item}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
~~~

## `src/renderer/components/tasks/AgentWeeklyPlanEditor.tsx`

- 编码: `utf-8`

~~~tsx
import { useEffect, useMemo, useState } from 'react';

import type { AgentPlanStatus, AgentWeeklyPlan, AgentWeeklyPlanPayload } from '../../../shared/types';

type AgentWeeklyPlanEditorProps = {
  plans: AgentWeeklyPlan[];
  onSavePlan: (payload: AgentWeeklyPlanPayload) => Promise<void>;
};

type DraftPlan = {
  summary: string;
  planItems: Array<{
    title: string;
    rationale: string;
    scheduleHint: string;
    status: AgentPlanStatus;
  }>;
};

const STATUS_OPTIONS: Array<{ value: AgentPlanStatus; label: string }> = [
  { value: 'planned', label: '待推进' },
  { value: 'doing', label: '进行中' },
  { value: 'done', label: '已完成' },
  { value: 'blocked', label: '阻塞中' },
];

function createDraftMap(plans: AgentWeeklyPlan[]) {
  return Object.fromEntries(
    plans.map((plan) => [
      plan.agentKey,
      {
        summary: plan.summary,
        planItems: plan.planItems.map((item) => ({
          title: item.title,
          rationale: item.rationale,
          scheduleHint: item.scheduleHint,
          status: item.status,
        })),
      } satisfies DraftPlan,
    ]),
  ) as Record<string, DraftPlan>;
}

function statusClass(status: AgentPlanStatus) {
  if (status === 'doing') return 'bg-blue-50 text-blue-700';
  if (status === 'done') return 'bg-emerald-50 text-emerald-700';
  if (status === 'blocked') return 'bg-rose-50 text-rose-700';
  return 'bg-amber-50 text-amber-700';
}

export function AgentWeeklyPlanEditor({ plans, onSavePlan }: AgentWeeklyPlanEditorProps) {
  const [drafts, setDrafts] = useState<Record<string, DraftPlan>>(() => createDraftMap(plans));
  const [savingKey, setSavingKey] = useState<string | null>(null);

  useEffect(() => {
    setDrafts(createDraftMap(plans));
  }, [plans]);

  const orderedPlans = useMemo(
    () => [...plans].sort((left, right) => left.departmentName.localeCompare(right.departmentName, 'zh-CN')),
    [plans],
  );

  const updateDraft = (agentKey: string, updater: (draft: DraftPlan) => DraftPlan) => {
    setDrafts((prev) => ({
      ...prev,
      [agentKey]: updater(prev[agentKey] || { summary: '', planItems: [] }),
    }));
  };

  if (plans.length === 0) {
    return (
      <div className="bg-white border border-gray-200 rounded-[32px] shadow-sm overflow-hidden">
        <div className="px-6 py-5 border-b border-gray-100">
          <h3 className="text-[17px] font-bold text-gray-900">本周正式计划</h3>
          <p className="mt-1 text-[12px] leading-6 text-gray-500">当前这一周还没有足够的真实痕迹，暂时无法生成可调整的正式计划。</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-[32px] shadow-sm overflow-hidden">
      <div className="px-6 py-5 border-b border-gray-100 bg-[linear-gradient(135deg,rgba(255,247,237,0.95),rgba(255,255,255,1))]">
        <h3 className="text-[18px] font-bold text-gray-900">三个部门本周正式计划</h3>
        <p className="mt-1 text-[12px] leading-6 text-gray-600">
          这里是 CEO 可调整的正式计划层。默认值来自真实日志推演，但你一旦保存，后续模拟日程和周复盘都会优先读这里。
        </p>
      </div>

      <div className="grid gap-5 p-6 xl:grid-cols-3">
        {orderedPlans.map((plan) => {
          const draft = drafts[plan.agentKey] || { summary: '', planItems: [] };
          return (
            <div key={`${plan.agentKey}:${plan.weekLabel}`} className="rounded-[28px] border border-gray-200 bg-gray-50/60 p-5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="h-3 w-3 rounded-full" style={{ backgroundColor: plan.color }} />
                <p className="text-[15px] font-bold text-gray-900">{plan.departmentName}</p>
                <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-gray-500 shadow-sm">{plan.agentName}</span>
                {plan.sourcePolicy?.manualOverride === true && (
                  <span className="rounded-full bg-slate-900 px-2.5 py-1 text-[10px] font-bold text-white">已人工修订</span>
                )}
              </div>

              <textarea
                value={draft.summary}
                onChange={(event) =>
                  updateDraft(plan.agentKey, (current) => ({ ...current, summary: event.target.value }))
                }
                className="mt-4 min-h-[112px] w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[12px] leading-6 text-gray-700 outline-none focus:border-amber-200"
              />

              <div className="mt-4 space-y-3">
                {draft.planItems.map((item, index) => (
                  <div key={`${plan.agentKey}-${index}`} className="rounded-2xl bg-white px-4 py-4 shadow-sm space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${statusClass(item.status)}`}>
                        {STATUS_OPTIONS.find((option) => option.value === item.status)?.label || '待推进'}
                      </span>
                      <button
                        type="button"
                        className="text-[11px] font-bold text-gray-400 hover:text-rose-500"
                        onClick={() =>
                          updateDraft(plan.agentKey, (current) => ({
                            ...current,
                            planItems: current.planItems.filter((_, itemIndex) => itemIndex !== index),
                          }))
                        }
                      >
                        删除
                      </button>
                    </div>
                    <input
                      value={item.title}
                      onChange={(event) =>
                        updateDraft(plan.agentKey, (current) => ({
                          ...current,
                          planItems: current.planItems.map((currentItem, itemIndex) =>
                            itemIndex === index ? { ...currentItem, title: event.target.value } : currentItem,
                          ),
                        }))
                      }
                      className="w-full rounded-2xl border border-gray-200 bg-gray-50 px-3 py-2 text-[12px] font-bold text-gray-800 outline-none focus:border-amber-200 focus:bg-white"
                    />
                    <textarea
                      value={item.rationale}
                      onChange={(event) =>
                        updateDraft(plan.agentKey, (current) => ({
                          ...current,
                          planItems: current.planItems.map((currentItem, itemIndex) =>
                            itemIndex === index ? { ...currentItem, rationale: event.target.value } : currentItem,
                          ),
                        }))
                      }
                      className="min-h-[88px] w-full rounded-2xl border border-gray-200 bg-gray-50 px-3 py-3 text-[12px] leading-6 text-gray-600 outline-none focus:border-amber-200 focus:bg-white"
                    />
                    <input
                      value={item.scheduleHint}
                      onChange={(event) =>
                        updateDraft(plan.agentKey, (current) => ({
                          ...current,
                          planItems: current.planItems.map((currentItem, itemIndex) =>
                            itemIndex === index ? { ...currentItem, scheduleHint: event.target.value } : currentItem,
                          ),
                        }))
                      }
                      className="w-full rounded-2xl border border-gray-200 bg-gray-50 px-3 py-2 text-[12px] text-gray-700 outline-none focus:border-amber-200 focus:bg-white"
                    />
                    <select
                      value={item.status}
                      onChange={(event) =>
                        updateDraft(plan.agentKey, (current) => ({
                          ...current,
                          planItems: current.planItems.map((currentItem, itemIndex) =>
                            itemIndex === index ? { ...currentItem, status: event.target.value as AgentPlanStatus } : currentItem,
                          ),
                        }))
                      }
                      className="w-full rounded-2xl border border-gray-200 bg-gray-50 px-3 py-2 text-[12px] font-bold text-gray-700 outline-none focus:border-amber-200 focus:bg-white"
                    >
                      {STATUS_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>

              <div className="mt-4 flex items-center justify-between gap-3">
                <button
                  type="button"
                  className="rounded-2xl border border-dashed border-gray-300 px-3 py-2 text-[12px] font-bold text-gray-500 hover:border-amber-200 hover:text-amber-700"
                  onClick={() =>
                    updateDraft(plan.agentKey, (current) => ({
                      ...current,
                      planItems: [
                        ...current.planItems,
                        { title: '', rationale: '', scheduleHint: '', status: 'planned' },
                      ],
                    }))
                  }
                >
                  新增计划项
                </button>
                <button
                  type="button"
                  disabled={savingKey === plan.agentKey}
                  className="rounded-2xl bg-[#5B7BFE] px-4 py-2 text-[12px] font-bold text-white shadow-sm disabled:opacity-60"
                  onClick={async () => {
                    setSavingKey(plan.agentKey);
                    try {
                      await onSavePlan({
                        weekLabel: plan.weekLabel,
                        agentKey: plan.agentKey,
                        summary: draft.summary,
                        planItems: draft.planItems.filter((item) => item.title.trim()),
                      });
                    } finally {
                      setSavingKey(null);
                    }
                  }}
                >
                  {savingKey === plan.agentKey ? '保存中...' : '保存正式计划'}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
~~~

## `src/renderer/components/tasks/AgentWeeklyPlanPanel.tsx`

- 编码: `utf-8`

~~~tsx
import type { AgentWeeklyPlan } from '../../../shared/types';

type AgentWeeklyPlanPanelProps = {
  plans: AgentWeeklyPlan[];
  title?: string;
  subtitle?: string;
};

function sourceLabel(sourceType: unknown) {
  if (sourceType === 'activity_log') return '战略动作';
  if (sourceType === 'topic_capture') return '情报处理';
  if (sourceType === 'workspace_sync') return '系统同步';
  return '真实日志';
}

function statusLabel(status: string) {
  if (status === 'doing') return '进行中';
  if (status === 'done') return '已完成';
  if (status === 'blocked') return '阻塞中';
  return '待推进';
}

function statusClass(status: string) {
  if (status === 'doing') return 'bg-blue-50 text-blue-700';
  if (status === 'done') return 'bg-emerald-50 text-emerald-700';
  if (status === 'blocked') return 'bg-rose-50 text-rose-700';
  return 'bg-amber-50 text-amber-700';
}

export function AgentWeeklyPlanPanel({
  plans,
  title = '三个部门本周计划',
  subtitle = '这些计划不是手工编造，而是基于真实工作痕迹和部门职责自动推演出的 CEO 视角计划板。',
}: AgentWeeklyPlanPanelProps) {
  if (plans.length === 0) return null;

  return (
    <div className="bg-white border border-gray-200 rounded-3xl shadow-sm overflow-hidden">
      <div className="px-6 py-5 border-b border-gray-100 bg-[linear-gradient(135deg,rgba(255,247,237,0.95),rgba(255,255,255,1))]">
        <h2 className="text-[18px] font-bold text-gray-900">{title}</h2>
        <p className="mt-1 text-[12px] leading-6 text-gray-600">{subtitle}</p>
      </div>

      <div className="grid gap-5 p-6 xl:grid-cols-3">
        {plans.map((plan) => (
          <div key={`${plan.agentKey}:${plan.weekLabel}`} className="rounded-[28px] border border-gray-200 bg-gray-50/60 p-5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="h-3 w-3 rounded-full" style={{ backgroundColor: plan.color }} />
              <p className="text-[15px] font-bold text-gray-900">{plan.departmentName}</p>
              <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-gray-500 shadow-sm">{plan.agentName}</span>
            </div>

            <div className="mt-3 flex flex-wrap gap-2">
              <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-gray-500 shadow-sm">{plan.weekLabel}</span>
              <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-gray-500 shadow-sm">
                {sourceLabel(plan.sourcePolicy?.sourceType)}
              </span>
            </div>

            <p className="mt-4 text-[13px] leading-6 text-gray-700">{plan.summary}</p>

            <div className="mt-4 space-y-3">
              {plan.planItems.map((item) => (
                <div key={item.id} className="rounded-2xl bg-white px-4 py-3 shadow-sm">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-[12px] font-bold text-gray-900">{item.title}</p>
                    <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${statusClass(item.status)}`}>
                      {statusLabel(item.status)}
                    </span>
                  </div>
                  {item.rationale && <p className="mt-1 text-[12px] leading-6 text-gray-600">{item.rationale}</p>}
                  {item.scheduleHint && <p className="mt-2 text-[11px] font-bold text-amber-600">{item.scheduleHint}</p>}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
~~~

## `src/renderer/components/tasks/EventLineClarificationComposer.tsx`

- 编码: `utf-8`

~~~tsx
import React from 'react';
import { AlertCircle, MessageSquareText, Sparkles } from 'lucide-react';

type EventLineClarificationDraftValue = {
  summary: string;
  stage: string;
  intent: string;
  currentBlocker: string;
  nextStep: string;
  recentDecision: string;
  missingInfo: string[];
  confidence: 'low' | 'medium' | 'high';
};

type EventLineClarificationComposerProps = {
  transcript: string;
  onTranscriptChange: (value: string) => void;
  draft: EventLineClarificationDraftValue;
  onDraftChange: (patch: Partial<EventLineClarificationDraftValue>) => void;
  onGenerate: () => void;
  onCancel: () => void;
  onSave: () => void;
  isGenerating: boolean;
  isSaving: boolean;
  compact?: boolean;
};

export function EventLineClarificationComposer({
  transcript,
  onTranscriptChange,
  draft,
  onDraftChange,
  onGenerate,
  onCancel,
  onSave,
  isGenerating,
  isSaving,
  compact = false,
}: EventLineClarificationComposerProps) {
  const fieldClassName = compact
    ? 'rounded-2xl border border-gray-200 bg-white px-3 py-2.5 text-[12px] leading-5 text-gray-800 outline-none transition focus:border-[#B7C8FF] focus:ring-2 focus:ring-[#DCE5FF]'
    : 'rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] leading-6 text-gray-800 outline-none transition focus:border-[#B7C8FF] focus:ring-2 focus:ring-[#DCE5FF]';

  const labelClassName = compact ? 'text-[11px] font-bold text-slate-600' : 'text-[12px] font-bold text-gray-600';

  return (
    <div className={`mt-4 rounded-3xl border border-[#D7E0FF] bg-white/95 ${compact ? 'px-3 py-3' : 'px-4 py-4'}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <MessageSquareText size={compact ? 14 : 16} className="text-[#5B7BFE]" />
            <p className={`${compact ? 'text-[11px]' : 'text-[12px]'} font-semibold text-[#33449a]`}>粘贴聊天记录，AI 自动整理这条线</p>
          </div>
          <p className={`mt-1 ${compact ? 'text-[11px]' : 'text-[12px]'} leading-5 text-[#5c6ba1]`}>
            把和客户的聊天记录、会议纪要或沟通摘录贴进来，AI 会先提炼摘要、当前事项、阻塞、下一步和最近关键决策。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className={`rounded-2xl border border-[#D7E0FF] bg-[#F8FAFF] ${compact ? 'px-3 py-2 text-[11px]' : 'px-4 py-2 text-[12px]'} font-bold text-[#33449a] transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-60`}
            onClick={onGenerate}
            disabled={isGenerating || transcript.trim().length < 8}
          >
            <span className="inline-flex items-center gap-1.5">
              <Sparkles size={compact ? 12 : 14} />
              {isGenerating ? 'AI 整理中…' : 'AI 整理聊天记录'}
            </span>
          </button>
        </div>
      </div>

      <label className="mt-4 flex flex-col gap-2">
        <span className={labelClassName}>聊天记录 / 沟通摘录</span>
        <textarea
          value={transcript}
          onChange={(event) => onTranscriptChange(event.target.value)}
          rows={compact ? 6 : 8}
          placeholder="把和客户的聊天记录、语音转写、会议纪要、微信/飞书沟通摘录贴进来。AI 会先整理成这条事件线的当前态草稿。"
          className={`${fieldClassName} min-h-[160px] resize-y`}
        />
      </label>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span
          className={`rounded-full px-3 py-1 text-[11px] font-bold ${
            draft.confidence === 'high'
              ? 'bg-emerald-50 text-emerald-700'
              : draft.confidence === 'medium'
                ? 'bg-amber-50 text-amber-700'
                : 'bg-slate-100 text-slate-600'
          }`}
        >
          AI 置信度：{draft.confidence === 'high' ? '高' : draft.confidence === 'medium' ? '中' : '低'}
        </span>
        {draft.missingInfo.map((item) => (
          <span key={item} className="rounded-full bg-[#FFF6EA] px-3 py-1 text-[11px] font-semibold text-[#E38B17]">
            缺：{item}
          </span>
        ))}
      </div>

      <div className={`mt-4 grid gap-3 ${compact ? 'md:grid-cols-2' : 'md:grid-cols-2'}`}>
        <label className="flex flex-col gap-2 md:col-span-2">
          <span className={labelClassName}>AI 整理摘要</span>
          <textarea
            value={draft.summary}
            onChange={(event) => onDraftChange({ summary: event.target.value })}
            rows={compact ? 3 : 4}
            placeholder="AI 会先总结这条线现在发生了什么。"
            className={fieldClassName}
          />
        </label>
        <label className="flex flex-col gap-2">
          <span className={labelClassName}>当前阶段</span>
          <input
            value={draft.stage}
            onChange={(event) => onDraftChange({ stage: event.target.value })}
            placeholder="例如：等待确认 / 资料补齐中"
            className={fieldClassName}
          />
        </label>
        <label className="flex flex-col gap-2">
          <span className={labelClassName}>当前事项</span>
          <textarea
            value={draft.intent}
            onChange={(event) => onDraftChange({ intent: event.target.value })}
            rows={compact ? 2 : 3}
            placeholder="这条线当前到底在推进什么。"
            className={fieldClassName}
          />
        </label>
        <label className="flex flex-col gap-2 md:col-span-2">
          <span className={labelClassName}>当前阻塞</span>
          <textarea
            value={draft.currentBlocker}
            onChange={(event) => onDraftChange({ currentBlocker: event.target.value })}
            rows={compact ? 2 : 3}
            placeholder="最卡的地方是什么，卡在谁、卡在哪个确认或资料上。"
            className={fieldClassName}
          />
        </label>
        <label className="flex flex-col gap-2">
          <span className={labelClassName}>下一步动作</span>
          <textarea
            value={draft.nextStep}
            onChange={(event) => onDraftChange({ nextStep: event.target.value })}
            rows={compact ? 2 : 3}
            placeholder="接下来最关键的一步是什么。"
            className={fieldClassName}
          />
        </label>
        <label className="flex flex-col gap-2">
          <span className={labelClassName}>最近关键决策</span>
          <textarea
            value={draft.recentDecision}
            onChange={(event) => onDraftChange({ recentDecision: event.target.value })}
            rows={compact ? 2 : 3}
            placeholder="最近哪次决定真正改变了这条线。"
            className={fieldClassName}
          />
        </label>
      </div>

      <div className="mt-4 rounded-2xl border border-[#F6E2B8] bg-[#FFF9ED] px-3 py-3 text-[11px] leading-5 text-[#8A6114]">
        <div className="flex items-start gap-2">
          <AlertCircle size={14} className="mt-0.5 shrink-0" />
          <p>AI 先帮你整理，再由你确认后保存；如果有缺口，优先继续补聊天摘录或手工修正，不要直接让系统猜。</p>
        </div>
      </div>

      <div className="mt-4 flex justify-end gap-2">
        <button
          type="button"
          className={`rounded-2xl border border-gray-200 bg-white ${compact ? 'px-3 py-2 text-[11px]' : 'px-4 py-2 text-[12px]'} font-bold text-gray-500 transition hover:text-gray-700`}
          onClick={onCancel}
        >
          取消
        </button>
        <button
          type="button"
          className={`rounded-2xl bg-[#5B7BFE] ${compact ? 'px-3 py-2 text-[11px]' : 'px-4 py-2 text-[12px]'} font-bold text-white transition hover:bg-[#4a68df] disabled:cursor-not-allowed disabled:bg-[#C9D4FF]`}
          onClick={onSave}
          disabled={isSaving}
        >
          {isSaving ? '保存中…' : '保存澄清'}
        </button>
      </div>
    </div>
  );
}
~~~

## `src/renderer/components/tasks/EventLineReportPanel.tsx`

- 编码: `utf-8`

~~~tsx
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  X,
  Download,
  Upload,
  ChevronDown,
  ChevronRight,
  Paperclip,
  Clock,
  Users,
  FileBadge,
  FileText,
  Image,
} from 'lucide-react';
import type {
  EventLineReportSnapshot,
  EventLineReportAttachment,
  EventLineActivity,
  Task,
} from '../../../shared/types.js';
import { getEventLineReportSnapshot, getOrgModelProfile, updateEventLine } from '../../lib/api.js';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type EditableActivity = EventLineActivity & {
  /** 用户在本地编辑过的标题 */
  editedTitle?: string;
  /** 用户在本地编辑过的摘要 */
  editedSummary?: string;
  /** 用户标记为隐藏（不纳入导出） */
  hidden?: boolean;
};

type ReportDraft = {
  eventLineName: string;
  summary: string;
  activities: EditableActivity[];
  attachments: EventLineReportAttachment[];
  tasks: Task[];
  participantNames: string[];
  snapshotAt: string;
};

type PreviewCard = {
  label: string;
  value: string;
  note: string;
};

type PreviewSection = {
  index: string;
  title: string;
  pages: string;
  summary: string;
};

type PreviewModel = {
  hasRenderableContent: boolean;
  organizationName: string;
  brandCaption: string;
  reportTitle: string;
  reportSubtitle: string;
  coverSummary: string;
  coreJudgment: string;
  coreJudgmentNote: string;
  reviewWindow: string;
  kindLabel: string;
  statusLabel: string;
  statusTone: string;
  clientName: string;
  audienceLabel: string;
  departmentName: string;
  ownerName: string;
  snapshotAtLabel: string;
  participantNames: string[];
  participantSummary: string;
  supportCards: PreviewCard[];
  tocSections: PreviewSection[];
  reviewQuestions: string[];
  deliverables: string[];
  readingSteps: string[];
  readingIntro: string;
  pageOneNote: string;
  pageTwoNote: string;
  emptyStateTitle: string;
  emptyStateDescription: string;
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const SOURCE_TYPE_LABELS: Record<string, string> = {
  task_activity: '任务',
  meeting: '会议',
  support_request: '支持请求',
  review: '复核',
  attachment: '附件',
  manual_note: '备注',
};

const EVENT_LINE_KIND_LABELS: Record<string, string> = {
  project_line: '项目线',
  issue_line: '议题线',
  coordination_line: '协同线',
  case_line: '案例线',
  custom: '事件线',
};

const EVENT_LINE_STATUS_LABELS: Record<string, string> = {
  active: '推进中',
  blocked: '存在阻点',
  paused: '暂缓中',
  done: '已完成',
  archived: '已归档',
};

const EVENT_LINE_STATUS_TONE: Record<string, string> = {
  active: 'border-emerald-300/30 bg-emerald-400/15 text-emerald-50',
  blocked: 'border-rose-300/30 bg-rose-400/15 text-rose-50',
  paused: 'border-amber-300/30 bg-amber-400/15 text-amber-50',
  done: 'border-sky-300/30 bg-sky-400/15 text-sky-50',
  archived: 'border-white/20 bg-white/10 text-white/75',
};

/** Key events: task created, manual note (review content), attachment upload.
 *  Uses backend-computed `isKey` flag; falls back to heuristic for older data. */
function isKeyActivity(activity: { sourceType: string; title: string; summary: string; isKey?: boolean; metadata?: Record<string, unknown> }): boolean {
  if (activity.isKey !== undefined) return activity.isKey;
  // Fallback for activities without backend isKey flag
  if (['manual_note', 'attachment'].includes(activity.sourceType)) return true;
  if (activity.sourceType === 'task_activity' && activity.metadata?.eventType === 'created') return true;
  return false;
}

function isBootstrapActivity(activity: EditableActivity): boolean {
  const metadata = activity.metadata || {};
  const eventType = String((metadata as Record<string, unknown>).eventType || '').toLowerCase();
  if (activity.sourceType === 'task_activity' && eventType === 'created') return true;
  if (eventType === 'event_line_created' || eventType === 'line_created') return true;
  const text = `${previewActivityTitle(activity)} ${previewActivitySummary(activity)}`.toLowerCase();
  return text.includes('创建事件线') || text.includes('created event line');
}

function isMeaningfulPreviewActivity(activity: EditableActivity): boolean {
  if (isBootstrapActivity(activity)) return false;
  return Boolean(previewActivitySummary(activity) || previewActivityTitle(activity));
}

function formatTs(iso: string) {
  if (!iso) return '';
  return iso.slice(0, 16).replace('T', ' ');
}

function formatDateLabel(iso?: string | null) {
  if (!iso) return '待补充';
  return iso.slice(0, 10).replace(/-/g, '.');
}

function truncateText(value: string | null | undefined, maxLength: number) {
  const normalized = (value || '').replace(/\s+/g, ' ').trim();
  if (!normalized) return '';
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, Math.max(0, maxLength - 1)).trim()}…`;
}

function normalizeText(value: string | null | undefined) {
  return (value || '').replace(/\s+/g, ' ').trim();
}

function dedupeStrings(items: Array<string | null | undefined>) {
  return Array.from(
    new Set(items.map((item) => normalizeText(item)).filter(Boolean)),
  );
}

function formatReadableList(items: string[], limit = 4) {
  const normalized = dedupeStrings(items);
  if (normalized.length === 0) return '';
  if (normalized.length <= limit) return normalized.join('、');
  return `${normalized.slice(0, limit).join('、')} 等`;
}

function previewActivityTitle(activity: EditableActivity) {
  return normalizeText(activity.editedTitle) || normalizeText(activity.title) || '未命名活动';
}

function previewActivitySummary(activity: EditableActivity) {
  return normalizeText(activity.editedSummary) || normalizeText(activity.summary);
}

function isImageAttachment(att: EventLineReportAttachment) {
  return (att.mimeType || '').startsWith('image/') || /\.(jpg|jpeg|png|gif|webp)$/i.test(att.title);
}

function attachmentFamilyLabel(att: EventLineReportAttachment) {
  if (isImageAttachment(att)) return '图像证据';
  const ext = (att.title.split('.').pop() || '').toLowerCase();
  if (ext === 'pdf') return 'PDF 资料';
  if (['doc', 'docx'].includes(ext)) return 'Word 文档';
  if (['xls', 'xlsx'].includes(ext)) return '表格资料';
  if (['ppt', 'pptx'].includes(ext)) return '汇报材料';
  return '补充资料';
}

function fileSizeLabel(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function attachmentFamilySummary(attachments: EventLineReportAttachment[]) {
  const familyCounts = new Map<string, number>();
  for (const attachment of attachments) {
    const family = attachmentFamilyLabel(attachment);
    familyCounts.set(family, (familyCounts.get(family) || 0) + 1);
  }
  const entries = Array.from(familyCounts.entries()).sort((left, right) => {
    if (right[1] !== left[1]) return right[1] - left[1];
    return left[0].localeCompare(right[0], 'zh-CN');
  });
  return {
    entries,
    shortText: entries.length > 0 ? entries.slice(0, 3).map(([label]) => label).join('、') : '暂无附件',
    detailedText: entries.length > 0 ? entries.slice(0, 3).map(([label, count]) => `${label}${count}份`).join('、') : '暂无附件材料',
  };
}

function previewPageLabel(index: number, isLast: boolean) {
  const startPage = 3 + index * 2;
  if (isLast) return `P${String(startPage).padStart(2, '0')}+`;
  return `P${String(startPage).padStart(2, '0')}-P${String(startPage + 1).padStart(2, '0')}`;
}

function buildCoreJudgmentText({
  blockerText,
  decisionText,
  nextStepText,
  latestSignals,
}: {
  blockerText: string;
  decisionText: string;
  nextStepText: string;
  latestSignals: string[];
}) {
  if (decisionText && nextStepText) {
    return `已形成“${truncateText(decisionText, 28)}”，当前要把“${truncateText(nextStepText, 28)}”继续推进到明确结果。`;
  }
  if (blockerText && nextStepText) {
    return `当前卡点是“${truncateText(blockerText, 28)}”，需要围绕“${truncateText(nextStepText, 28)}”继续收束责任人与时间点。`;
  }
  if (decisionText) {
    return `最近已经形成“${truncateText(decisionText, 34)}”，下一步重点是确认这个判断是否真正带动了后续推进。`;
  }
  if (nextStepText) {
    return `当前最需要盯住的是“${truncateText(nextStepText, 34)}”，确保这一步不再停留在口头判断。`;
  }
  if (latestSignals.length >= 2) {
    return `最近的关键推进集中在“${truncateText(latestSignals[0], 26)}”和“${truncateText(latestSignals[1], 26)}”。`;
  }
  if (latestSignals.length === 1) {
    return `目前最值得关注的进展是“${truncateText(latestSignals[0], 40)}”。`;
  }
  return '当前资料不足，建议先补活动记录、阶段判断或附件材料，再生成对外汇报。';
}

function deriveReportPreview(
  snapshot: EventLineReportSnapshot,
  draft: ReportDraft,
  visibleActivities: EditableActivity[],
  organizationName: string,
): PreviewModel {
  const eventLine = snapshot.eventLine;
  const sortedActivities = [...visibleActivities].sort((left, right) => left.happenedAt.localeCompare(right.happenedAt));
  const meaningfulActivities = sortedActivities.filter((activity) => isMeaningfulPreviewActivity(activity));
  const keyActivities = meaningfulActivities.filter((activity) => isKeyActivity(activity));
  const milestoneSource = keyActivities.length > 0 ? keyActivities : meaningfulActivities;
  const latestMilestone = milestoneSource[milestoneSource.length - 1] || null;
  const latestMilestoneSignal = latestMilestone
    ? previewActivitySummary(latestMilestone) || previewActivityTitle(latestMilestone)
    : '';
  const latestSignals = milestoneSource
    .slice(-2)
    .reverse()
    .map((activity) => previewActivitySummary(activity) || previewActivityTitle(activity));
  const clientName = normalizeText(eventLine.primaryClientName);
  const kindLabel = EVENT_LINE_KIND_LABELS[eventLine.kind] || '事件线';
  const statusLabel = EVENT_LINE_STATUS_LABELS[eventLine.status] || eventLine.status;
  const statusTone = EVENT_LINE_STATUS_TONE[eventLine.status] || EVENT_LINE_STATUS_TONE.archived;
  const blockerText = normalizeText(eventLine.currentBlocker);
  const decisionText = normalizeText(eventLine.recentDecision);
  const nextStepText = normalizeText(eventLine.nextStep);
  const ownerName = normalizeText(eventLine.ownerName) || '待指定负责人';
  const departmentName = normalizeText(eventLine.primaryDepartmentName) || '未设置归属部门';
  const attachmentCount = draft.attachments.length;
  const taskCount = draft.tasks.length;
  const completedTaskCount = draft.tasks.filter((task) => task.status === 'done').length;
  const pendingTaskCount = draft.tasks.filter((task) => !['done', 'rejected'].includes(task.status)).length;
  const participantSummary = formatReadableList(draft.participantNames, 4) || ownerName;
  const familySummary = attachmentFamilySummary(draft.attachments);
  const startAt = sortedActivities[0]?.happenedAt || eventLine.createdAt || snapshot.snapshotAt;
  const endAt = sortedActivities[sortedActivities.length - 1]?.happenedAt || snapshot.snapshotAt || eventLine.updatedAt;
  const reviewWindow = `${formatDateLabel(startAt)} - ${formatDateLabel(endAt)}`;
  const hasNarrativeEvidence = [
    normalizeText(eventLine.intent),
    normalizeText(draft.summary),
    normalizeText(eventLine.summary),
    blockerText,
    decisionText,
    nextStepText,
  ].some((item) => item.length >= 6);
  const hasRenderableContent = (
    meaningfulActivities.length >= 2
    || (meaningfulActivities.length >= 1 && (attachmentCount > 0 || taskCount > 0))
    || hasNarrativeEvidence
    || attachmentCount > 0
    || taskCount >= 2
  );

  const reportTitle = normalizeText(draft.eventLineName) || normalizeText(eventLine.name) || '事件线汇报';
  const reportSubtitle = clientName ? `${clientName} · ${kindLabel}汇报` : `${kindLabel}汇报`;
  const normalizedOrganizationName = normalizeText(organizationName) || '当前组织';
  const emptySummaryFallback = '当前资料不足，暂无法生成模拟汇报。请先在素材清单中补充活动说明、阶段判断或附件材料。';
  const coverSummarySource = (
    normalizeText(eventLine.intent)
      || normalizeText(draft.summary)
      || normalizeText(eventLine.summary)
      || (hasRenderableContent ? latestMilestoneSignal : '')
  );
  const coverSummary = truncateText(
    coverSummarySource || emptySummaryFallback,
    122,
  ) || emptySummaryFallback;

  const contentScaleValue = `关键 ${milestoneSource.length} / 活动 ${sortedActivities.length}`;
  const contentScaleNote = `附件 ${attachmentCount} · 任务 ${taskCount}`;

  const sectionSeeds = [
    {
      title: '事件背景与目标',
      summary: truncateText(
        normalizeText(eventLine.intent)
          || normalizeText(draft.summary)
          || normalizeText(eventLine.summary)
          || `${kindLabel}当前处于“${statusLabel}”，需要先补充阶段背景与目标说明。`,
        82,
      ),
    },
    {
      title: '关键里程碑',
      summary: milestoneSource.length > 0
        ? truncateText(`已记录 ${milestoneSource.length} 条关键活动，最近一条是“${previewActivityTitle(latestMilestone || milestoneSource[0])}”。`, 82)
        : '尚未沉淀关键里程碑，建议先在素材清单里补充活动记录。',
    },
    {
      title: '任务推进',
      summary: taskCount > 0
        ? truncateText(`关联任务 ${taskCount} 条，已完成 ${completedTaskCount} 条，待推进 ${pendingTaskCount} 条。${nextStepText ? `当前下一步是“${nextStepText}”。` : ''}`, 82)
        : '当前没有关联任务，建议补充执行动作、责任人和时间点。',
    },
    {
      title: '材料与证据',
      summary: attachmentCount > 0 || eventLine.evidenceCount > 0
        ? truncateText(`当前已有 ${attachmentCount} 份附件，材料类型覆盖 ${familySummary.detailedText}。证据计数 ${eventLine.evidenceCount}。`, 82)
        : '暂未沉淀附件材料，导出时只能依赖活动描述与阶段判断。',
    },
    {
      title: '风险与阻点',
      summary: blockerText
        ? truncateText(`当前主要阻点是“${blockerText}”，需要核对是否已有明确应对动作。`, 82)
        : pendingTaskCount > 0
          ? truncateText(`仍有 ${pendingTaskCount} 条未完成任务需要推进，建议重点关注依赖关系与节奏风险。`, 82)
          : '当前没有突出的阻点记录，但仍建议在复盘中核对潜在风险。',
    },
    {
      title: '决策与下一步',
      summary: decisionText || nextStepText
        ? truncateText(`最近决策：${decisionText || '待补充'}。下一步：${nextStepText || '待补充'}。`, 82)
        : latestMilestoneSignal
          ? truncateText(`可以从最近活动“${latestMilestoneSignal}”继续推演下一步动作。`, 82)
          : '尚未形成明确的下一步动作，建议先补阶段判断。',
    },
  ];

  if (draft.participantNames.length > 0 || normalizeText(eventLine.ownerName) || normalizeText(eventLine.primaryDepartmentName)) {
    sectionSeeds.push({
      title: '协作与责任',
      summary: truncateText(`负责人 ${ownerName}，归属 ${departmentName}，当前参与者 ${participantSummary}。`, 82),
    });
  }

  const tocSections = sectionSeeds.slice(0, 7).map((section, index, array) => ({
    index: String(index + 1).padStart(2, '0'),
    title: section.title,
    pages: previewPageLabel(index, index === array.length - 1),
    summary: section.summary,
  }));

  const readingSteps = dedupeStrings([
    blockerText ? `先看风险与阻点，确认“${truncateText(blockerText, 18)}”是否已有应对动作。` : '',
    pendingTaskCount > 0 ? `再看任务推进，优先识别 ${pendingTaskCount} 条未完成任务里最影响节奏的部分。` : '',
    attachmentCount > 0 ? `随后核对材料与证据，确认现有 ${attachmentCount} 份附件是否足够支撑当前判断。` : '',
    nextStepText ? `最后检查下一步“${truncateText(nextStepText, 18)}”是否已经落实到责任人与时间点。` : '',
  ]);
  while (readingSteps.length < 3) {
    readingSteps.push(
      [
        '先建立这条事件线当前的阶段判断，再回到活动和附件核对事实依据。',
        '把关键活动、关联任务和当前阻点对齐，避免只看动作不看收束程度。',
        '最后确认下一步动作是否足够明确，便于直接用于后续协作或导出。',
      ][readingSteps.length],
    );
  }

  const reviewQuestions = dedupeStrings([
    blockerText ? `当前阻点“${truncateText(blockerText, 22)}”是否已经拆成了具体应对动作？` : '',
    decisionText ? `最近形成的关键决策“${truncateText(decisionText, 22)}”会怎样影响后续推进？` : '',
    nextStepText ? `下一步“${truncateText(nextStepText, 22)}”是否已经落实到责任人与时间点？` : '',
    pendingTaskCount > 0 ? `剩余 ${pendingTaskCount} 条未完成任务里，哪一条最影响整体推进节奏？` : '',
    attachmentCount > 0 ? `现有 ${attachmentCount} 份材料是否足以支撑当前判断与对外汇报？` : '',
    milestoneSource.length > 0 ? '最近关键活动能否证明这条事件线确实产生了阶段性进展？' : '',
  ]).slice(0, 4);
  while (reviewQuestions.length < 4) {
    reviewQuestions.push(
      [
        '这条事件线目前最需要被看清的阶段判断是什么？',
        '有哪些事实已经足够明确，哪些判断仍需要补材料验证？',
        '如果现在导出汇报，最容易被追问的缺口会是什么？',
        '下一步最应该推动的动作，是否已经写到可以执行的程度？',
      ][reviewQuestions.length],
    );
  }

  const deliverables = dedupeStrings([
    milestoneSource.length > 0 ? `${milestoneSource.length} 条关键活动摘要与时间线` : '',
    taskCount > 0 ? `${taskCount} 条关联任务推进状态` : '',
    attachmentCount > 0 ? `${attachmentCount} 份附件材料（${familySummary.shortText}）` : '',
    draft.participantNames.length > 0 || normalizeText(eventLine.ownerName) ? '参与人名单与责任分工说明' : '',
    blockerText || decisionText || nextStepText ? '当前阻点、近期决策与下一步建议' : '',
    '导出时间与快照范围说明',
  ]).slice(0, 6);

  return {
    hasRenderableContent,
    organizationName: normalizedOrganizationName,
    brandCaption: 'EVENT LINE REPORT',
    reportTitle,
    reportSubtitle,
    coverSummary,
    coreJudgment: buildCoreJudgmentText({
      blockerText,
      decisionText,
      nextStepText,
      latestSignals,
    }),
    coreJudgmentNote: dedupeStrings([
      decisionText ? `最近决策：${truncateText(decisionText, 28)}` : '',
      blockerText ? `当前阻点：${truncateText(blockerText, 28)}` : '',
      nextStepText ? `下一步：${truncateText(nextStepText, 28)}` : '',
      milestoneSource.length > 0 ? `最近关键活动 ${milestoneSource.length} 条` : '',
    ]).slice(0, 2).join(' · ') || '当前仅能基于已有快照生成基础判断，建议继续补充活动说明与附件。',
    reviewWindow,
    kindLabel,
    statusLabel,
    statusTone,
    clientName,
    audienceLabel: participantSummary || '待补充参与信息',
    departmentName,
    ownerName,
    snapshotAtLabel: formatDateLabel(snapshot.snapshotAt),
    participantNames: draft.participantNames,
    participantSummary,
    supportCards: [
      {
        label: '汇报类型',
        value: '事件线汇报',
        note: `${kindLabel} · ${statusLabel}`,
      },
      {
        label: '时间范围',
        value: reviewWindow,
        note: `快照日期 ${formatDateLabel(snapshot.snapshotAt)}`,
      },
      {
        label: '内容规模',
        value: contentScaleValue,
        note: contentScaleNote,
      },
    ],
    tocSections,
    reviewQuestions,
    deliverables,
    readingSteps: readingSteps.slice(0, 3),
    readingIntro: hasRenderableContent
      ? `先快速建立这条${kindLabel}的阶段判断，再回到里程碑、任务推进、材料证据与后续动作逐项核对。`
      : '当前资料还不足以组织完整模拟汇报，建议先切到素材清单补充活动说明、任务状态或附件材料。',
    pageOneNote: hasRenderableContent
      ? `${kindLabel} · ${statusLabel} · 快照 ${formatDateLabel(snapshot.snapshotAt)}`
      : '当前资料不足，建议先切换到素材清单补资料。',
    pageTwoNote: hasRenderableContent
      ? '目录依据当前事件线快照自动生成，已包含关键活动、任务、附件和下一步信息。'
      : '目录页仅在形成足够阶段信息后展示。',
    emptyStateTitle: '资料不足，暂无法生成模拟汇报',
    emptyStateDescription: '当前事件线缺少足够的活动、任务、附件或阶段判断。先到素材清单里补活动说明、任务状态或附件材料，再回来预览更合适。',
  };
}

/* ------------------------------------------------------------------ */
/*  DocContentViewer — loads and displays document text content         */
/* ------------------------------------------------------------------ */

/** Map file extension to a display label + color for the file-type badge */
function fileTypeBadge(filename: string): { label: string; color: string; bg: string } {
  const ext = (filename.split('.').pop() || '').toLowerCase();
  switch (ext) {
    case 'doc': case 'docx': return { label: 'Word', color: '#2B579A', bg: '#E8EEF7' };
    case 'xls': case 'xlsx': return { label: 'Excel', color: '#217346', bg: '#E2F0E8' };
    case 'ppt': case 'pptx': return { label: 'PPT', color: '#D24726', bg: '#FCEAE5' };
    case 'pdf': return { label: 'PDF', color: '#B30B00', bg: '#FDE8E7' };
    case 'txt': case 'md': return { label: 'TXT', color: '#6B7280', bg: '#F3F4F6' };
    case 'jpg': case 'jpeg': case 'png': case 'gif': case 'webp': return { label: ext.toUpperCase(), color: '#7C3AED', bg: '#EDE9FE' };
    default: return { label: ext.toUpperCase() || '文件', color: '#6B7280', bg: '#F3F4F6' };
  }
}

function DocContentViewer({ att, backendBaseUrl }: { att: EventLineReportAttachment; backendBaseUrl: string }) {
  const [summary, setSummary] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const badge = fileTypeBadge(att.title);

  useEffect(() => {
    // Try text-content first, fall back to ocr-summary
    void fetch(`${backendBaseUrl}/api/public/task-attachments/${att.id}/text-content`)
      .then((r) => r.json())
      .then((data: { text?: string; unsupported?: boolean }) => {
        const text = (data.text || '').trim();
        if (text && !text.includes('提取失败') && !text.includes('No module') && !data.unsupported) {
          setSummary(text);
        } else {
          // Fall back to ocr-summary
          return fetch(`${backendBaseUrl}/api/public/task-attachments/${att.id}/ocr-summary`)
            .then((r2) => r2.json())
            .then((ocr: { summary?: string; unsupported?: boolean }) => {
              if (ocr.summary && !ocr.unsupported) {
                setSummary(ocr.summary);
              } else {
                setSummary(null);
              }
            });
        }
      })
      .catch(() => setSummary(null))
      .finally(() => setLoading(false));
  }, [att.id, backendBaseUrl]);

  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
      {/* File header — icon badge + filename, looks like a file preview */}
      <div className="flex items-center gap-2.5 px-3 py-2.5 bg-gray-50/80 border-b border-gray-100">
        <div
          className="flex-shrink-0 flex items-center justify-center rounded-lg w-9 h-9 text-[10px] font-bold"
          style={{ backgroundColor: badge.bg, color: badge.color }}
        >
          {badge.label}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[12px] font-medium text-gray-800 truncate">{att.title}</p>
          <p className="text-[10px] text-gray-400">{fileSizeLabel(att.sizeBytes)}</p>
        </div>
        <a
          href={`${backendBaseUrl}${att.downloadUrl}`}
          download={att.title}
          className="flex-shrink-0 rounded p-1 text-gray-400 hover:text-[#5B7BFE] hover:bg-gray-100 transition"
          title="下载文件"
        >
          <Download size={14} />
        </a>
      </div>
      {/* AI summary */}
      <div className="px-3 py-2">
        {loading ? (
          <div className="flex items-center gap-1.5">
            <div className="h-2.5 w-2.5 animate-spin rounded-full border-2 border-gray-300 border-t-[#5B7BFE]" />
            <span className="text-[10px] text-gray-400">正在提取文档摘要…</span>
          </div>
        ) : summary ? (
          <pre className="max-h-[600px] overflow-y-auto whitespace-pre-wrap text-[11px] leading-5 text-gray-500">{summary}</pre>
        ) : (
          <p className="text-[10px] text-gray-300">暂无文档摘要</p>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  ImageWithOcr — image preview with OCR summary below                */
/* ------------------------------------------------------------------ */

function ImageWithOcr({ att, backendBaseUrl }: { att: EventLineReportAttachment; backendBaseUrl: string }) {
  const [ocrText, setOcrText] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void fetch(`${backendBaseUrl}/api/public/task-attachments/${att.id}/ocr-summary`)
      .then((r) => r.json())
      .then((data: { summary?: string; unsupported?: boolean }) => {
        if (data.summary && !data.unsupported) {
          setOcrText(data.summary);
        } else {
          setOcrText(null);
        }
      })
      .catch(() => setOcrText(null))
      .finally(() => setLoading(false));
  }, [att.id, backendBaseUrl]);

  return (
    <div className="rounded-xl border border-gray-200 overflow-hidden bg-gray-50">
      <img
        src={`${backendBaseUrl}${att.downloadUrl}`}
        alt={att.title}
        className="w-full object-contain max-h-[300px]"
      />
      <div className="px-2 py-1.5">
        <p className="text-[10px] text-gray-500 truncate">{att.title}</p>
        {loading ? (
          <div className="mt-1 flex items-center gap-1">
            <div className="h-2 w-2 animate-spin rounded-full border border-gray-300 border-t-[#5B7BFE]" />
            <span className="text-[9px] text-gray-400">识别中…</span>
          </div>
        ) : ocrText ? (
          <p className="mt-1 text-[10px] leading-4 text-gray-400">{ocrText}</p>
        ) : null}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

type Props = {
  eventLineId: string;
  backendBaseUrl: string;
  onClose: () => void;
  onExportWord: (draft: ReportDraft) => void;
};

export default function EventLineReportPanel({ eventLineId, backendBaseUrl, onClose, onExportWord }: Props) {
  const [snapshot, setSnapshot] = useState<EventLineReportSnapshot | null>(null);
  const [organizationName, setOrganizationName] = useState('');
  const [uploadProgressByActivity, setUploadProgressByActivity] = useState<Record<string, { current: number; total: number; fileName: string; error?: string }>>({});
  const [exportProgress, setExportProgress] = useState<{ stage: string; detail: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /* Local editable draft — built from immutable cloud snapshot */
  const [draft, setDraft] = useState<ReportDraft | null>(null);

  /* Per-activity toggle: which activities have docs expanded / images expanded */
  const [docsExpandedActivities, setDocsExpandedActivities] = useState<Set<string>>(new Set());
  const [imagesExpandedActivities, setImagesExpandedActivities] = useState<Set<string>>(new Set());
  const [showSystemTraces, setShowSystemTraces] = useState(false);
  const [viewMode, setViewMode] = useState<'preview' | 'materials'>('preview');

  /* Track which attachments are expanded (legacy, kept for export) */
  const [expandedAttachments, setExpandedAttachments] = useState<Set<string>>(new Set());

  /* Fetch immutable snapshot from cloud */
  useEffect(() => {
    setSnapshot(null);
    setOrganizationName('');
    setDraft(null);
    setError(null);
    setLoading(true);
    setUploadProgressByActivity({});
    setExportProgress(null);
    setDocsExpandedActivities(new Set());
    setImagesExpandedActivities(new Set());
    setExpandedAttachments(new Set());
    setShowSystemTraces(false);
    setViewMode('preview');
  }, [eventLineId]);

  const loadSnapshot = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const [data, orgProfile] = await Promise.all([
        getEventLineReportSnapshot(eventLineId),
        getOrgModelProfile().catch(() => null),
      ]);
      setSnapshot(data);
      const orgName = normalizeText(orgProfile?.organization?.name);
      setOrganizationName(orgName);
      setDraft((prev) => {
        // Preserve user edits during silent refresh
        const prevEditMap = new Map<string, { editedTitle?: string; editedSummary?: string }>();
        if (options?.silent && prev) {
          for (const a of prev.activities) {
            if (a.editedTitle || a.editedSummary) {
              prevEditMap.set(a.id, { editedTitle: a.editedTitle, editedSummary: a.editedSummary });
            }
          }
        }
        return {
          eventLineName: options?.silent && prev ? prev.eventLineName : data.eventLine.name,
          summary: options?.silent && prev ? prev.summary : data.eventLine.summary ?? '',
          activities: data.activities.map((a: EventLineActivity) => ({
            ...a,
            ...(prevEditMap.get(a.id) || {}),
          })),
          attachments: [...data.attachments],
          tasks: [...(data.tasks || [])],
          participantNames: [...data.participantNames],
          snapshotAt: data.snapshotAt,
        };
      });
    } catch (err) {
      if (!options?.silent) {
        setError(err instanceof Error ? err.message : '加载事件线快照失败');
      }
    } finally {
      if (!options?.silent) {
        setLoading(false);
      }
    }
  }, [eventLineId]);

  useEffect(() => {
    void loadSnapshot();
  }, [loadSnapshot]);

  /* Group attachments by activity — match via metadata.taskId or sourceId */
  const attachmentsByActivity = useMemo(() => {
    if (!draft) return new Map<string, EventLineReportAttachment[]>();
    const map = new Map<string, EventLineReportAttachment[]>();
    for (const att of draft.attachments) {
      // Try to match to an activity via metadata.taskId or sourceId
      const matchingActivity = draft.activities.find((a) => {
        const meta = a.metadata as Record<string, unknown> | undefined;
        if (meta?.taskId && String(meta.taskId) === att.taskId) return true;
        if (meta?.attachmentId && String(meta.attachmentId) === att.id) return true;
        if (a.sourceType === 'attachment' && a.sourceId === att.id) return true;
        return false;
      });
      const key = matchingActivity?.id || att.taskId || '_unlinked';
      const list = map.get(key) || [];
      list.push(att);
      map.set(key, list);
    }
    return map;
  }, [draft]);

  /* Build task lookup map: taskId → Task for displaying task details in activities */
  const taskMap = useMemo(() => {
    const m = new Map<string, Task>();
    if (draft) for (const t of (draft.tasks || [])) m.set(t.id, t);
    return m;
  }, [draft]);

  /* Edit handlers — only modify the local draft */
  const updateActivityField = useCallback(
    (activityId: string, field: 'editedTitle' | 'editedSummary', value: string) => {
      setDraft((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          activities: prev.activities.map((a) => (a.id === activityId ? { ...a, [field]: value } : a)),
        };
      });
    },
    [],
  );

  const toggleActivityHidden = useCallback((activityId: string) => {
    setDraft((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        activities: prev.activities.map((a) => (a.id === activityId ? { ...a, hidden: !a.hidden } : a)),
      };
    });
  }, []);

  const toggleAttachmentExpand = useCallback((attachmentId: string) => {
    setExpandedAttachments((prev) => {
      const next = new Set(prev);
      if (next.has(attachmentId)) next.delete(attachmentId);
      else next.add(attachmentId);
      return next;
    });
  }, []);

  const visibleActivities = useMemo(() => (draft?.activities ?? []).filter((a) => !a.hidden), [draft]);

  const reportPreview = useMemo(() => {
    if (!draft || !snapshot) return null;
    return deriveReportPreview(snapshot, draft, visibleActivities, organizationName);
  }, [draft, snapshot, visibleActivities, organizationName]);

  /* Auto-save summary with debounce */
  const summaryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const saveSummary = useCallback(
    (newSummary: string) => {
      if (summaryTimerRef.current) clearTimeout(summaryTimerRef.current);
      summaryTimerRef.current = setTimeout(() => {
        void updateEventLine(eventLineId, { summary: newSummary } as Parameters<typeof updateEventLine>[1]).catch(() => {});
      }, 800);
    },
    [eventLineId],
  );
  // Cleanup timer on unmount
  useEffect(() => () => { if (summaryTimerRef.current) clearTimeout(summaryTimerRef.current); }, []);

  /* ---------------------------------------------------------------- */
  /*  Render                                                           */
  /* ---------------------------------------------------------------- */

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-md">
        <div className="rounded-3xl bg-white px-10 py-8 text-center shadow-xl">
          <p className="text-[13px] text-gray-500">正在从云端拉取完整事件线...</p>
        </div>
      </div>
    );
  }

  if (error || !draft || !snapshot) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-md">
        <div className="rounded-3xl bg-white px-10 py-8 text-center shadow-xl">
          <p className="text-[13px] text-red-600">{error || '无法加载事件线'}</p>
          <button type="button" className="mt-4 rounded-2xl bg-gray-100 px-4 py-2 text-[12px]" onClick={onClose}>
            关闭
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4 backdrop-blur-md animate-in fade-in">
      <div
        className="relative flex max-h-[90vh] w-full max-w-[860px] flex-col rounded-[28px] border border-gray-100 bg-white shadow-[0_20px_60px_rgba(0,0,0,0.15)]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── Header ── */}
        <div className="flex items-start gap-4 border-b border-gray-100 p-6 pb-4">
          <button
            type="button"
            className="mt-1 rounded-2xl border border-gray-200 bg-white p-2 text-gray-400 transition hover:text-gray-700"
            onClick={onClose}
          >
            <X size={16} />
          </button>
          <div className="flex-1 min-w-0">
            <p className="text-[12px] font-bold tracking-[0.12em] text-[#5B7BFE]">事件线汇报</p>
            <h2 className="mt-1 text-[20px] font-bold text-gray-900">{draft.eventLineName}</h2>
            <textarea
              className="mt-2 w-full resize-none rounded-lg border border-transparent bg-transparent px-0 text-[13px] leading-6 text-gray-500 transition hover:border-gray-200 focus:border-[#5B7BFE] focus:bg-white focus:px-2 focus:py-1 focus:outline-none"
              rows={Math.max(2, (draft.summary || '').split('\n').length)}
              placeholder="点击编辑事件线说明…"
              value={draft.summary}
              onChange={(e) => {
                const val = e.target.value;
                setDraft((prev) => prev ? { ...prev, summary: val } : prev);
                saveSummary(val);
              }}
            />
          </div>
          <button
            type="button"
            disabled={!!exportProgress}
            className={`shrink-0 flex items-center gap-2 rounded-2xl px-5 py-2.5 text-[12px] font-bold text-white transition ${exportProgress ? 'bg-blue-400' : 'bg-[#5B7BFE] hover:bg-[#4a6ae8]'}`}
            onClick={() => {
              const exportDraft = {
                ...draft,
                expandedAttachmentIds: Array.from(expandedAttachments),
                docsExpandedActivityIds: Array.from(docsExpandedActivities),
                imagesExpandedActivityIds: Array.from(imagesExpandedActivities),
                showSystemTraces,
              };
              setExportProgress({ stage: '准备导出...', detail: '正在整理事件线数据' });
              void (async () => {
                try {
                  setExportProgress({ stage: '生成文档...', detail: `正在处理 ${draft.activities.length} 条活动记录和 ${draft.attachments.length} 个附件` });
                  const response = await fetch(`${backendBaseUrl}/api/v1/event-lines/${eventLineId}/export-word`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(exportDraft),
                  });
                  if (!response.ok) throw new Error(`导出失败 (${response.status})`);
                  const result = await response.json();
                  if (!result.filePath) throw new Error('后端未返回文件路径');
                  setExportProgress({ stage: '保存文件...', detail: '文档已生成，请选择保存位置' });
                  const saved = await window.yiyuWorkbench?.saveFileAs(result.filePath, result.fileName);
                  if (saved) {
                    setExportProgress({ stage: '导出成功', detail: `已保存到 ${saved}` });
                    setTimeout(() => setExportProgress(null), 2000);
                  } else {
                    setExportProgress(null);
                  }
                } catch (err) {
                  setExportProgress({ stage: '导出失败', detail: err instanceof Error ? err.message : '未知错误' });
                  setTimeout(() => setExportProgress(null), 3000);
                }
              })();
            }}
          >
            <Download size={14} />
            {exportProgress ? '导出中...' : '导出 Word'}
          </button>
        </div>

        {/* ── Meta badges ── */}
        <div className="flex flex-wrap items-center gap-2 border-b border-gray-50 px-6 py-3 text-[11px]">
          <span className="flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-1 font-bold text-emerald-700">
            {snapshot.eventLine.status}
          </span>
          {snapshot.eventLine.stage && (
            <span className="rounded-full bg-amber-50 px-2.5 py-1 font-bold text-amber-700">{snapshot.eventLine.stage}</span>
          )}
          {snapshot.eventLine.primaryClientName && (
            <span className="rounded-full bg-violet-50 px-2.5 py-1 font-bold text-violet-700">{snapshot.eventLine.primaryClientName}</span>
          )}
          {draft.participantNames.length > 0 && (
            <span className="flex items-center gap-1 rounded-full bg-blue-50 px-2.5 py-1 font-bold text-blue-700">
              <Users size={11} /> {draft.participantNames.join('、')}
            </span>
          )}
        </div>

        {/* ── Export progress overlay ── */}
        {exportProgress && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-white/80 backdrop-blur-sm rounded-[28px]">
            <div className="text-center px-8 py-6">
              <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-3 border-gray-200 border-t-[#5B7BFE]" />
              <p className="text-[14px] font-bold text-gray-800">{exportProgress.stage}</p>
              <p className="mt-1 text-[12px] text-gray-500">{exportProgress.detail}</p>
            </div>
          </div>
        )}

        {/* ── Scrollable body ── */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div className="inline-flex rounded-full bg-[#F4F6FB] p-1">
              <button
                type="button"
                className={`rounded-full px-4 py-2 text-[12px] font-bold transition ${viewMode === 'preview' ? 'bg-white text-[#1D3361] shadow-[0_6px_18px_rgba(31,56,110,0.12)]' : 'text-gray-500 hover:text-gray-700'}`}
                onClick={() => setViewMode('preview')}
              >
                模拟报告
              </button>
              <button
                type="button"
                className={`rounded-full px-4 py-2 text-[12px] font-bold transition ${viewMode === 'materials' ? 'bg-white text-[#1D3361] shadow-[0_6px_18px_rgba(31,56,110,0.12)]' : 'text-gray-500 hover:text-gray-700'}`}
                onClick={() => setViewMode('materials')}
              >
                素材清单
              </button>
            </div>
            <p className="text-right text-[11px] text-gray-400">
              {viewMode === 'preview'
                ? (reportPreview?.hasRenderableContent ? '当前为动态模拟汇报：封面页 + 目录页' : '当前资料不足，建议先切到素材清单补资料')
                : '素材流保留原始活动与附件明细，便于继续补资料'}
            </p>
          </div>

          {viewMode === 'preview' && reportPreview ? (
            reportPreview.hasRenderableContent ? (
            <div className="mx-auto max-w-[760px] space-y-8 pb-6">
              <section className="overflow-hidden rounded-[32px] border border-[#DDE4F3] bg-[#F9FBFF] shadow-[0_24px_70px_rgba(56,86,174,0.10)]">
                <div className="relative min-h-[1020px] px-10 py-10 text-[#3F3A36]">
                  <div
                    className="absolute inset-0"
                    style={{
                      background: 'radial-gradient(circle at 18% 14%, rgba(93, 125, 255, 0.14), transparent 26%), radial-gradient(circle at 85% 84%, rgba(123, 168, 255, 0.12), transparent 22%), linear-gradient(180deg, #F9FBFF 0%, #EEF3FD 100%)',
                    }}
                  />
                  <div className="absolute right-[-90px] top-[-90px] h-[280px] w-[280px] rounded-full bg-[radial-gradient(circle_at_30%_30%,rgba(112,143,255,0.26),rgba(112,143,255,0.05)_62%,transparent_74%)]" />
                  <div className="absolute bottom-[40px] right-[8px] h-[140px] w-[140px] rounded-full bg-[radial-gradient(circle_at_center,rgba(122,173,255,0.16),transparent_74%)]" />

                  <div className="relative flex h-full flex-col">
                    <div>
                      <p className="text-[11px] font-bold tracking-[0.16em] text-[#67718B]">{reportPreview.organizationName}</p>
                      <p className="mt-1 text-[11px] font-medium text-[#8A95AF]">{reportPreview.brandCaption}</p>
                      <span className="mt-5 inline-flex rounded-full bg-[#5B7BFE] px-4 py-2 text-[11px] font-bold text-white">
                        封面页
                      </span>
                    </div>

                    <div className="mt-24 max-w-[620px]">
                      <p className="text-[14px] font-semibold tracking-[0.08em] text-[#4B66D8]">{reportPreview.reportSubtitle}</p>
                      <h3 className="mt-5 text-[52px] font-semibold leading-[1.08] tracking-[-0.04em] text-[#3F3A36]">
                        {reportPreview.reportTitle}
                      </h3>
                      <div className="mt-7 h-[4px] w-12 rounded-full bg-[#5B7BFE]" />
                      <p className="mt-7 max-w-[560px] text-[16px] leading-8 text-[#6F685F]">
                        {reportPreview.coverSummary}
                      </p>
                    </div>

                    <div className="mt-20 max-w-[560px]">
                      <p className="text-[32px] font-semibold leading-[1.45] tracking-[-0.03em] text-[#5A524A]">
                        {reportPreview.coreJudgment}
                      </p>
                      <p className="mt-6 max-w-[460px] text-[13px] leading-6 text-[#8A8177]">
                        {reportPreview.coreJudgmentNote}
                      </p>
                    </div>

                    <div className="mt-auto rounded-[28px] border border-[#DDE4F3] bg-[linear-gradient(180deg,rgba(250,252,255,0.98)_0%,rgba(239,245,255,0.95)_100%)] px-6 py-6">
                      <div className="grid grid-cols-3 gap-4">
                        {reportPreview.supportCards.map((card, index) => (
                          <div
                            key={card.label}
                            className={`min-w-0 ${index < reportPreview.supportCards.length - 1 ? 'border-r border-[#D7E0F2] pr-4' : ''}`}
                          >
                            <p className="text-[11px] font-bold tracking-[0.12em] text-[#6C7897]">{card.label}</p>
                            <p className="mt-3 text-[22px] font-semibold tracking-[-0.02em] text-[#4B443E]">{card.value}</p>
                            <p className="mt-2 text-[12px] leading-5 text-[#6E778E]">{card.note}</p>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="mt-6 flex items-end justify-between text-[12px] text-[#9B9388]">
                      <p>{reportPreview.pageOneNote}</p>
                      <span className="font-medium tracking-[0.18em] text-[#4B66D8]">01 / 02</span>
                    </div>
                  </div>
                </div>
              </section>

              <section className="overflow-hidden rounded-[32px] border border-[#DDE4F3] bg-[#F9FBFF] shadow-[0_24px_60px_rgba(56,86,174,0.08)]">
                <div className="relative min-h-[1020px] px-10 py-10 text-[#3F3A36]">
                  <div
                    className="absolute inset-0"
                    style={{
                      background: 'radial-gradient(circle at 10% 12%, rgba(102, 132, 255, 0.10), transparent 24%), radial-gradient(circle at 88% 12%, rgba(132, 171, 255, 0.20), transparent 18%), linear-gradient(180deg, #F9FBFF 0%, #EEF3FD 100%)',
                    }}
                  />
                  <div className="absolute right-[22px] top-[-26px] h-[170px] w-[170px] rounded-full bg-[radial-gradient(circle_at_center,rgba(103,134,255,0.22),transparent_70%)]" />

                  <div className="relative">
                    <div className="flex items-start justify-between gap-6">
                      <div>
                        <p className="text-[11px] font-bold tracking-[0.18em] text-[#6B7692]">目录页</p>
                        <h3 className="mt-3 text-[34px] font-semibold tracking-[-0.03em] text-[#3F3A36]">目录与阅读指引</h3>
                        <div className="mt-4 h-[4px] w-12 rounded-full bg-[#5B7BFE]" />
                        <p className="mt-5 max-w-[520px] text-[13px] leading-6 text-[#756D65]">
                          {reportPreview.readingIntro}
                        </p>
                      </div>
                      <div className="rounded-[24px] border border-[#D7E0F2] bg-[linear-gradient(180deg,rgba(250,252,255,0.98)_0%,rgba(239,245,255,0.95)_100%)] px-5 py-4 shadow-[0_10px_24px_rgba(56,86,174,0.08)]">
                        <p className="text-[10px] font-bold tracking-[0.18em] text-[#4B66D8]">Report Profile</p>
                        <div className="mt-3 flex items-center gap-2 text-[13px] font-semibold text-[#4B443E]">
                          <Clock size={14} />
                          {reportPreview.reviewWindow}
                        </div>
                        <div className="mt-2 flex items-center gap-2 text-[13px] text-[#756D65]">
                          <Users size={14} />
                          {reportPreview.audienceLabel}
                        </div>
                      </div>
                    </div>

                    <div className="mt-8 grid grid-cols-12 gap-5">
                      <div className="col-span-7">
                        <div className="space-y-3">
                          {reportPreview.tocSections.slice(0, 7).map((section) => (
                            <div key={section.index} className="rounded-[22px] border border-[#DFE6F6] bg-white/82 px-5 py-4 shadow-[0_10px_24px_rgba(56,86,174,0.05)]">
                              <div className="flex items-start gap-4">
                                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-[#CFDBFB] bg-[#EEF3FF] text-[13px] font-bold text-[#4B66D8]">
                                  {section.index}
                                </div>
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-start justify-between gap-4">
                                    <p className="text-[16px] font-semibold tracking-[-0.02em] text-[#4B443E]">{section.title}</p>
                                    <span className="rounded-full bg-[#EAF0FF] px-2.5 py-1 text-[10px] font-bold text-[#4B66D8]">
                                      {section.pages}
                                    </span>
                                  </div>
                                  <p className="mt-2 text-[12px] leading-6 text-[#7A7269]">{section.summary}</p>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="col-span-5 space-y-5">
                        <div className="rounded-[28px] bg-[linear-gradient(180deg,#5B7BFE_0%,#3F5EF7_100%)] p-6 text-white shadow-[0_18px_40px_rgba(63,94,247,0.28)]">
                          <p className="text-[11px] font-bold tracking-[0.18em] text-white/75">建议阅读顺序</p>
                          <div className="mt-5 space-y-3">
                            {reportPreview.readingSteps.map((item, index) => (
                              <div key={`${item}-${index}`} className="flex items-start gap-3 rounded-[18px] bg-white/10 px-4 py-3">
                                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white text-[11px] font-bold text-[#3F5EF7]">
                                    {index + 1}
                                  </span>
                                <p className="text-[12px] leading-6 text-white/92">{item}</p>
                              </div>
                            ))}
                          </div>
                        </div>

                        <div className="rounded-[28px] border border-[#DFE6F6] bg-white/86 p-6 shadow-[0_12px_32px_rgba(56,86,174,0.05)]">
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="text-[11px] font-bold tracking-[0.18em] text-[#8F857A]">审阅问题</p>
                              <p className="mt-2 text-[22px] font-semibold tracking-[-0.03em] text-[#4B443E]">本报告回答什么</p>
                            </div>
                            <FileBadge size={18} className="text-[#4B66D8]" />
                          </div>
                          <div className="mt-5 space-y-3">
                            {reportPreview.reviewQuestions.map((item, index) => (
                              <div key={`${item}-${index}`} className="rounded-[18px] bg-[#F2F6FF] px-4 py-4">
                                <p className="text-[11px] font-bold tracking-[0.12em] text-[#4B66D8]">0{index + 1}</p>
                                <p className="mt-1 text-[13px] leading-6 text-[#5A524A]">{item}</p>
                              </div>
                            ))}
                          </div>
                        </div>

                        <div className="rounded-[28px] border border-[#D7E0F2] bg-[linear-gradient(180deg,rgba(250,252,255,0.96)_0%,rgba(239,245,255,0.92)_100%)] p-6 shadow-[0_12px_32px_rgba(56,86,174,0.06)]">
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="text-[11px] font-bold tracking-[0.18em] text-[#8F857A]">交付组成</p>
                              <p className="mt-2 text-[22px] font-semibold tracking-[-0.03em] text-[#4B443E]">建议纳入的模块</p>
                            </div>
                            <Paperclip size={18} className="text-[#4B66D8]" />
                          </div>
                          <div className="mt-4 space-y-3">
                            {reportPreview.deliverables.map((deliverable, index) => (
                              <div key={`${deliverable}-${index}`} className="rounded-[18px] px-4 py-3">
                                <div className="flex items-center gap-3">
                                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#EAF0FF] text-[11px] font-bold text-[#4B66D8]">
                                    {index + 1}
                                  </span>
                                  <p className="text-[13px] font-semibold leading-6 text-[#5A524A]">{deliverable}</p>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="mt-6 flex items-end justify-between text-[12px] text-[#8F867B]">
                      <p>{reportPreview.pageTwoNote}</p>
                      <span className="font-medium tracking-[0.18em] text-[#4B66D8]">02 / 02</span>
                    </div>
                  </div>
                </div>
              </section>
            </div>
            ) : (
              <div className="mx-auto max-w-[760px] pb-6">
                <section className="overflow-hidden rounded-[32px] border border-[#DDE4F3] bg-[#F9FBFF] shadow-[0_24px_70px_rgba(56,86,174,0.10)]">
                  <div className="relative min-h-[520px] px-10 py-10 text-[#3F3A36]">
                    <div
                      className="absolute inset-0"
                      style={{
                        background: 'radial-gradient(circle at 20% 16%, rgba(93, 125, 255, 0.14), transparent 26%), radial-gradient(circle at 85% 85%, rgba(123, 168, 255, 0.12), transparent 20%), linear-gradient(180deg, #F9FBFF 0%, #EEF3FD 100%)',
                      }}
                    />
                    <div className="relative flex h-full flex-col items-start justify-center">
                      <span className="inline-flex rounded-full bg-[#5B7BFE] px-4 py-2 text-[11px] font-bold text-white">
                        模拟报告暂不可用
                      </span>
                      <h3 className="mt-6 text-[38px] font-semibold leading-[1.16] tracking-[-0.04em] text-[#3F3A36]">
                        {reportPreview.emptyStateTitle}
                      </h3>
                      <p className="mt-5 max-w-[560px] text-[16px] leading-8 text-[#6F685F]">
                        {reportPreview.emptyStateDescription}
                      </p>
                      <div className="mt-8 flex flex-wrap items-center gap-3 text-[13px] text-[#5D6781]">
                        <span className="rounded-full bg-white/84 px-4 py-2 shadow-[0_8px_20px_rgba(56,86,174,0.08)]">
                          当前事件线：{reportPreview.reportTitle}
                        </span>
                        <span className="rounded-full bg-white/84 px-4 py-2 shadow-[0_8px_20px_rgba(56,86,174,0.08)]">
                          快照日期：{reportPreview.snapshotAtLabel}
                        </span>
                      </div>
                      <button
                        type="button"
                        className="mt-10 rounded-full bg-[#5B7BFE] px-5 py-2.5 text-[13px] font-bold text-white transition hover:bg-[#3F5EF7]"
                        onClick={() => setViewMode('materials')}
                      >
                        去素材清单补资料
                      </button>
                    </div>
                  </div>
                </section>
              </div>
            )
          ) : (
            <div>
              {(() => {
                const keyCount = draft.activities.filter((a) => isKeyActivity(a)).length;
                const traceCount = draft.activities.length - keyCount;
                return (
                  <div className="flex items-center justify-between">
                    <p className="text-[12px] font-bold text-gray-500">
                      {showSystemTraces ? '全部活动' : '关键活动'}
                    </p>
                    <div className="flex items-center gap-3 text-[11px]">
                      <span className="text-gray-400">{showSystemTraces ? draft.activities.length : keyCount} 条</span>
                      {traceCount > 0 && (
                        <button
                          type="button"
                          className="text-[#5B7BFE] hover:underline"
                          onClick={() => setShowSystemTraces((prev) => !prev)}
                        >
                          {showSystemTraces ? '只看关键活动' : `显示全部（含 ${traceCount} 条系统痕迹）`}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })()}

              <div className="mt-3 space-y-1">
                {draft.activities.filter((a) => showSystemTraces || isKeyActivity(a)).map((activity) => {
                  const activityAtts = attachmentsByActivity.get(activity.id) || [];
                  const imageAtts = activityAtts.filter((a) => isImageAttachment(a));
                  const docAtts = activityAtts.filter((a) => !isImageAttachment(a));
                  const hasAtts = activityAtts.length > 0;
                  const isDocsExpanded = docsExpandedActivities.has(activity.id);
                  const isImagesExpanded = imagesExpandedActivities.has(activity.id);

                  return (
                    <div
                      key={activity.id}
                      className="group rounded-2xl border border-gray-100 bg-white px-4 py-3 transition hover:border-gray-200"
                    >
                      <div className="space-y-1.5">
                        <div>
                          <p className="text-[14px] font-bold text-gray-900">{activity.title}</p>
                          <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px]">
                            <span className="rounded bg-slate-100 px-1.5 py-0.5 font-bold text-slate-500">
                              {SOURCE_TYPE_LABELS[activity.sourceType] || activity.sourceType}
                            </span>
                            <span className="text-gray-400">{formatTs(activity.happenedAt)}</span>
                            {activity.actorName && (
                              <span className="text-gray-400">— {activity.actorName}</span>
                            )}
                          </div>
                        </div>
                        {activity.summary && (
                          <p className="text-[12px] leading-5 text-gray-500 whitespace-pre-wrap">{activity.summary}</p>
                        )}
                        {(() => {
                          const taskId = activity.sourceType === 'task_activity'
                            ? activity.sourceId
                            : (activity.metadata?.taskId as string | undefined);
                          const task = taskId ? taskMap.get(taskId) : undefined;
                          const taskDesc = task?.desc || (task as Record<string, unknown> | undefined)?.description as string | undefined;
                          if (!task || !taskDesc) return null;
                          return (
                            <div className="mt-1 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
                              <p className="text-[11px] font-medium text-slate-500">{task.title}</p>
                              <p className="mt-0.5 text-[11px] leading-4 text-slate-400 whitespace-pre-wrap">{taskDesc}</p>
                            </div>
                          );
                        })()}
                        <div className="flex-1 min-w-0">
                          <div className="mt-2 flex items-center gap-1">
                            <button
                              type="button"
                              title={isDocsExpanded ? '折叠文档' : '展开文档'}
                              disabled={docAtts.length === 0}
                              className={`rounded p-1 transition ${docAtts.length === 0 ? 'text-gray-200 cursor-default' : isDocsExpanded ? 'bg-blue-100 text-[#5B7BFE]' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'}`}
                              onClick={() => {
                                if (docAtts.length === 0) return;
                                setDocsExpandedActivities((prev) => {
                                  const next = new Set(prev);
                                  if (next.has(activity.id)) next.delete(activity.id);
                                  else next.add(activity.id);
                                  return next;
                                });
                              }}
                            >
                              <FileText size={12} />
                            </button>
                            <button
                              type="button"
                              title={isImagesExpanded ? '折叠图片' : '展开图片'}
                              disabled={imageAtts.length === 0}
                              className={`rounded p-1 transition ${imageAtts.length === 0 ? 'text-gray-200 cursor-default' : isImagesExpanded ? 'bg-blue-100 text-[#5B7BFE]' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'}`}
                              onClick={() => {
                                if (imageAtts.length === 0) return;
                                setImagesExpandedActivities((prev) => {
                                  const next = new Set(prev);
                                  if (next.has(activity.id)) next.delete(activity.id);
                                  else next.add(activity.id);
                                  return next;
                                });
                              }}
                            >
                              <Image size={12} />
                            </button>
                            <button
                              type="button"
                              title={hasAtts ? `下载全部附件（${activityAtts.length}个）` : '暂无附件'}
                              disabled={!hasAtts}
                              className={`rounded p-1 transition ${hasAtts ? 'text-gray-400 hover:text-[#5B7BFE] hover:bg-gray-100' : 'text-gray-200 cursor-default'}`}
                              onClick={() => {
                                if (!hasAtts) return;
                                for (const att of activityAtts) {
                                  const link = document.createElement('a');
                                  link.href = `${backendBaseUrl}${att.downloadUrl}`;
                                  link.download = att.title;
                                  link.click();
                                }
                              }}
                            >
                              <Download size={12} />
                            </button>
                            {hasAtts && <span className="ml-0.5 text-[9px] text-gray-300">{activityAtts.length}</span>}
                          </div>

                          {uploadProgressByActivity[activity.id] && (
                            <div className="mt-1 rounded-lg bg-blue-50 px-2 py-1">
                              <div className="flex items-center gap-1.5">
                                {uploadProgressByActivity[activity.id].error ? (
                                  <span className="text-[10px] text-red-600">{uploadProgressByActivity[activity.id].error}</span>
                                ) : (
                                  <>
                                    <div className="h-2 w-2 animate-spin rounded-full border border-blue-300 border-t-[#5B7BFE]" />
                                    <span className="text-[10px] text-blue-700">
                                      上传 {uploadProgressByActivity[activity.id].current}/{uploadProgressByActivity[activity.id].total}：{uploadProgressByActivity[activity.id].fileName}
                                    </span>
                                  </>
                                )}
                              </div>
                            </div>
                          )}

                          {hasAtts && !isDocsExpanded && !isImagesExpanded && (
                            <div className="mt-2 flex flex-wrap gap-1.5">
                              {activityAtts.map((att) => {
                                const badge = fileTypeBadge(att.title);
                                return (
                                  <a
                                    key={att.id}
                                    href={`${backendBaseUrl}${att.downloadUrl}`}
                                    download={att.title}
                                    className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-[10px] text-gray-600 transition hover:border-[#C9D6FF] hover:text-[#5B7BFE]"
                                    title={`${att.title} · ${fileSizeLabel(att.sizeBytes)}`}
                                  >
                                    <span className="rounded px-1 py-0.5 text-[8px] font-bold" style={{ backgroundColor: badge.bg, color: badge.color }}>{badge.label}</span>
                                    {att.title}
                                  </a>
                                );
                              })}
                            </div>
                          )}

                          {isDocsExpanded && docAtts.length > 0 && (
                            <div className="mt-2 space-y-2">
                              {docAtts.map((att) => (
                                <DocContentViewer key={att.id} att={att} backendBaseUrl={backendBaseUrl} />
                              ))}
                            </div>
                          )}

                          {isImagesExpanded && imageAtts.length > 0 && (
                            <div className="mt-2 grid grid-cols-2 gap-2">
                              {imageAtts.map((att) => (
                                <ImageWithOcr key={att.id} att={att} backendBaseUrl={backendBaseUrl} />
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export type { ReportDraft };
~~~

## `src/renderer/components/tasks/HierarchyReportCard.tsx`

- 编码: `utf-8`

~~~tsx
import { useState } from 'react';

import type {
  HierarchyReport,
  ReviewActionCard,
  ReviewActionExecutionResult,
  ReviewDashboardCardTarget,
  ReviewDashboardEvidenceRef,
  WeeklyReviewAnalysis,
} from '../../../shared/types';
import { ReviewMetricGrid } from './ReviewMetricGrid';

type HierarchyReportCardTone = 'slate' | 'emerald' | 'amber';

type HierarchyReportCardProps = {
  report: HierarchyReport;
  title: string;
  subtitle: string;
  tone?: HierarchyReportCardTone;
  analysis?: WeeklyReviewAnalysis | null;
  showAnonymousInsights?: boolean;
  onTriggerAction?: (action: ReviewActionCard, report: HierarchyReport) => Promise<ReviewActionExecutionResult | void> | ReviewActionExecutionResult | void;
  onOpenActionResult?: (result: ReviewActionExecutionResult, action: ReviewActionCard, report: HierarchyReport) => Promise<void> | void;
  onDrillTarget?: (target: ReviewDashboardCardTarget) => Promise<void> | void;
};

const toneClassMap: Record<HierarchyReportCardTone, { header: string; subtitle: string; chip: string; action: string; fact: string }> = {
  slate: {
    header: 'bg-slate-900 text-white',
    subtitle: 'text-white/70',
    chip: 'bg-slate-100 text-slate-700',
    action: 'bg-slate-50 text-slate-700',
    fact: 'bg-slate-50 text-slate-700',
  },
  emerald: {
    header: 'bg-emerald-600 text-white',
    subtitle: 'text-emerald-50',
    chip: 'bg-emerald-50 text-emerald-800',
    action: 'bg-emerald-50/70 text-emerald-900/80',
    fact: 'bg-emerald-50/60 text-emerald-900/80',
  },
  amber: {
    header: 'bg-amber-500 text-white',
    subtitle: 'text-amber-50',
    chip: 'bg-amber-50 text-amber-800',
    action: 'bg-amber-50/80 text-amber-900/80',
    fact: 'bg-amber-50 text-amber-900/80',
  },
};

function readNumber(source: Record<string, unknown>, key: string): number | null {
  const value = source[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function confidenceClass(confidence: string) {
  if (confidence === 'high') return 'bg-emerald-50 text-emerald-700';
  if (confidence === 'medium') return 'bg-amber-50 text-amber-700';
  return 'bg-slate-100 text-slate-500';
}

function confidenceLabel(confidence: string) {
  if (confidence === 'high') return '高置信';
  if (confidence === 'medium') return '中置信';
  return '低置信';
}

function lensLabel(lens: string) {
  if (lens === 'organization') return '组织视角';
  if (lens === 'business') return '业务视角';
  if (lens === 'team') return '团队视角';
  if (lens === 'market') return '市场视角';
  if (lens === 'growth') return '成长视角';
  return '执行视角';
}

function actionTypeLabel(actionType: string) {
  if (actionType === 'meeting') return '会议';
  if (actionType === 'support_request') return '支持请求';
  if (actionType === 'resource_request') return '资源调整';
  if (actionType === 'one_on_one') return '1v1';
  return '任务动作';
}

function actionTypeClass(actionType: string) {
  if (actionType === 'meeting') return 'bg-blue-50 text-[#33449a]';
  if (actionType === 'support_request') return 'bg-amber-50 text-amber-700';
  if (actionType === 'resource_request') return 'bg-rose-50 text-rose-700';
  if (actionType === 'one_on_one') return 'bg-emerald-50 text-emerald-700';
  return 'bg-slate-100 text-slate-600';
}

function severityLabel(severity: string) {
  if (severity === 'high') return '高严重度';
  if (severity === 'medium') return '中严重度';
  return '低严重度';
}

type ExecutiveOverviewCard = {
  key: string;
  title: string;
  subtitle: string;
  items: Array<{
    title: string;
    body: string;
    chips?: string[];
    target?: ReviewDashboardCardTarget | null;
    evidenceRefs?: ReviewDashboardEvidenceRef[];
  }>;
  empty: string;
  className: string;
};

type StructuredLine = {
  title: string;
  body: string;
};

function parseStructuredLine(value: string): StructuredLine | null {
  const normalized = value.trim();
  if (!normalized.includes('｜')) return null;
  const [title, ...rest] = normalized.split('｜');
  const cleanTitle = title.trim();
  const cleanBody = rest.join('｜').trim();
  if (!cleanTitle || !cleanBody) return null;
  return { title: cleanTitle, body: cleanBody };
}

function overviewItemsFromText(values: string[], fallbackChip?: string): Array<{ title: string; body: string; chips?: string[] }> {
  return values.slice(0, 4).map((item) => {
    const parsed = parseStructuredLine(item);
    if (parsed) {
      return {
        title: parsed.title,
        body: parsed.body,
      };
    }
    return {
      title: item,
      body: item,
      chips: fallbackChip ? [fallbackChip] : undefined,
    };
  });
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-[28px] border border-gray-200 bg-white px-5 py-5 shadow-sm">
      <div className="mb-4">
        <h4 className="text-[15px] font-bold text-gray-900">{title}</h4>
        {subtitle ? <p className="mt-1 text-[12px] leading-5 text-gray-500">{subtitle}</p> : null}
      </div>
      {children}
    </section>
  );
}

function buildExecutiveOverviewCards(report: HierarchyReport, analysis?: WeeklyReviewAnalysis | null): ExecutiveOverviewCard[] {
  const trendRiskItems = analysis?.trendSignals?.length
    ? analysis.trendSignals.slice(0, 4).map((item) => ({
      title: item.title,
      body: item.statement,
      chips: [severityLabel(item.severity), item.windowLabel],
      target: item.target,
      evidenceRefs: item.evidenceRefs || [],
    }))
    : [];
  const eventLineItems = analysis?.eventLineSummaries?.length
    ? analysis.eventLineSummaries.slice(0, 4).map((item) => ({
      title: item.title,
      body: item.whatHappenedThisWeek || item.currentState,
      chips: [
        item.projectName || '',
        item.moduleName || item.flowName || '',
        `完整度 ${item.completenessScore}%`,
      ].filter(Boolean),
      target: item.target,
      evidenceRefs: item.evidenceRefs || [],
    }))
    : overviewItemsFromText(report.focusAreas);
  const riskCardItems = analysis?.riskCards?.length
    ? analysis.riskCards.slice(0, 4).map((item) => ({
      title: item.title,
      body: item.statement,
      chips: [
        item.probability === 'high' ? '高概率' : item.probability === 'medium' ? '中概率' : '低概率',
        item.forecastWindow === '1w' ? '未来 1 周' : item.forecastWindow === '2w' ? '未来 2 周' : '未来 3 周',
      ],
      target: item.target,
      evidenceRefs: item.evidenceRefs || [],
    }))
    : overviewItemsFromText(report.supportSignals);
  const riskItems = [...trendRiskItems, ...riskCardItems]
    .filter((item, index, list) => list.findIndex((candidate) => candidate.title === item.title && candidate.body === item.body) === index)
    .slice(0, 4);
  const opportunityItems = analysis?.opportunityCards?.length
    ? analysis.opportunityCards.slice(0, 4).map((item) => ({
      title: item.title,
      body: item.statement,
      chips: [
        item.confidence === 'high' ? '高把握' : item.confidence === 'medium' ? '中把握' : '低把握',
        item.upside,
      ].filter(Boolean),
      target: item.target,
      evidenceRefs: item.evidenceRefs || [],
    }))
    : overviewItemsFromText(report.anonymousInsights);
  const actionItems = report.actions.length > 0
    ? report.actions.slice(0, 4).map((item) => ({
      title: item.title,
      body: typeof item.payload.summary === 'string' ? item.payload.summary : item.title,
      chips: [actionTypeLabel(item.actionType)],
      target: item.target,
      evidenceRefs: item.evidenceRefs || [],
    }))
    : [
      ...overviewItemsFromText(report.suggestedActions.slice(0, 3), '建议动作'),
      ...(analysis?.nextWeekFocus?.slice(0, 1).map((item) => ({ title: '下周关注', body: item, chips: ['下周关注'] })) || []),
    ];

  return [
    {
      key: 'event_lines',
      title: '本周关键事件线',
      subtitle: '先看这一周真正推进了哪几条线。',
      items: eventLineItems,
      empty: '事件线尚在梳理中|任务痕迹积累足够后，事件线会自动归纳到这里',
      className: 'border-blue-100 bg-blue-50/50',
    },
    {
      key: 'risks',
      title: '本周最值得关注的风险',
      subtitle: '优先看未来 1-3 周可能继续放大的问题。',
      items: riskItems,
      empty: '暂无风险信号|当出现延期、阻塞或资源冲突时，风险卡片会自动生成',
      className: 'border-rose-100 bg-rose-50/55',
    },
    {
      key: 'opportunities',
      title: '本周最值得放大的机会',
      subtitle: '不是亮点罗列，而是值得加码的正向势能。',
      items: opportunityItems,
      empty: '暂无机会信号|当出现超预期进展或正向势能时，机会卡片会自动生成',
      className: 'border-emerald-100 bg-emerald-50/45',
    },
    {
      key: 'actions',
      title: '本周建议动作',
      subtitle: '把判断收束成可执行的最小动作。',
      items: actionItems,
      empty: '建议待生成|综合事件线、风险和机会分析后，建议动作会自动归纳',
      className: 'border-amber-100 bg-amber-50/55',
    },
  ];
}

export function HierarchyReportCard({
  report,
  title,
  subtitle,
  tone = 'slate',
  analysis = null,
  showAnonymousInsights = true,
  onTriggerAction,
  onOpenActionResult,
  onDrillTarget,
}: HierarchyReportCardProps) {
  const [runningActionId, setRunningActionId] = useState<string | null>(null);
  const [actionResults, setActionResults] = useState<Record<string, ReviewActionExecutionResult>>({});
  const toneClasses = toneClassMap[tone];
  const sourcePolicy = report.sourcePolicy || {};
  const sampleSize = readNumber(sourcePolicy, 'sampleSize');
  const agentSampleCount = readNumber(sourcePolicy, 'agentSampleCount');
  const simulationMode = sourcePolicy.simulationMode === true;
  const overviewCards = buildExecutiveOverviewCards(report, analysis);
  const focusAreaCards = report.focusAreas
    .map((item) => parseStructuredLine(item))
    .filter((item): item is StructuredLine => Boolean(item));
  const plainFocusAreas = report.focusAreas.filter((item) => !parseStructuredLine(item));
  const evidenceSourceLabels = Array.from(
    new Set([
      '任务痕迹',
      report.scopeType === 'org' ? '组织背景' : report.scopeType === 'team' ? '部门计划' : '个人执行',
      ...(analysis?.dnaModuleTitles || []).map((item) => `参考：${item}`),
      ...(report.scopeType !== 'employee' ? ['项目/业务背景'] : []),
    ]),
  );

  const actionButtonLabel = (actionType: string) => {
    if (actionType === 'meeting') return '发起会议';
    if (actionType === 'support_request') return '发支持请求';
    if (actionType === 'resource_request') return '发资源请求';
    if (actionType === 'one_on_one') return '转成 1v1 任务';
    return '转成任务';
  };

  const handleTriggerAction = async (action: ReviewActionCard) => {
    if (!onTriggerAction || runningActionId) return;
    setRunningActionId(action.id);
    try {
      const result = await onTriggerAction(action, report);
      if (result) {
        setActionResults((prev) => ({
          ...prev,
          [action.id]: result,
        }));
      }
    } finally {
      setRunningActionId(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className={`rounded-3xl border border-gray-200 p-5 shadow-sm ${toneClasses.header}`}>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-[18px] font-bold">{title}</h2>
          {simulationMode ? (
            <span className="rounded-full bg-white/15 px-3 py-1 text-[10px] font-bold tracking-[0.12em] text-white/90">
              模拟视角
            </span>
          ) : null}
        </div>
        <p className={`mt-1 text-[12px] ${toneClasses.subtitle}`}>{subtitle}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {sampleSize ? (
            <span className="rounded-full bg-white/10 px-3 py-1.5 text-[11px] font-bold text-white/90">
              约 {sampleSize} 条复盘样本
            </span>
          ) : null}
          {agentSampleCount && agentSampleCount > 0 ? (
            <span className="rounded-full bg-white/10 px-3 py-1.5 text-[11px] font-bold text-white/90">
              含 {agentSampleCount} 条机器人自动样本
            </span>
          ) : null}
          {evidenceSourceLabels.map((item) => (
            <span key={item} className="rounded-full bg-white/10 px-3 py-1.5 text-[11px] font-bold text-white/90">
              {item}
            </span>
          ))}
        </div>
      </div>

      <Section title="本周全局判断" subtitle="先建立全局认知，再决定要不要往下看详细事实和解释。">
        <div className="grid gap-3 lg:grid-cols-2">
          {overviewCards.map((card) => (
            <div key={card.key} className={`rounded-3xl border px-4 py-4 ${card.className}`}>
              <div>
                <h5 className="text-[14px] font-bold text-gray-900">{card.title}</h5>
                <p className="mt-1 text-[11px] leading-5 text-gray-500">{card.subtitle}</p>
              </div>
              {card.items.length > 0 ? (
                <div className="mt-4 space-y-2">
                  {card.items.map((item) => (
                    <div key={`${card.key}-${item.title}`} className="rounded-2xl bg-white/80 px-3 py-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-[12px] font-bold leading-5 text-gray-900">{item.title}</p>
                        {item.chips?.map((chip) => (
                          <span key={chip} className="rounded-full bg-white px-2 py-1 text-[10px] font-bold text-gray-500">
                            {chip}
                          </span>
                        ))}
                        {item.evidenceRefs && item.evidenceRefs.length > 0 ? (
                          <span className="rounded-full bg-white px-2 py-1 text-[10px] font-bold text-slate-400">
                            {item.evidenceRefs.length} 条证据
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-2 line-clamp-3 text-[12px] leading-6 text-gray-700">{item.body}</p>
                      {item.target && onDrillTarget ? (
                        <div className="mt-3">
                          <button
                            type="button"
                            className="rounded-full border border-gray-200 bg-white px-3 py-1.5 text-[11px] font-bold text-[#33449a] transition hover:border-[#BFD0FF] hover:bg-[#F6F8FF]"
                            onClick={() => void onDrillTarget(item.target!)}
                          >
                            查看证据与下钻
                          </button>
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mt-4 rounded-2xl bg-white/75 px-3 py-3 text-center"><p className="text-[13px] font-bold text-slate-500">{card.empty.split('|')[0]}</p><p className="text-[12px] text-slate-400 mt-1">{card.empty.split('|')[1]}</p></div>
              )}
            </div>
          ))}
        </div>
      </Section>

      <Section title="本周事实" subtitle="先看真实发生了什么，再进入解释和预测。">
        <div className="space-y-4">
          <ReviewMetricGrid metrics={report.summaryMetrics || []} />
          <div className="space-y-2">
            <div className={`rounded-2xl px-4 py-4 text-[13px] leading-6 ${toneClasses.fact}`}>
              <p className="font-bold text-gray-900">{report.headline}</p>
              <p className="mt-2 text-gray-700">{report.summary}</p>
            </div>
            {showAnonymousInsights && report.anonymousInsights.length > 0
              ? report.anonymousInsights.map((item) => (
                <div key={item} className={`rounded-2xl px-4 py-3 text-[13px] leading-6 ${toneClasses.fact}`}>
                  {item}
                </div>
              ))
              : null}
          </div>
        </div>
      </Section>

      <Section title="AI 判断" subtitle="结合组织、部门和项目背景解释这些任务痕迹。">
        <div className="space-y-3">
          {focusAreaCards.length > 0 ? (
            <div className="grid gap-2 lg:grid-cols-2">
              {focusAreaCards.map((item) => (
                <div key={`${item.title}-${item.body}`} className="rounded-2xl bg-slate-50 px-4 py-3">
                  <p className="text-[12px] font-bold text-gray-900">{item.title}</p>
                  <p className="mt-1 text-[12px] leading-6 text-gray-600">{item.body}</p>
                </div>
              ))}
            </div>
          ) : null}
          {plainFocusAreas.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {plainFocusAreas.map((item) => (
                <span key={item} className={`rounded-full px-3 py-2 text-[12px] font-bold ${toneClasses.chip}`}>
                  {item}
                </span>
              ))}
            </div>
          ) : null}
          {report.supportSignals.length > 0 ? (
            <div className="space-y-2">
              {report.supportSignals.map((item) => (
                <div key={item} className="rounded-2xl bg-gray-50 px-4 py-3 text-[13px] leading-6 text-gray-700">
                  {item}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-2xl bg-slate-50 px-4 py-3 text-center"><p className="text-[13px] font-bold text-slate-500">判断线索待积累</p><p className="text-[12px] text-slate-400 mt-1">任务数据和背景信息足够丰富后，AI 会在这里展示解释性判断</p></div>
          )}
        </div>
      </Section>

      <Section title="可能性分析" subtitle="从当前信号里看未来 1-3 周可能出现的风险和机会。">
        {analysis?.hypothesisHighlights.length ? (
          <div className="space-y-3">
            {analysis.hypothesisHighlights.map((item) => (
              <div key={item.id} className="rounded-3xl border border-gray-200 bg-white px-5 py-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[14px] font-bold text-gray-900">{item.title}</span>
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold text-slate-600">{lensLabel(item.lens)}</span>
                  <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${confidenceClass(item.confidence)}`}>{confidenceLabel(item.confidence)}</span>
                </div>
                <p className="mt-3 text-[13px] leading-6 text-gray-700">{item.statement}</p>
                <p className="mt-3 text-[12px] leading-5 text-slate-500">依据：{item.reason}</p>
                {item.assumptionNote ? <p className="mt-2 text-[12px] leading-5 text-amber-700">提示：{item.assumptionNote}</p> : null}
              </div>
            ))}
          </div>
        ) : report.focusAreas.length > 0 ? (
          <div className="space-y-2">
            {report.focusAreas.map((item) => (
              <div key={item} className="rounded-2xl bg-blue-50/70 px-4 py-3 text-[13px] leading-6 text-[#33449a]">
                {item}
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-2xl bg-slate-50 px-4 py-3 text-center"><p className="text-[13px] font-bold text-slate-500">可能性分析待生成</p><p className="text-[12px] text-slate-400 mt-1">积累足够的任务和趋势数据后，风险与机会预测会自动展示</p></div>
        )}
      </Section>

      <Section title="建议动作" subtitle="把总结收敛成个人、部门或机构层面可以执行的动作。">
        {report.actions.length > 0 || report.suggestedActions.length > 0 || analysis?.nextWeekFocus.length ? (
          <div className="space-y-2">
            {report.actions.map((action) => {
              const summary = typeof action.payload.summary === 'string' ? action.payload.summary : '';
              const relatedTaskTitles = Array.isArray(action.payload.relatedTaskTitles)
                ? action.payload.relatedTaskTitles.filter((item): item is string => typeof item === 'string')
                : [];
              const actionResult = actionResults[action.id];
              return (
                <div key={action.id} className="rounded-3xl border border-gray-200 bg-white px-4 py-4 shadow-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${actionTypeClass(action.actionType)}`}>
                      {actionTypeLabel(action.actionType)}
                    </span>
                    <span className="text-[14px] font-bold text-gray-900">{action.title}</span>
                  </div>
                  {summary ? <p className="mt-3 text-[13px] leading-6 text-gray-700">{summary}</p> : null}
                  {relatedTaskTitles.length > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {relatedTaskTitles.map((item) => (
                        <span key={item} className="rounded-full bg-slate-50 px-3 py-1.5 text-[11px] font-bold text-slate-600">
                          {item}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  {onTriggerAction ? (
                    <div className="mt-4 flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        className="rounded-2xl bg-[#5B7BFE] px-4 py-2 text-[12px] font-bold text-white shadow-sm transition hover:bg-[#4c6df0] disabled:cursor-not-allowed disabled:opacity-60"
                        onClick={() => void handleTriggerAction(action)}
                        disabled={Boolean(runningActionId)}
                      >
                        {runningActionId === action.id ? '处理中...' : actionButtonLabel(action.actionType)}
                      </button>
                      {actionResult && onOpenActionResult && actionResult.canOpen ? (
                        <button
                          type="button"
                          className="rounded-2xl border border-gray-200 bg-white px-4 py-2 text-[12px] font-bold text-gray-600 transition hover:border-[#5B7BFE] hover:text-[#33449a]"
                          onClick={() => void onOpenActionResult(actionResult, action, report)}
                        >
                          {actionResult.objectType === 'task'
                            ? '打开任务'
                            : actionResult.objectType === 'support_request'
                              ? '打开请求'
                              : '打开项目'}
                        </button>
                      ) : null}
                    </div>
                  ) : null}
                  {actionResult ? (
                    <div className="mt-3 rounded-2xl bg-emerald-50 px-4 py-3 text-[12px] leading-6 text-emerald-800">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full bg-white/90 px-2.5 py-1 text-[10px] font-bold text-emerald-700">
                          已执行
                        </span>
                        <span className="font-bold">
                          {actionResult.objectType === 'task'
                            ? '已创建任务'
                            : actionResult.objectType === 'meeting'
                              ? '已发起会议草稿'
                              : '已创建支持请求'}
                        </span>
                      </div>
                      <p className="mt-2 text-emerald-900">
                        {actionResult.objectLabel}
                        <span className="ml-2 text-emerald-700/80">#{actionResult.objectId}</span>
                      </p>
                      {actionResult.targetClientName ? (
                        <p className="text-emerald-700/80">关联项目：{actionResult.targetClientName}</p>
                      ) : null}
                      {actionResult.targetEventLineName ? (
                        <p className="text-emerald-700/80">关联事件线：{actionResult.targetEventLineName}</p>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              );
            })}
            {report.suggestedActions.map((item) => (
              <div key={item} className={`rounded-2xl px-4 py-3 text-[13px] leading-6 ${toneClasses.action}`}>
                {item}
              </div>
            ))}
            {analysis?.nextWeekFocus.map((item) => (
              <div key={item} className="rounded-2xl bg-blue-50/70 px-4 py-3 text-[13px] leading-6 text-[#33449a]">
                {item}
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-2xl bg-slate-50 px-4 py-3 text-center"><p className="text-[13px] font-bold text-slate-500">建议待生成</p><p className="text-[12px] text-slate-400 mt-1">综合分析完成后，可执行的建议动作会归纳到这里</p></div>
        )}
      </Section>
    </div>
  );
}
~~~

## `src/renderer/components/tasks/ReviewHistoryPicker.tsx`

- 编码: `utf-8`

~~~tsx
import React from 'react';

import type { ReviewHistoryEntry } from '../../../shared/types';

type ReviewHistoryPickerProps = {
  open: boolean;
  loading: boolean;
  items: ReviewHistoryEntry[];
  activeWeekLabel: string;
  onClose: () => void;
  onSelect: (weekLabel: string) => void;
};

function formatHistoryTimestamp(value: string) {
  if (!value) return '未记录时间';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return `${parsed.getMonth() + 1}月${parsed.getDate()}日 ${String(parsed.getHours()).padStart(2, '0')}:${String(parsed.getMinutes()).padStart(2, '0')}`;
}

export function ReviewHistoryPicker({
  open,
  loading,
  items,
  activeWeekLabel,
  onClose,
  onSelect,
}: ReviewHistoryPickerProps) {
  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="false"
      className="mt-4 rounded-[28px] border border-amber-100 bg-white p-5 shadow-[0_18px_50px_rgba(15,23,42,0.08)]"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h3 className="text-[18px] font-bold text-gray-900">查看历史复盘</h3>
          <p className="mt-1 text-[12px] leading-6 text-gray-500">选择一个历史周次，直接切换到对应的复盘内容。</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="h-9 w-9 shrink-0 rounded-full border border-gray-200 text-gray-400 transition hover:border-gray-300 hover:text-gray-600"
          aria-label="关闭历史复盘"
        >
          ×
        </button>
      </div>

      <div className="mt-5 max-h-[420px] space-y-3 overflow-y-auto pr-1">
        {loading && <div className="rounded-2xl bg-gray-50 px-4 py-6 text-center text-[13px] text-gray-500">正在读取历史复盘…</div>}
        {!loading && items.length === 0 && <div className="rounded-2xl bg-gray-50 px-4 py-6 text-center text-[13px] text-gray-500">还没有可查看的历史复盘。</div>}
        {!loading &&
          items.map((item) => {
            const isActive = item.weekLabel === activeWeekLabel;
            return (
              <button
                key={item.weekLabel}
                type="button"
                onClick={() => onSelect(item.weekLabel)}
                className={`w-full rounded-[24px] border px-4 py-4 text-left transition ${
                  isActive
                    ? 'border-[#5B7BFE]/30 bg-[#5B7BFE]/6 shadow-sm'
                    : 'border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50'
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-[15px] font-bold text-gray-900">{item.weekLabel}</div>
                    <div className="mt-1 text-[12px] text-gray-500">最近提交：{formatHistoryTimestamp(item.submittedAt)}</div>
                  </div>
                  {isActive && (
                    <span className="rounded-full bg-[#5B7BFE] px-2.5 py-1 text-[10px] font-bold text-white">
                      当前查看
                    </span>
                  )}
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <span className="rounded-full bg-gray-100 px-2.5 py-1 text-[11px] font-bold text-gray-500">
                    工作复盘 {item.workItemCount} 条
                  </span>
                  <span className="rounded-full bg-rose-50 px-2.5 py-1 text-[11px] font-bold text-rose-500">
                    成长复盘 {item.personalItemCount} 条
                  </span>
                </div>
              </button>
            );
          })}
      </div>
    </div>
  );
}
~~~

## `src/renderer/components/tasks/ReviewMetricGrid.tsx`

- 编码: `utf-8`

~~~tsx
import type { ReviewMetricCard } from '../../../shared/types';

type ReviewMetricGridProps = {
  metrics: ReviewMetricCard[];
};

function toneClasses(tone: ReviewMetricCard['tone']) {
  if (tone === 'positive') return 'border-emerald-100 bg-emerald-50/70 text-emerald-900';
  if (tone === 'neutral') return 'border-slate-200 bg-slate-50 text-slate-800';
  if (tone === 'warning') return 'border-amber-100 bg-amber-50 text-amber-900';
  return 'border-rose-100 bg-rose-50 text-rose-900';
}

export function ReviewMetricGrid({ metrics }: ReviewMetricGridProps) {
  if (!metrics.length) return null;

  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric) => (
        <div key={metric.key} className={`rounded-3xl border px-4 py-4 ${toneClasses(metric.tone)}`}>
          <p className="text-[12px] font-bold opacity-80">{metric.label}</p>
          <div className="mt-3 flex items-end justify-between gap-3">
            <p className="text-[26px] font-bold leading-none">{metric.valueText}</p>
            <span className="rounded-full bg-white/70 px-2.5 py-1 text-[10px] font-bold">
              {metric.denominator > 0 ? `${metric.numerator}/${metric.denominator}` : '待补录'}
            </span>
          </div>
          <p className="mt-3 text-[12px] leading-5 opacity-80">{metric.description}</p>
        </div>
      ))}
    </div>
  );
}
~~~

## `src/renderer/components/tasks/TaskCalendarView.tsx`

- 编码: `utf-8`

~~~tsx
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Pencil,
  Plus,
  Search,
  MoveVertical,
} from 'lucide-react';

import type { Task } from '../../../shared/types';
import { formatMonthTitle } from '../../../shared/calendar';
import { getChinaCalendarMarkers, type ChinaCalendarMarker } from '../../../shared/china-calendar';
import {
  assignTimedTaskLanes,
  buildTaskDayTimedSegment,
  formatTaskMinuteOfDay as formatMinuteOfDay,
  formatTaskTimelineLabel,
  normalizeTaskTimeInput,
  resolveTaskDateTimeRange,
  splitTaskDueDateTime,
  taskDateForCalendar as resolveTaskCalendarDate,
  taskOverlapsCalendarWindow,
} from '../../lib/taskTimeline';

type CalendarDisplayMode = 'month' | 'week';

type TaskCalendarViewProps = {
  tasks: Task[];
  clientColorById?: Record<string, string>;
  currentUserId?: string | null;
  calendarDisplayMode: CalendarDisplayMode;
  onSetCalendarDisplayMode: (mode: CalendarDisplayMode) => void;
  calendarDate: Date;
  selectedDate: Date;
  onSelectDate: (date: Date) => void;
  onShiftMonth: (delta: number) => void;
  onAlignCalendarDate: (date: Date) => void;
  onGoToToday: () => void;
  onOpenTaskEditor: (task?: Task, dueDate?: string, options?: { durationMinutes?: number }) => void;
  onCalendarNotice?: (kind: 'info' | 'error', message: string) => void;
  onToggleTaskStatus: (taskId: string, nextDone?: boolean) => Promise<void>;
  onRescheduleTask: (
    task: Task,
    dueDate: string,
    options?: { preserveCalendarViewport?: boolean },
  ) => Promise<void>;
  onUpdateTaskDuration: (task: Task, durationMinutes: number) => Promise<void>;
  onApproveTaskReview: (taskId: string) => Promise<void>;
  onReturnTaskReview: (taskId: string) => Promise<void>;
  isTaskOverdue: (task: Task, today?: Date) => boolean;
  showCollaborativeTasks: boolean;
  onToggleCollaborativeTasks: () => void;
};

const sourceTypeLabels: Record<string, string> = {
  manual: '手动',
  meeting: '会议',
  goal: '目标',
  topic_candidate: '资讯',
  knowledge_chunk: '知识片段',
  knowledge_document: '知识文档',
  chat: '聊天',
};

const DAY_TIMELINE_SLOT_MINUTES = 15;
const DAY_TIMELINE_SLOT_HEIGHT = 14;
const DAY_TIMELINE_DEFAULT_DURATION_MINUTES = 60;
const DAY_TIMELINE_DEFAULT_START_MINUTE = 8 * 60;
const DAY_MINUTES = 24 * 60;
const WEEK_MAX_VISIBLE_COLUMNS = 2;
const DEFAULT_UNLINKED_TASK_COLOR = '#5B7BFE';

type WeekCreateSelection = {
  dayKey: number;
  dayDate: Date;
  startMinute: number;
  endMinute: number;
};

type TimedWeekTask = {
  task: Task;
  dayIndex: number;
  dayDate: Date;
  startMinute: number;
  endMinute: number;
  durationMinutes: number;
  timeLabel: string;
  lane: number;
  laneCount: number;
  clusterId: number;
};

type WeekTaskDisplayItem =
  | {
      kind: 'task';
      taskItem: TimedWeekTask;
      column: number;
      columnCount: number;
    }
  | {
      kind: 'aggregate';
      key: string;
      hiddenItems: TimedWeekTask[];
      startMinute: number;
      endMinute: number;
      column: number;
      columnCount: number;
      summary: string;
    };

function formatDateInputValue(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function combineDateAndTime(date: Date, minuteOfDay: number) {
  return `${formatDateInputValue(date)}T${formatMinuteOfDay(minuteOfDay)}`;
}

function hasTaskExplicitTime(task: Pick<Task, 'startDate' | 'dueDate'>) {
  const startParts = splitTaskDueDateTime(task.startDate);
  const dueParts = splitTaskDueDateTime(task.dueDate);
  return Boolean(normalizeTaskTimeInput(startParts.time) || normalizeTaskTimeInput(dueParts.time));
}

function minuteOfDayFromClientPosition(column: HTMLDivElement, clientY: number) {
  const rect = column.getBoundingClientRect();
  const clampedOffsetY = Math.max(0, Math.min(rect.height - 1, clientY - rect.top));
  const slotCount = (24 * 60) / DAY_TIMELINE_SLOT_MINUTES;
  const slotIndex = Math.max(
    0,
    Math.min(slotCount - 1, Math.floor(clampedOffsetY / DAY_TIMELINE_SLOT_HEIGHT)),
  );
  return slotIndex * DAY_TIMELINE_SLOT_MINUTES;
}

function buildSelectionRange(anchorMinute: number, currentMinute: number): { startMinute: number; endMinute: number } {
  if (currentMinute >= anchorMinute) {
    return {
      startMinute: anchorMinute,
      endMinute: Math.min(currentMinute + DAY_TIMELINE_SLOT_MINUTES, 24 * 60),
    };
  }
  return {
    startMinute: currentMinute,
    endMinute: Math.min(anchorMinute + DAY_TIMELINE_SLOT_MINUTES, 24 * 60),
  };
}

function isSameDay(left: Date, right: Date) {
  return left.getFullYear() === right.getFullYear()
    && left.getMonth() === right.getMonth()
    && left.getDate() === right.getDate();
}

function addDays(baseDate: Date, days: number) {
  return new Date(baseDate.getFullYear(), baseDate.getMonth(), baseDate.getDate() + days);
}

function startOfDayValue(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function startOfWeek(baseDate: Date) {
  const dayIndex = (baseDate.getDay() + 6) % 7;
  return addDays(baseDate, -dayIndex);
}

function isDateWithinRange(date: Date, startDate: Date, endDate: Date) {
  const time = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  return time >= startDate.getTime() && time <= endDate.getTime();
}

function formatWeekRangeTitle(startDate: Date, endDate: Date) {
  const sameMonth = startDate.getMonth() === endDate.getMonth() && startDate.getFullYear() === endDate.getFullYear();
  if (sameMonth) {
    return `${startDate.getFullYear()}年 ${startDate.getMonth() + 1}月 · ${startDate.getDate()}-${endDate.getDate()}日`;
  }
  return `${startDate.getFullYear()}年 ${startDate.getMonth() + 1}月${startDate.getDate()}日 - ${endDate.getMonth() + 1}月${endDate.getDate()}日`;
}

function sourceLabel(sourceType: string) {
  return sourceTypeLabels[sourceType] || sourceType || '任务';
}

function controlLevelLabel(task: Task) {
  const level = task.orgContext?.controlLevel;
  if (level === 'leader_control') return '负责人控制';
  if (level === 'department_control') return '部门控制';
  if (level === 'organization_control') return '机构控制';
  return '';
}

function taskOrgSummary(task: Task) {
  const parts: string[] = [];
  const control = controlLevelLabel(task);
  if (task.orgContext?.needsReview) parts.push('待复核');
  if (control) parts.push(control);
  if (task.orgContext?.isCrossDepartment) parts.push('跨部门');
  return parts.join(' · ');
}

function isTransportItineraryTask(task: Task) {
  const text = `${task.title || ''}\n${task.desc || ''}`.trim();
  if (!text) return false;
  return /(飞[\u4e00-\u9fff]{1,8}|飞去[\u4e00-\u9fff]{1,8}|飞往[\u4e00-\u9fff]{1,8}|航班|机票|火车去[\u4e00-\u9fff]{1,8}|高铁去[\u4e00-\u9fff]{1,8}|动车去[\u4e00-\u9fff]{1,8}|坐火车去[\u4e00-\u9fff]{1,8}|坐高铁去[\u4e00-\u9fff]{1,8}|乘火车去[\u4e00-\u9fff]{1,8}|乘高铁去[\u4e00-\u9fff]{1,8})/.test(text);
}

function calendarTaskAccentColor(task: Task, clientColorById?: Record<string, string>) {
  if (isTransportItineraryTask(task)) return '#16A34A';
  const normalizedClientId = (task.clientId || '').trim();
  if (!normalizedClientId) return DEFAULT_UNLINKED_TASK_COLOR;
  const clientColor = (clientColorById?.[normalizedClientId] || '').trim();
  if (clientColor) return clientColor;
  return DEFAULT_UNLINKED_TASK_COLOR;
}

function calendarChipStyle(task: Task, clientColorById?: Record<string, string>) {
  if (task.status === 'done') {
    return {
      color: '#94A3B8',
      backgroundColor: '#F8FAFC',
      borderColor: '#E2E8F0',
    };
  }
  const accentColor = calendarTaskAccentColor(task, clientColorById);
  return {
    color: accentColor,
    backgroundColor: `${accentColor}14`,
    borderColor: `${accentColor}22`,
  };
}

function calendarMarkerClassName(marker: ChinaCalendarMarker) {
  if (marker.kind === 'festival') return 'bg-rose-50 text-rose-600 border-rose-100';
  if (marker.kind === 'offday') return 'bg-orange-50 text-orange-700 border-orange-100';
  return 'bg-slate-100 text-slate-600 border-slate-200';
}

function sortTasksForCalendar(items: Task[]) {
  const statusRank: Record<Task['status'], number> = {
    inbox: 0,
    doing: 1,
    todo: 2,
    done: 3,
    rejected: 4,
  };
  const priorityRank: Record<Task['priority'], number> = {
    high: 0,
    normal: 1,
    low: 2,
  };
  return [...items].sort((left, right) => {
    const leftRange = resolveTaskDateTimeRange(left);
    const rightRange = resolveTaskDateTimeRange(right);
    if (leftRange.startDateTime.getTime() !== rightRange.startDateTime.getTime()) {
      return leftRange.startDateTime.getTime() - rightRange.startDateTime.getTime();
    }
    if (leftRange.hasExplicitTime !== rightRange.hasExplicitTime) {
      return leftRange.hasExplicitTime ? -1 : 1;
    }
    const leftDone = left.status === 'done';
    const rightDone = right.status === 'done';
    if (leftDone !== rightDone) return leftDone ? 1 : -1;

    const statusDelta = statusRank[left.status] - statusRank[right.status];
    if (statusDelta !== 0) return statusDelta;

    const priorityDelta = priorityRank[left.priority] - priorityRank[right.priority];
    if (priorityDelta !== 0) return priorityDelta;

    return new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime();
  });
}

function buildWeekTaskDisplayItems(items: TimedWeekTask[]) {
  const clusters = new Map<number, TimedWeekTask[]>();
  items.forEach((item) => {
    const existing = clusters.get(item.clusterId) || [];
    existing.push(item);
    clusters.set(item.clusterId, existing);
  });

  const displayItems: WeekTaskDisplayItem[] = [];
  [...clusters.entries()]
    .sort((left, right) => {
      const leftStart = Math.min(...left[1].map((item) => item.startMinute));
      const rightStart = Math.min(...right[1].map((item) => item.startMinute));
      return leftStart - rightStart;
    })
    .forEach(([clusterId, clusterItems]) => {
      const sortedClusterItems = [...clusterItems].sort((left, right) => {
        if (left.startMinute !== right.startMinute) return left.startMinute - right.startMinute;
        if (left.endMinute !== right.endMinute) return left.endMinute - right.endMinute;
        return left.lane - right.lane;
      });
      const hasOverflow = sortedClusterItems.some((item) => item.laneCount > WEEK_MAX_VISIBLE_COLUMNS);
      if (!hasOverflow) {
        sortedClusterItems.forEach((taskItem) => {
          displayItems.push({
            kind: 'task',
            taskItem,
            column: Math.min(taskItem.lane, WEEK_MAX_VISIBLE_COLUMNS - 1),
            columnCount: Math.min(taskItem.laneCount, WEEK_MAX_VISIBLE_COLUMNS),
          });
        });
        return;
      }

      sortedClusterItems
        .filter((taskItem) => taskItem.lane === 0)
        .forEach((taskItem) => {
          displayItems.push({
            kind: 'task',
            taskItem,
            column: 0,
            columnCount: WEEK_MAX_VISIBLE_COLUMNS,
          });
        });

      const hiddenItems = sortedClusterItems.filter((taskItem) => taskItem.lane >= 1);
      if (hiddenItems.length > 0) {
        const startMinute = Math.min(...hiddenItems.map((item) => item.startMinute));
        const endMinute = Math.max(...hiddenItems.map((item) => item.endMinute));
        const hiddenTitles = hiddenItems.map((item) => item.task.title).filter(Boolean);
        displayItems.push({
          kind: 'aggregate',
          key: `aggregate-${clusterId}`,
          hiddenItems,
          startMinute,
          endMinute,
          column: 1,
          columnCount: WEEK_MAX_VISIBLE_COLUMNS,
          summary: hiddenTitles.slice(0, 4).join('、'),
        });
      }
    });

  return displayItems;
}

export function TaskCalendarView({
  tasks,
  clientColorById,
  currentUserId: _currentUserId,
  calendarDisplayMode,
  onSetCalendarDisplayMode,
  calendarDate,
  selectedDate,
  onSelectDate,
  onShiftMonth,
  onAlignCalendarDate,
  onGoToToday,
  onOpenTaskEditor,
  onCalendarNotice,
  onToggleTaskStatus,
  onRescheduleTask,
  onUpdateTaskDuration,
  onApproveTaskReview: _onApproveTaskReview,
  onReturnTaskReview: _onReturnTaskReview,
  isTaskOverdue,
  showCollaborativeTasks,
  onToggleCollaborativeTasks,
}: TaskCalendarViewProps) {
  const [isJumpPickerOpen, setIsJumpPickerOpen] = useState(false);
  const [draggingTaskId, setDraggingTaskId] = useState<string | null>(null);
  const [dragTargetDay, setDragTargetDay] = useState<number | null>(null);
  const [dragTargetMinute, setDragTargetMinute] = useState<number | null>(null);
  const [expandedCalendarDays, setExpandedCalendarDays] = useState<Set<string>>(new Set());
  const dragDropHandledRef = useRef(false);
  const [resizingTaskId, setResizingTaskId] = useState<string | null>(null);
  const [resizePreviewMinutes, setResizePreviewMinutes] = useState<number | null>(null);
  const [weekCreateSelection, setWeekCreateSelection] = useState<WeekCreateSelection | null>(null);
  const [visibleWeekPageIndex, setVisibleWeekPageIndex] = useState(1);
  const [isWeekPaging, setIsWeekPaging] = useState(false);
  const resizePreviewRef = useRef<number | null>(null);
  const resizeDraftRef = useRef<{ taskId: string; startY: number; startMinute: number; baseDuration: number } | null>(null);
  const weekCreateDraftRef = useRef<{
    dayKey: number;
    dayDate: Date;
    anchorMinute: number;
    column: HTMLDivElement;
  } | null>(null);
  const weekCreateSelectionRef = useRef<WeekCreateSelection | null>(null);
  const weekCreateCleanupRef = useRef<(() => void) | null>(null);
  const weekTimelineScrollRef = useRef<HTMLDivElement | null>(null);
  const weekPagerRef = useRef<HTMLDivElement | null>(null);
  const weekPagerIdleTimerRef = useRef<number | null>(null);
  const weekPagerVerticalSyncRef = useRef(false);
  const weekPagerGestureDeadlineRef = useRef(0);
  const today = useMemo(() => new Date(), []);
  const taskDateForCalendar = resolveTaskCalendarDate;
  const visibleTasks = useMemo(
    () => tasks.filter((task) => task.status !== 'rejected'),
    [tasks],
  );
  const activeMonthDate = useMemo(() => new Date(calendarDate.getFullYear(), calendarDate.getMonth(), 1), [calendarDate]);

  const monthTasksByDateKey = useMemo(() => {
    const mapping = new Map<string, Task[]>();
    visibleTasks.forEach((task) => {
      const range = resolveTaskDateTimeRange(task);
      for (
        let cursor = startOfDayValue(range.startDateTime);
        cursor.getTime() < range.endDateTime.getTime();
        cursor = addDays(cursor, 1)
      ) {
        const date = cursor;
        const key = formatDateInputValue(date);
        const existing = mapping.get(key) || [];
        existing.push(task);
        mapping.set(key, existing);
      }
    });
    mapping.forEach((dayTasks, key) => {
      mapping.set(key, sortTasksForCalendar(dayTasks));
    });
    return mapping;
  }, [visibleTasks]);

  const tasksByDay = useMemo(() => {
    const mapping = new Map<number, Task[]>();
    const daysInMonth = new Date(activeMonthDate.getFullYear(), activeMonthDate.getMonth() + 1, 0).getDate();
    for (let day = 1; day <= daysInMonth; day += 1) {
      const date = new Date(activeMonthDate.getFullYear(), activeMonthDate.getMonth(), day);
      const dayTasks = monthTasksByDateKey.get(formatDateInputValue(date)) || [];
      if (dayTasks.length > 0) mapping.set(day, dayTasks);
    }
    mapping.forEach((dayTasks, day) => {
      mapping.set(day, sortTasksForCalendar(dayTasks));
    });
    return mapping;
  }, [activeMonthDate, monthTasksByDateKey]);

  const monthTasks = useMemo(() => {
    const monthStart = new Date(activeMonthDate.getFullYear(), activeMonthDate.getMonth(), 1);
    const monthEndExclusive = new Date(activeMonthDate.getFullYear(), activeMonthDate.getMonth() + 1, 1);
    return sortTasksForCalendar(
      visibleTasks.filter((task) => taskOverlapsCalendarWindow(task, monthStart, monthEndExclusive)),
    );
  }, [activeMonthDate, visibleTasks]);

  const monthTimelineWeeks = useMemo(() => {
    const firstRenderedMonth = new Date(calendarDate.getFullYear(), calendarDate.getMonth(), 1);
    const rangeStart = startOfWeek(firstRenderedMonth);
    const lastRenderedDay = new Date(firstRenderedMonth.getFullYear(), firstRenderedMonth.getMonth() + 1, 0);
    const rangeEnd = addDays(lastRenderedDay, 6 - ((lastRenderedDay.getDay() + 6) % 7));
    const weeks: Array<{
      key: string;
      days: Array<{
        date: Date;
        dayTasks: Task[];
      }>;
    }> = [];
    for (let cursor = rangeStart; cursor.getTime() <= rangeEnd.getTime(); cursor = addDays(cursor, 7)) {
      const weekStart = cursor;
      weeks.push({
        key: formatDateInputValue(weekStart),
        days: Array.from({ length: 7 }, (_, index) => {
          const date = addDays(weekStart, index);
          return {
            date,
            dayTasks: monthTasksByDateKey.get(formatDateInputValue(date)) || [],
          };
        }),
      });
    }
    return weeks;
  }, [calendarDate, monthTasksByDateKey]);

  const weekStartDate = useMemo(() => startOfWeek(selectedDate), [selectedDate]);
  const weekPages = useMemo(() => {
    return [-7, 0, 7].map((offsetDays) => {
      const startDate = addDays(weekStartDate, offsetDays);
      const days = Array.from({ length: 7 }, (_, index) => addDays(startDate, index));
      const endDate = days[6];
      const tasks = sortTasksForCalendar(
        visibleTasks.filter((task) => taskOverlapsCalendarWindow(task, startDate, addDays(endDate, 1))),
      );
      const timedTasks = days.flatMap((day, dayIndex) => {
        const items = tasks
          .map((task) => {
            const segment = buildTaskDayTimedSegment(task, day);
            if (!segment) return null;
            return {
              task,
              dayIndex,
              dayDate: day,
              ...segment,
            };
          })
          .filter((item): item is { task: Task; dayIndex: number; dayDate: Date; startMinute: number; endMinute: number; durationMinutes: number; timeLabel: string } => Boolean(item));
        return assignTimedTaskLanes(items) as TimedWeekTask[];
      });
      return {
        key: `${startDate.toISOString()}-${offsetDays}`,
        offsetDays,
        startDate,
        endDate,
        days,
        title: formatWeekRangeTitle(startDate, endDate),
        tasks,
        timedTasks,
      };
    });
  }, [visibleTasks, weekStartDate]);
  const currentWeekPage = weekPages[1];
  const visibleWeekPage = weekPages[visibleWeekPageIndex] ?? currentWeekPage;
  const weekStartKey = weekStartDate.getTime();
  const weekDays = visibleWeekPage.days;
  const weekEndDate = visibleWeekPage.endDate;
  const weekTasks = visibleWeekPage.tasks;
  const weekTimedTasks = visibleWeekPage.timedTasks;
  const weekDisplayItemsByDay = useMemo(() => {
    const mapping = new Map<number, WeekTaskDisplayItem[]>();
    visibleWeekPage.days.forEach((_, dayIndex) => {
      const items = visibleWeekPage.timedTasks.filter((item) => item.dayIndex === dayIndex) as TimedWeekTask[];
      mapping.set(dayIndex, buildWeekTaskDisplayItems(items));
    });
    return mapping;
  }, [visibleWeekPage.days, visibleWeekPage.timedTasks]);
  const draggedTask = useMemo(
    () => (calendarDisplayMode === 'week' ? weekTasks : visibleTasks).find((task) => task.id === draggingTaskId) || null,
    [calendarDisplayMode, draggingTaskId, visibleTasks, weekTasks],
  );

  const draggedDurationMinutes = useMemo(() => {
    if (!draggedTask) return DAY_TIMELINE_DEFAULT_DURATION_MINUTES;
    const timedMatch = weekTimedTasks.find((item) => item.task.id === draggedTask.id);
    if (timedMatch) return timedMatch.durationMinutes;
    return Math.max(DAY_TIMELINE_SLOT_MINUTES, draggedTask.durationMinutes ?? DAY_TIMELINE_DEFAULT_DURATION_MINUTES);
  }, [draggedTask, weekTimedTasks]);

  useEffect(() => {
    if (calendarDisplayMode !== 'week') return;
    const nextScrollTop = Math.max(0, (DAY_TIMELINE_DEFAULT_START_MINUTE / DAY_TIMELINE_SLOT_MINUTES) * DAY_TIMELINE_SLOT_HEIGHT - 12);
    const pager = weekPagerRef.current;
    if (!pager) return;
    pager.querySelectorAll<HTMLElement>('[data-week-scroll="true"]').forEach((node) => {
      node.scrollTop = nextScrollTop;
    });
  }, [calendarDisplayMode, selectedDate]);

  useEffect(() => {
    if (!resizingTaskId || !resizeDraftRef.current) return;

    const handleMouseMove = (event: MouseEvent) => {
      const draft = resizeDraftRef.current;
      if (!draft) return;
      const deltaY = event.clientY - draft.startY;
      const deltaSlots = Math.round(deltaY / DAY_TIMELINE_SLOT_HEIGHT);
      const maxDuration = Math.max(DAY_TIMELINE_SLOT_MINUTES, 24 * 60 - draft.startMinute);
      const nextDuration = Math.max(
        DAY_TIMELINE_SLOT_MINUTES,
        Math.min(maxDuration, draft.baseDuration + deltaSlots * DAY_TIMELINE_SLOT_MINUTES),
      );
      resizePreviewRef.current = nextDuration;
      setResizePreviewMinutes(nextDuration);
      document.body.style.cursor = 'ns-resize';
      document.body.style.userSelect = 'none';
    };

    const handleMouseUp = () => {
      const draft = resizeDraftRef.current;
      const task = weekTimedTasks.find((item) => item.task.id === draft?.taskId)?.task;
      const nextDuration = resizePreviewRef.current ?? draft?.baseDuration ?? null;
      resizeDraftRef.current = null;
      resizePreviewRef.current = null;
      setResizingTaskId(null);
      setResizePreviewMinutes(null);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      if (task && nextDuration && draft && nextDuration !== draft.baseDuration) {
        void onUpdateTaskDuration(task, nextDuration);
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [onUpdateTaskDuration, resizingTaskId, weekTimedTasks]);

  const cleanupWeekCreateInteraction = useCallback(() => {
    weekCreateCleanupRef.current?.();
    weekCreateCleanupRef.current = null;
    weekCreateDraftRef.current = null;
    weekCreateSelectionRef.current = null;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  }, []);

  useEffect(() => {
    return () => {
      cleanupWeekCreateInteraction();
    };
  }, [cleanupWeekCreateInteraction]);

  const timelineSlotMinutes = useMemo(
    () => Array.from({ length: (24 * 60) / DAY_TIMELINE_SLOT_MINUTES }, (_, index) => index * DAY_TIMELINE_SLOT_MINUTES),
    [],
  );
  const hourLineMinutes = useMemo(
    () => timelineSlotMinutes.filter((minute) => minute % 60 === 0),
    [timelineSlotMinutes],
  );

  const monthStats = useMemo(() => {
    return {
      dayCount: tasksByDay.size,
      total: monthTasks.length,
      open: monthTasks.filter((task) => task.status !== 'done').length,
      done: monthTasks.filter((task) => task.status === 'done').length,
      overdue: monthTasks.filter((task) => isTaskOverdue(task, today)).length,
      highPriority: monthTasks.filter((task) => task.status !== 'done' && task.priority === 'high').length,
    };
  }, [isTaskOverdue, monthTasks, tasksByDay.size, today]);

  const weekStats = useMemo(() => {
    return {
      total: weekTasks.length,
      open: weekTasks.filter((task) => task.status !== 'done').length,
      done: weekTasks.filter((task) => task.status === 'done').length,
      overdue: weekTasks.filter((task) => isTaskOverdue(task, today)).length,
      highPriority: weekTasks.filter((task) => task.status !== 'done' && task.priority === 'high').length,
    };
  }, [isTaskOverdue, today, weekTasks]);
  const visibleWeekStats = useMemo(() => {
    return {
      total: visibleWeekPage.tasks.length,
      open: visibleWeekPage.tasks.filter((task) => task.status !== 'done').length,
      done: visibleWeekPage.tasks.filter((task) => task.status === 'done').length,
      overdue: visibleWeekPage.tasks.filter((task) => isTaskOverdue(task, today)).length,
      highPriority: visibleWeekPage.tasks.filter((task) => task.status !== 'done' && task.priority === 'high').length,
    };
  }, [isTaskOverdue, today, visibleWeekPage]);

  const handleDateJump = (value: string) => {
    const nextDate = new Date(value);
    if (Number.isNaN(nextDate.getTime())) return;
    onSelectDate(nextDate);
    onAlignCalendarDate(nextDate);
    setIsJumpPickerOpen(false);
  };

  const handleShiftPeriod = (delta: number) => {
    if (calendarDisplayMode === 'week') {
      const nextDate = addDays(selectedDate, delta * 7);
      onSelectDate(nextDate);
      onAlignCalendarDate(nextDate);
      return;
    }
    onShiftMonth(delta);
  };

  const handleDaySelect = (date: Date) => {
    if (calendarDisplayMode === 'week') {
      onSelectDate(date);
      return;
    }
    onSelectDate(date);
    if (date.getFullYear() !== calendarDate.getFullYear() || date.getMonth() !== calendarDate.getMonth()) {
      onAlignCalendarDate(date);
    }
  };

  const handleTaskDrop = async (task: Task, cellDate: Date) => {
    const nextDueDate = formatDateInputValue(cellDate);
    const currentTaskDate = taskDateForCalendar(task);
    if (
      currentTaskDate.getFullYear() === cellDate.getFullYear()
      && currentTaskDate.getMonth() === cellDate.getMonth()
      && currentTaskDate.getDate() === cellDate.getDate()
    ) {
      return;
    }
    await onRescheduleTask(task, nextDueDate);
    onSelectDate(cellDate);
  };

  const handleTimelineTaskDrop = async (task: Task, minuteOfDay: number) => {
    const nextDueDate = combineDateAndTime(selectedDate, minuteOfDay);
    setDragTargetMinute(null);
    setDraggingTaskId(null);
    await onRescheduleTask(task, nextDueDate);
  };

  const handleWeekTimelineTaskDrop = async (task: Task, dayDate: Date, minuteOfDay: number) => {
    const nextDueDate = combineDateAndTime(dayDate, minuteOfDay);
    setDragTargetMinute(null);
    setDragTargetDay(null);
    setDraggingTaskId(null);
    onSelectDate(dayDate);
    await onRescheduleTask(task, nextDueDate, { preserveCalendarViewport: true });
  };

  const resolveDraggedTaskId = (event: React.DragEvent) => {
    const transferTaskId = event.dataTransfer.getData('text/plain').trim();
    return transferTaskId || draggingTaskId || null;
  };

  const handleStartWeekTaskResize = (
    taskId: string,
    startMinute: number,
    baseDuration: number,
    event: React.MouseEvent,
  ) => {
    event.preventDefault();
    event.stopPropagation();
    resizeDraftRef.current = {
      taskId,
      startY: event.clientY,
      startMinute,
      baseDuration,
    };
    resizePreviewRef.current = baseDuration;
    setResizingTaskId(taskId);
    setResizePreviewMinutes(baseDuration);
  };

  const handleStartWeekCreateSelection = (
    day: Date,
    column: HTMLDivElement,
    event: React.MouseEvent<HTMLDivElement>,
  ) => {
    if (draggingTaskId || resizingTaskId) return;
    event.preventDefault();
    event.stopPropagation();
    const anchorMinute = minuteOfDayFromClientPosition(column, event.clientY);
    const dayKey = day.getTime();
    cleanupWeekCreateInteraction();
    const initialSelection = {
      dayKey,
      dayDate: day,
      startMinute: anchorMinute,
      endMinute: Math.min(anchorMinute + DAY_TIMELINE_SLOT_MINUTES, 24 * 60),
    };
    weekCreateDraftRef.current = {
      dayKey,
      dayDate: day,
      anchorMinute,
      column,
    };
    weekCreateSelectionRef.current = initialSelection;
    setWeekCreateSelection(initialSelection);
    document.body.style.cursor = 'ns-resize';
    document.body.style.userSelect = 'none';

    const updateSelectionFromPointer = (clientY: number) => {
      const draft = weekCreateDraftRef.current;
      if (!draft) return;
      const currentMinute = minuteOfDayFromClientPosition(draft.column, clientY);
      const nextRange = buildSelectionRange(draft.anchorMinute, currentMinute);
      const nextSelection = {
        dayKey: draft.dayKey,
        dayDate: draft.dayDate,
        startMinute: nextRange.startMinute,
        endMinute: nextRange.endMinute,
      };
      weekCreateSelectionRef.current = nextSelection;
      setWeekCreateSelection(nextSelection);
    };

    const handleWindowMouseMove = (moveEvent: MouseEvent) => {
      updateSelectionFromPointer(moveEvent.clientY);
    };

    const handleWindowMouseUp = () => {
      const draft = weekCreateDraftRef.current;
      const selection = weekCreateSelectionRef.current;
      cleanupWeekCreateInteraction();
      setWeekCreateSelection(null);
      if (!draft || !selection) return;
      const durationMinutes = Math.max(DAY_TIMELINE_SLOT_MINUTES, selection.endMinute - selection.startMinute);
      const dueDate = combineDateAndTime(draft.dayDate, selection.startMinute);
      window.requestAnimationFrame(() => {
        onSelectDate(draft.dayDate);
        onOpenTaskEditor(undefined, dueDate, { durationMinutes });
      });
    };

    window.addEventListener('mousemove', handleWindowMouseMove);
    window.addEventListener('mouseup', handleWindowMouseUp);
    weekCreateCleanupRef.current = () => {
      window.removeEventListener('mousemove', handleWindowMouseMove);
      window.removeEventListener('mouseup', handleWindowMouseUp);
    };
  };

  const handleGoToToday = () => {
    onGoToToday();
  };

  const handleCreateTaskFromWeekSlot = useCallback(
    (day: Date, startMinute: number) => {
      if (draggingTaskId || resizingTaskId) return;
      const durationMinutes = DAY_TIMELINE_DEFAULT_DURATION_MINUTES;
      const endMinute = Math.min(startMinute + durationMinutes, DAY_MINUTES);
      const hasOverlap = visibleWeekPage.timedTasks.some(
        (item) =>
          item.dayDate.getTime() === day.getTime()
          && item.startMinute < endMinute
          && item.endMinute > startMinute,
      );
      if (hasOverlap) {
        onCalendarNotice?.('info', '这个时间段已经有任务了，请点空闲时间再新建，或先调整现有任务。');
        return;
      }
      window.requestAnimationFrame(() => {
        onSelectDate(day);
        onOpenTaskEditor(undefined, combineDateAndTime(day, startMinute), { durationMinutes });
      });
    },
    [draggingTaskId, onCalendarNotice, onOpenTaskEditor, onSelectDate, resizingTaskId, visibleWeekPage.timedTasks],
  );

  const centerWeekPager = (behavior: ScrollBehavior = 'auto') => {
    const pager = weekPagerRef.current;
    if (!pager) return;
    const pageWidth = pager.clientWidth;
    if (!pageWidth) return;
    pager.scrollTo({ left: pageWidth, behavior });
  };

  useEffect(() => {
    if (calendarDisplayMode !== 'week') return;
    let frame = 0;
    frame = window.requestAnimationFrame(() => {
      setVisibleWeekPageIndex(1);
      centerWeekPager('auto');
    });
    return () => {
      window.cancelAnimationFrame(frame);
      if (weekPagerIdleTimerRef.current) {
        window.clearTimeout(weekPagerIdleTimerRef.current);
        weekPagerIdleTimerRef.current = null;
      }
    };
  }, [calendarDisplayMode, weekStartKey]);

  useEffect(() => {
    if (calendarDisplayMode !== 'week' || isWeekPaging) return;
    if (Date.now() < weekPagerGestureDeadlineRef.current) return;
    const pager = weekPagerRef.current;
    if (!pager || pager.clientWidth <= 0) return;
    const centerOffset = Math.abs(pager.scrollLeft - pager.clientWidth);
    if (centerOffset < 2) return;
    let frame = 0;
    frame = window.requestAnimationFrame(() => {
      setVisibleWeekPageIndex(1);
      centerWeekPager('auto');
    });
    return () => {
      window.cancelAnimationFrame(frame);
    };
  }, [calendarDisplayMode, isWeekPaging, weekTasks, weekTimedTasks]);

  const handleWeekVerticalScroll = (event: React.UIEvent<HTMLDivElement>) => {
    if (weekPagerVerticalSyncRef.current) return;
    const source = event.currentTarget;
    const pager = weekPagerRef.current;
    if (!pager) return;
    weekPagerVerticalSyncRef.current = true;
    pager.querySelectorAll<HTMLElement>('[data-week-scroll="true"]').forEach((node) => {
      if (node !== source) node.scrollTop = source.scrollTop;
    });
    window.requestAnimationFrame(() => {
      weekPagerVerticalSyncRef.current = false;
    });
  };

  const finalizeWeekPagerScroll = () => {
    const pager = weekPagerRef.current;
    if (!pager) return;
    const pageWidth = pager.clientWidth;
    if (!pageWidth) return;
    weekPagerGestureDeadlineRef.current = 0;
    const pageIndex = Math.round(pager.scrollLeft / pageWidth);
    if (pageIndex === 0) {
      onSelectDate(addDays(selectedDate, -7));
      return;
    }
    if (pageIndex === 2) {
      onSelectDate(addDays(selectedDate, 7));
      return;
    }
    centerWeekPager('smooth');
  };

  const handleWeekPagerScroll = () => {
    const pager = weekPagerRef.current;
    if (!pager || pager.clientWidth <= 0) return;
    const now = Date.now();
    const isUserGesture = now < weekPagerGestureDeadlineRef.current;
    const centerOffset = Math.abs(pager.scrollLeft - pager.clientWidth);
    if (!isUserGesture) {
      if (centerOffset < 6) return;
      return;
    }
    weekPagerGestureDeadlineRef.current = now + 180;
    setIsWeekPaging(true);
    const pageIndex = Math.max(0, Math.min(2, Math.round(pager.scrollLeft / pager.clientWidth)));
    setVisibleWeekPageIndex(pageIndex);
    if (weekPagerIdleTimerRef.current) {
      window.clearTimeout(weekPagerIdleTimerRef.current);
    }
    weekPagerIdleTimerRef.current = window.setTimeout(() => {
      setIsWeekPaging(false);
      finalizeWeekPagerScroll();
    }, 120);
  };

  const handleWeekScrollWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    if (Math.abs(event.deltaX) <= Math.abs(event.deltaY) || Math.abs(event.deltaX) < 6) return;
    const pager = weekPagerRef.current;
    if (!pager) return;
    weekPagerGestureDeadlineRef.current = Date.now() + 280;
    pager.scrollLeft += event.deltaX;
    event.preventDefault();
  };

  const handleWeekTaskSelect = (event?: React.MouseEvent) => {
    event?.preventDefault();
    event?.stopPropagation();
  };

  const periodStats = calendarDisplayMode === 'week' ? visibleWeekStats : monthStats;
  const periodTitle = calendarDisplayMode === 'week' ? visibleWeekPage.title : formatMonthTitle(activeMonthDate);

  return (
    <div className="w-full min-w-0 grid grid-cols-1 gap-6 items-start transition-all xl:grid-cols-[minmax(0,1fr)]">
      <div className="min-w-0 w-full bg-white border border-gray-200 rounded-[32px] shadow-sm overflow-hidden">
        <div className="flex flex-col gap-3 px-5 lg:px-6 py-4 border-b border-gray-100">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-3">
                <div className="inline-flex rounded-2xl border border-gray-200 bg-slate-50 p-1">
                  {(['month', 'week'] as CalendarDisplayMode[]).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      className={`rounded-[12px] px-3 py-1.5 text-[12px] font-bold transition-colors ${calendarDisplayMode === mode ? 'bg-white text-[#5B7BFE] shadow-sm' : 'text-gray-500 hover:text-gray-800'}`}
                      onClick={() => onSetCalendarDisplayMode(mode)}
                    >
                      {mode === 'month' ? '月' : '周'}
                    </button>
                  ))}
                </div>
                <h2 className={`text-[18px] lg:text-[22px] font-bold text-gray-900 transition-all duration-200 ${isWeekPaging && calendarDisplayMode === 'week' ? 'opacity-90 translate-x-[1px]' : 'opacity-100 translate-x-0'}`}>{periodTitle}</h2>
              </div>
              <div className={`flex flex-wrap gap-1.5 text-[10px] font-semibold transition-opacity duration-200 ${isWeekPaging && calendarDisplayMode === 'week' ? 'opacity-85' : 'opacity-100'}`}>
                <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-slate-600">{calendarDisplayMode === 'week' ? '本周任务' : '本月任务'} {periodStats.total} 条</span>
                <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-emerald-600">完成 {periodStats.done}</span>
                <span className="rounded-full bg-amber-50 px-2.5 py-0.5 text-amber-700">待推进 {periodStats.open}</span>
                <span className="rounded-full bg-rose-50 px-2.5 py-0.5 text-rose-600">逾期 {periodStats.overdue}</span>
                <span className="rounded-full bg-violet-50 px-2.5 py-0.5 text-violet-600">高优先级 {periodStats.highPriority}</span>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-end gap-2 self-start lg:self-auto">
              <button
                type="button"
                role="switch"
                aria-checked={showCollaborativeTasks}
                aria-label={showCollaborativeTasks ? '隐藏个人任务' : '显示全部任务'}
                onClick={onToggleCollaborativeTasks}
                className="group relative flex items-center overflow-visible"
              >
                <span className="pointer-events-none absolute left-0 top-1/2 -translate-x-[calc(100%+8px)] -translate-y-1/2 text-[11px] font-medium text-gray-400 whitespace-nowrap opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-visible:opacity-100 group-active:opacity-100">
                  {showCollaborativeTasks ? '隐藏个人任务' : '显示全部任务'}
                </span>
                <span
                  className={`relative inline-flex h-6 w-10 items-center rounded-full transition-colors duration-200 ${
                    showCollaborativeTasks ? 'bg-[#5B7BFE]' : 'bg-gray-300'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200 ${
                      showCollaborativeTasks ? 'translate-x-5' : 'translate-x-1'
                    }`}
                  />
                </span>
              </button>
              <div className="relative flex items-center gap-2">
              <button
                type="button"
                className="h-9 w-9 rounded-xl border border-gray-200 text-gray-500 hover:text-[#5B7BFE] hover:border-blue-100 transition-colors"
                onClick={() => handleShiftPeriod(-1)}
              >
                <ChevronLeft size={16} className="mx-auto" />
              </button>
              <button
                type="button"
                className="h-9 px-3 rounded-xl border border-gray-200 bg-white text-[12px] font-bold text-gray-700 whitespace-nowrap hover:text-[#5B7BFE] hover:border-blue-100 transition-colors"
                onClick={handleGoToToday}
              >
                今天
              </button>
              <button
                type="button"
                aria-label="跳转日期"
                className={`h-9 w-9 rounded-xl border text-[12px] font-bold transition-colors ${
                  isJumpPickerOpen
                    ? 'border-blue-200 bg-blue-50 text-[#5B7BFE]'
                    : 'border-gray-200 bg-white text-gray-700 hover:text-[#5B7BFE] hover:border-blue-100'
                }`}
                onClick={() => setIsJumpPickerOpen((prev) => !prev)}
              >
                <Search size={14} className="mx-auto" />
              </button>
              <button
                type="button"
                className="h-9 w-9 rounded-xl border border-gray-200 text-gray-500 hover:text-[#5B7BFE] hover:border-blue-100 transition-colors"
                onClick={() => handleShiftPeriod(1)}
              >
                <ChevronRight size={16} className="mx-auto" />
              </button>

              {isJumpPickerOpen && (
                <div className="absolute top-11 right-0 z-20 w-[280px] rounded-[24px] border border-gray-200 bg-white p-4 shadow-[0_20px_50px_rgba(15,23,42,0.12)]">
                  <p className="text-[12px] font-bold text-gray-500 mb-3">跳到任意日期</p>
                  <input
                    type="date"
                    value={formatDateInputValue(selectedDate)}
                    onChange={(event) => handleDateJump(event.target.value)}
                    className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none"
                  />
                  <button
                    type="button"
                    className="mt-3 w-full rounded-2xl bg-[#5B7BFE] text-white text-[13px] font-bold h-11 shadow-[0_6px_18px_rgba(91,123,254,0.28)]"
                    onClick={() => {
                      handleGoToToday();
                      setIsJumpPickerOpen(false);
                    }}
                  >
                    回到今天
                  </button>
                </div>
              )}
              </div>
            </div>
          </div>

        </div>

        {calendarDisplayMode === 'month' ? (
          <>
            <div className="grid grid-cols-7 text-center text-[13px] font-bold text-gray-400 px-5 lg:px-6 pt-4 pb-3">
              {['周一', '周二', '周三', '周四', '周五', '周六', '周日'].map((day) => (
                <div key={day}>{day}</div>
              ))}
            </div>

            <div>
              {monthTimelineWeeks.map((week) => (
                <div key={week.key} className="grid w-full grid-cols-7">
                  {week.days.map(({ date: cellDate, dayTasks }) => {
                    const isActiveSelection = isSameDay(cellDate, selectedDate);
                    const isToday = isSameDay(cellDate, today);
                    const isMonthAnchor = cellDate.getDate() === 1;
                    const overflowCount = Math.max(dayTasks.length - 4, 0);
                    const chinaCalendarMarkers = getChinaCalendarMarkers(cellDate);
                    return (
                      <div
                        key={formatDateInputValue(cellDate)}
                        role="button"
                        tabIndex={0}
                        onClick={() => {
                          handleDaySelect(cellDate);
                        }}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault();
                            handleDaySelect(cellDate);
                          }
                        }}
                        onDragOver={(event) => {
                          const draggedTaskId = resolveDraggedTaskId(event);
                          if (!draggedTaskId) return;
                          event.preventDefault();
                          if (dragTargetDay !== cellDate.getTime()) {
                            setDragTargetDay(cellDate.getTime());
                          }
                        }}
                        onDragLeave={() => {
                          if (dragTargetDay === cellDate.getTime()) {
                            setDragTargetDay(null);
                          }
                        }}
                        onDrop={(event) => {
                          const draggedTaskId = resolveDraggedTaskId(event);
                          if (!draggedTaskId) return;
                          event.preventDefault();
                          const droppedTask = visibleTasks.find((item) => item.id === draggedTaskId);
                          dragDropHandledRef.current = true;
                          setDragTargetDay(null);
                          setDraggingTaskId(null);
                          if (!droppedTask) return;
                          void handleTaskDrop(droppedTask, cellDate);
                        }}
                        data-calendar-date={formatDateInputValue(cellDate)}
                        className={`relative min-h-[146px] rounded-none border-r border-b border-gray-100 bg-transparent p-2.5 text-left align-top outline-none transition-colors focus:outline-none focus-visible:outline-none cursor-pointer hover:bg-slate-50 ${
                          isActiveSelection ? 'bg-blue-50/40' : ''
                        } ${
                          dragTargetDay === cellDate.getTime() ? 'bg-blue-100 ring-2 ring-inset ring-[#5B7BFE]/40' : ''
                        }`}
                      >
                        <div className="relative z-10 flex h-full flex-col">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <div className={`h-7 min-w-7 rounded-full flex items-center justify-center px-1 text-[13px] font-bold ${
                                isToday ? 'bg-rose-500 text-white' : isActiveSelection ? 'bg-[#5B7BFE] text-white' : 'text-gray-600 bg-white'
                              }`}>
                                {cellDate.getDate()}
                              </div>
                              {isMonthAnchor && (
                                <span className="text-[11px] font-semibold tracking-[0.08em] text-gray-400">
                                  {cellDate.getMonth() + 1}月
                                </span>
                              )}
                            </div>
                            {chinaCalendarMarkers.length > 0 && (
                              <div className="flex flex-wrap justify-end gap-1 max-w-[60%]">
                                {chinaCalendarMarkers.slice(0, 2).map((marker) => (
                                  <span
                                    key={`${formatDateInputValue(cellDate)}-${marker.kind}-${marker.label}`}
                                    className={`rounded-full border px-1.5 py-0.5 text-[10px] font-semibold leading-none ${calendarMarkerClassName(marker)}`}
                                  >
                                    {marker.label}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>

                          <div className="mt-2.5 flex min-h-0 flex-1 flex-col gap-1">
                            {dayTasks.slice(0, expandedCalendarDays.has(formatDateInputValue(cellDate)) ? dayTasks.length : 4).map((task) => {
                              const timedSegment = buildTaskDayTimedSegment(task, cellDate);
                              const timePrefix = timedSegment && hasTaskExplicitTime(task)
                                ? `${formatMinuteOfDay(timedSegment.startMinute)} `
                                : '';
                              return (
                                <div
                                  key={task.id}
                                  data-no-month-range-drag="true"
                                  draggable
                                  onMouseDown={(event) => {
                                    event.stopPropagation();
                                  }}
                                  onDragStart={(event) => {
                                    event.stopPropagation();
                                    event.dataTransfer.effectAllowed = 'move';
                                    event.dataTransfer.setData('text/plain', task.id);
                                    dragDropHandledRef.current = false;
                                    setDraggingTaskId(task.id);
                                  }}
                                  onDragEnd={() => {
                                    if (!dragDropHandledRef.current) {
                                      setDraggingTaskId(null);
                                      setDragTargetDay(null);
                                    }
                                    dragDropHandledRef.current = false;
                                  }}
                                  className={`group relative block max-w-full rounded-lg border px-2 py-1 text-[11px] font-semibold text-left leading-4 cursor-grab active:cursor-grabbing ${
                                    task.status === 'done' ? '' : 'shadow-[0_1px_2px_rgba(15,23,42,0.04)]'
                                  } ${draggingTaskId === task.id ? 'opacity-50' : ''}`}
                                  style={calendarChipStyle(task, clientColorById)}
                                  title={`${timePrefix}${task.title}${taskOrgSummary(task) ? ` · ${taskOrgSummary(task)}` : ''}`}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    handleDaySelect(cellDate);
                                  }}
                                >
                                  <button
                                    type="button"
                                    data-no-month-range-drag="true"
                                    className={`absolute left-1.5 top-1/2 z-10 flex h-3.5 w-3.5 -translate-y-1/2 items-center justify-center rounded-[4px] border transition ${
                                      task.status === 'done'
                                        ? 'border-[#CBD5E1] bg-[#CBD5E1] text-white'
                                        : 'border-current bg-white/85 hover:bg-white'
                                    }`}
                                    onMouseDown={(event) => {
                                      event.stopPropagation();
                                    }}
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      void onToggleTaskStatus(task.id);
                                    }}
                                    title={task.status === 'done' ? '取消完成' : '标记完成'}
                                    aria-label={task.status === 'done' ? `取消完成 ${task.title}` : `完成 ${task.title}`}
                                  >
                                    {task.status === 'done' ? <Check size={10} strokeWidth={3} /> : null}
                                  </button>
                                  <button
                                    type="button"
                                    data-no-month-range-drag="true"
                                    className="absolute right-1.5 top-1/2 z-10 flex h-3.5 w-3.5 -translate-y-1/2 items-center justify-center rounded-[4px] border border-current bg-white/85 opacity-0 transition group-hover:opacity-100 hover:bg-white"
                                    onMouseDown={(event) => {
                                      event.stopPropagation();
                                    }}
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      onOpenTaskEditor(task);
                                    }}
                                    title={`编辑 ${task.title}`}
                                    aria-label={`编辑 ${task.title}`}
                                  >
                                    <Pencil size={9} strokeWidth={2.5} />
                                  </button>
                                  <span className="block overflow-hidden whitespace-nowrap pl-5 pr-1">{timePrefix}{task.title}</span>
                                </div>
                              );
                            })}
                            {overflowCount > 0 && !expandedCalendarDays.has(formatDateInputValue(cellDate)) && (
                              <button
                                type="button"
                                data-no-month-range-drag="true"
                                className="rounded-lg bg-slate-100 px-2 py-1 text-[11px] font-bold text-slate-500 text-left hover:bg-slate-200 transition-colors cursor-pointer"
                                onMouseDown={(event) => {
                                  event.stopPropagation();
                                }}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  setExpandedCalendarDays((prev) => { const next = new Set(prev); next.add(formatDateInputValue(cellDate)); return next; });
                                }}
                              >
                                + {overflowCount} 条更多
                              </button>
                            )}
                            {expandedCalendarDays.has(formatDateInputValue(cellDate)) && dayTasks.length > 4 && (
                              <button
                                type="button"
                                data-no-month-range-drag="true"
                                className="rounded-lg bg-slate-100 px-2 py-1 text-[11px] font-bold text-slate-500 text-left hover:bg-slate-200 transition-colors cursor-pointer"
                                onMouseDown={(event) => {
                                  event.stopPropagation();
                                }}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  setExpandedCalendarDays((prev) => { const next = new Set(prev); next.delete(formatDateInputValue(cellDate)); return next; });
                                }}
                              >
                                收起
                              </button>
                            )}
                            <button
                              type="button"
                              aria-label={`${cellDate.getDate()}日新建任务`}
                              className="group/add min-h-[18px] flex-1 rounded-lg bg-transparent hover:bg-blue-50/50 transition-colors flex items-center justify-center"
                              onMouseDown={(event) => {
                                event.stopPropagation();
                              }}
                              onClick={(event) => {
                                event.stopPropagation();
                                onOpenTaskEditor(undefined, formatDateInputValue(cellDate));
                              }}
                            >
                              <span className="text-[18px] text-blue-300 opacity-0 group-hover/add:opacity-100 transition-opacity font-light">+</span>
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="border-t border-gray-100">
            <div
              ref={weekPagerRef}
              className="overflow-x-auto overscroll-x-contain snap-x snap-proximity"
              onScroll={handleWeekPagerScroll}
            >
              <div className="flex min-w-full">
                {weekPages.map((page) => (
                  <div
                    key={page.key}
                    className={`min-w-full snap-center transition-opacity duration-200 ${
                      isWeekPaging
                        ? page === visibleWeekPage
                          ? 'opacity-100'
                          : 'opacity-75'
                        : 'opacity-100'
                    }`}
                    onWheel={handleWeekScrollWheel}
                  >
                    <div className="grid grid-cols-[56px_repeat(7,minmax(0,1fr))] border-b border-gray-100 bg-white">
                      <div />
                      {page.days.map((day) => {
                        const isActive = isSameDay(day, selectedDate);
                        const isToday = isSameDay(day, today);
                        const chinaCalendarMarkers = getChinaCalendarMarkers(day);
                        return (
                          <button
                            key={day.toISOString()}
                            type="button"
                            className={`border-l border-gray-100 px-2 py-3 text-center transition-colors ${isActive ? 'bg-blue-50/60' : 'hover:bg-slate-50'}`}
                            onClick={() => handleDaySelect(day)}
                          >
                            <p className="text-[11px] font-semibold text-gray-400">{day.toLocaleDateString('zh-CN', { weekday: 'short' })}</p>
                            <div className="mt-2 flex items-center justify-center">
                              <span className={`flex h-8 min-w-8 items-center justify-center rounded-full px-2 text-[13px] font-bold ${isToday ? 'bg-rose-500 text-white' : isActive ? 'bg-[#5B7BFE] text-white' : 'text-gray-700 bg-white'}`}>
                                {day.getDate()}
                              </span>
                            </div>
                            {chinaCalendarMarkers.length > 0 && (
                              <div className="mt-2 flex flex-wrap items-center justify-center gap-1">
                                {chinaCalendarMarkers.slice(0, 2).map((marker) => (
                                  <span
                                    key={`${day.toISOString()}-${marker.kind}-${marker.label}`}
                                    className={`rounded-full border px-1.5 py-0.5 text-[10px] font-semibold leading-none ${calendarMarkerClassName(marker)}`}
                                  >
                                    {marker.label}
                                  </span>
                                ))}
                              </div>
                            )}
                          </button>
                        );
                      })}
                    </div>

                    <div
                      className="max-h-[860px] overflow-y-auto"
                      data-week-scroll="true"
                      onScroll={handleWeekVerticalScroll}
                    >
                      <div className="grid grid-cols-[56px_repeat(7,minmax(0,1fr))] bg-white">
                        <div className="border-r border-gray-100">
                          {timelineSlotMinutes.map((minute) => {
                            const isHourLine = minute % 60 === 0;
                            return (
                              <div
                                key={`${page.key}-time-${minute}`}
                                className={`pr-2 text-right border-t ${isHourLine ? 'border-gray-200' : 'border-transparent'}`}
                                style={{ height: `${DAY_TIMELINE_SLOT_HEIGHT}px` }}
                              >
                                {isHourLine ? <span className="relative -top-2 text-[10px] font-semibold text-gray-400">{formatMinuteOfDay(minute)}</span> : null}
                              </div>
                            );
                          })}
                        </div>
                        {page.days.map((day, dayIndex) => (
                          <div
                            key={`${page.key}-column-${day.toISOString()}`}
                            className="relative border-r last:border-r-0 border-gray-100"
                            style={{ height: `${timelineSlotMinutes.length * DAY_TIMELINE_SLOT_HEIGHT}px` }}
                            data-week-day-key={day.getTime()}
                          >
                            {hourLineMinutes.map((minute) => (
                              <div
                                key={`${page.key}-hour-line-${day.toISOString()}-${minute}`}
                                className="pointer-events-none absolute left-0 right-0 border-t border-gray-200"
                                style={{ top: `${(minute / DAY_TIMELINE_SLOT_MINUTES) * DAY_TIMELINE_SLOT_HEIGHT}px` }}
                              />
                            ))}
                            {timelineSlotMinutes.map((minute) => (
                              <div
                                key={`${page.key}-${day.toISOString()}-${minute}`}
                                className={`group/slot relative cursor-pointer transition-colors ${dragTargetDay === day.getTime() && dragTargetMinute === minute ? 'bg-blue-50/70' : 'bg-transparent hover:bg-blue-50/40'}`}
                                style={{ height: `${DAY_TIMELINE_SLOT_HEIGHT}px` }}
                                onClick={() => {
                                  handleCreateTaskFromWeekSlot(day, minute);
                                }}
                                onDragOver={(event) => {
                                  const draggedTaskId = resolveDraggedTaskId(event);
                                  if (!draggedTaskId) return;
                                  event.preventDefault();
                                  if (dragTargetDay !== day.getTime()) setDragTargetDay(day.getTime());
                                  if (dragTargetMinute !== minute) setDragTargetMinute(minute);
                                }}
                                onDragLeave={() => {
                                  if (dragTargetDay === day.getTime() && dragTargetMinute === minute) {
                                    setDragTargetMinute(null);
                                  }
                                }}
                                onDrop={(event) => {
                                  const draggedTaskId = resolveDraggedTaskId(event);
                                  if (!draggedTaskId) return;
                                  event.preventDefault();
                                  const droppedTask = page.tasks.find((task) => task.id === draggedTaskId) || visibleTasks.find((task) => task.id === draggedTaskId);
                                  if (!droppedTask) {
                                    setDragTargetMinute(null);
                                    setDragTargetDay(null);
                                    setDraggingTaskId(null);
                                    return;
                                  }
                                  void handleWeekTimelineTaskDrop(droppedTask, day, minute);
                                }}
                                title={`${formatDateInputValue(day)} ${formatMinuteOfDay(minute)} 新建任务`}
                              >
                                <span className="pointer-events-none absolute inset-x-1 top-1/2 flex -translate-y-1/2 items-center justify-center opacity-0 transition-opacity group-hover/slot:opacity-100">
                                  <span className="flex h-4 w-4 items-center justify-center rounded-full bg-white/95 text-[#5B7BFE] shadow-sm ring-1 ring-[#5B7BFE]/15">
                                    <Plus size={11} strokeWidth={2.5} />
                                  </span>
                                </span>
                              </div>
                            ))}
                            {draggedTask && dragTargetDay === day.getTime() && dragTargetMinute !== null && (
                              <div
                                className="pointer-events-none absolute left-2 right-2 z-[1] rounded-2xl border border-dashed border-[#5B7BFE] bg-blue-50 shadow-[0_8px_24px_rgba(91,123,254,0.14)]"
                                style={{
                                  top: `${(dragTargetMinute / DAY_TIMELINE_SLOT_MINUTES) * DAY_TIMELINE_SLOT_HEIGHT + 2}px`,
                                  minHeight: `${Math.max(40, (draggedDurationMinutes / DAY_TIMELINE_SLOT_MINUTES) * DAY_TIMELINE_SLOT_HEIGHT - 4)}px`,
                                }}
                              >
                                <div className="flex h-full items-start justify-between gap-2 px-3 py-2 text-[#5B7BFE]">
                                  <span className="min-w-0 flex-1 text-[12px] font-bold leading-5 line-clamp-2">{draggedTask.title}</span>
                                  <span className="shrink-0 text-[10px] font-semibold">{`${formatMinuteOfDay(dragTargetMinute)}-${formatMinuteOfDay(Math.min(dragTargetMinute + draggedDurationMinutes, 24 * 60))}`}</span>
                                </div>
                              </div>
                            )}
                            {(weekDisplayItemsByDay.get(dayIndex) || []).map((displayItem) => {
                              const horizontalInset = 8;
                              const width = `calc((100% - ${horizontalInset * 2}px) / ${displayItem.columnCount})`;
                              const left = `calc(${horizontalInset}px + (${displayItem.column} * ((100% - ${horizontalInset * 2}px) / ${displayItem.columnCount})))`;

                              if (displayItem.kind === 'aggregate') {
                                const top = (displayItem.startMinute / DAY_TIMELINE_SLOT_MINUTES) * DAY_TIMELINE_SLOT_HEIGHT;
                                const height = Math.max(40, ((displayItem.endMinute - displayItem.startMinute) / DAY_TIMELINE_SLOT_MINUTES) * DAY_TIMELINE_SLOT_HEIGHT - 4);
                                const aggregateTitle = displayItem.summary
                                  ? `还有 ${displayItem.hiddenItems.length} 条重叠任务：${displayItem.summary}`
                                  : `还有 ${displayItem.hiddenItems.length} 条重叠任务`;
                                return (
                                  <button
                                    key={displayItem.key}
                                    type="button"
                                    className="group absolute rounded-2xl border border-dashed border-[#93C5FD] bg-[#EFF6FF] px-3 py-2 text-left text-[#1D4ED8] shadow-sm transition hover:bg-[#DBEAFE]"
                                    style={{
                                      top: `${top + 2}px`,
                                      left,
                                      width,
                                      minHeight: `${height}px`,
                                      zIndex: 1,
                                    }}
                                    onMouseDown={(event) => {
                                      event.stopPropagation();
                                    }}
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      onCalendarNotice?.('info', aggregateTitle);
                                    }}
                                    title={aggregateTitle}
                                    aria-label={aggregateTitle}
                                  >
                                    <div className="flex h-full min-h-full flex-col justify-center gap-1">
                                      <span className="text-[11px] font-bold">+{displayItem.hiddenItems.length}</span>
                                      <span className="line-clamp-2 text-[10px] font-medium leading-4 opacity-80">
                                        {displayItem.summary || '更多重叠任务'}
                                      </span>
                                    </div>
                                  </button>
                                );
                              }

                              const { task, startMinute, durationMinutes } = displayItem.taskItem;
                              const effectiveDuration = resizingTaskId === task.id && resizePreviewMinutes ? resizePreviewMinutes : durationMinutes;
                              const effectiveEndMinute = Math.min(startMinute + effectiveDuration, 24 * 60);
                              const effectiveTimeLabel = `${formatMinuteOfDay(startMinute)}-${formatMinuteOfDay(effectiveEndMinute)}`;
                              const top = (startMinute / DAY_TIMELINE_SLOT_MINUTES) * DAY_TIMELINE_SLOT_HEIGHT;
                              const height = Math.max(40, ((effectiveEndMinute - startMinute) / DAY_TIMELINE_SLOT_MINUTES) * DAY_TIMELINE_SLOT_HEIGHT - 4);
                              const chipStyle = calendarChipStyle(task, clientColorById);
                              const isResizing = resizingTaskId === task.id;
                              return (
                                <div
                                  key={task.id}
                                  role="button"
                                  tabIndex={0}
                                  draggable={!isResizing}
                                  onDragStart={(event) => {
                                    event.stopPropagation();
                                    event.dataTransfer.effectAllowed = 'move';
                                    event.dataTransfer.setData('text/plain', task.id);
                                    dragDropHandledRef.current = false;
                                    setDraggingTaskId(task.id);
                                  }}
                                  onDragEnd={() => {
                                    if (!dragDropHandledRef.current) {
                                      setDraggingTaskId(null);
                                      setDragTargetDay(null);
                                      setDragTargetMinute(null);
                                    }
                                    dragDropHandledRef.current = false;
                                  }}
                                  className={`group absolute rounded-2xl border px-2.5 py-2 pb-5 text-left shadow-sm transition cursor-grab active:cursor-grabbing ${isResizing ? 'cursor-ns-resize ring-2 ring-[#5B7BFE]/40' : draggingTaskId === task.id ? 'opacity-50' : ''}`}
                                  style={{
                                    top: `${top + 2}px`,
                                    left,
                                    width,
                                    minHeight: `${height}px`,
                                    color: chipStyle.color,
                                    backgroundColor: task.status === 'done' ? '#F8FAFC' : '#FFFFFF',
                                    borderColor: chipStyle.borderColor,
                                    zIndex: draggingTaskId === task.id || isResizing ? 2 : 1,
                                  }}
                                  onMouseDown={(event) => {
                                    event.stopPropagation();
                                  }}
                                  onClick={(event) => handleWeekTaskSelect(event)}
                                  title={`${effectiveTimeLabel} ${task.title}`}
                                  aria-label={`${effectiveTimeLabel} ${task.title}`}
                                >
                                  <div className="pr-10">
                                    <div className="text-[10px] font-semibold opacity-80">{effectiveTimeLabel}</div>
                                    <div className="mt-1 text-[12px] font-bold leading-4 line-clamp-2 break-words">{task.title}</div>
                                  </div>
                                  <div className="absolute right-2 top-2 flex items-center gap-1 opacity-0 transition group-hover:opacity-100">
                                    <button
                                      type="button"
                                      className={`flex h-4 w-4 items-center justify-center rounded-[4px] border bg-white/90 hover:bg-white ${task.status === 'done' ? 'border-[#CBD5E1] text-[#64748B]' : 'border-current'}`}
                                      onMouseDown={(event) => {
                                        event.stopPropagation();
                                      }}
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        void onToggleTaskStatus(task.id);
                                      }}
                                      title={task.status === 'done' ? '取消完成' : '标记完成'}
                                      aria-label={task.status === 'done' ? `取消完成 ${task.title}` : `完成 ${task.title}`}
                                    >
                                      <Check size={9} strokeWidth={3} />
                                    </button>
                                    <button
                                      type="button"
                                      className="flex h-4 w-4 items-center justify-center rounded-[4px] border border-current bg-white/90 hover:bg-white"
                                      onMouseDown={(event) => {
                                        event.stopPropagation();
                                      }}
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        onOpenTaskEditor(task);
                                      }}
                                      title={`编辑 ${task.title}`}
                                      aria-label={`编辑 ${task.title}`}
                                    >
                                      <Pencil size={9} strokeWidth={2.5} />
                                    </button>
                                  </div>
                                  <div
                                    className={`absolute inset-x-0 bottom-0 flex h-5 cursor-ns-resize items-end justify-center rounded-b-2xl transition-opacity ${isResizing ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}
                                    onMouseDown={(event) => handleStartWeekTaskResize(task.id, startMinute, durationMinutes, event)}
                                    onClick={(event) => {
                                      event.preventDefault();
                                      event.stopPropagation();
                                    }}
                                    title="拖动底边调整时长"
                                  >
                                    <div className="mb-1 flex items-center justify-center rounded-full bg-white/92 px-2 py-0.5 text-slate-400 shadow-sm ring-1 ring-slate-200">
                                      <MoveVertical size={12} />
                                    </div>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

    </div>
  );
}
~~~

## `src/renderer/components/tasks/TaskOrgContextPanel.tsx`

- 编码: `utf-8`

~~~tsx
import React from 'react';

import type { BackgroundReadiness, EmployeeRole, EventLine, Task, TaskContextPreview, TaskProjectContext } from '../../../shared/types';

type TaskOrgContextPanelProps = {
  task: Pick<Task, 'title' | 'desc' | 'projectModuleName' | 'projectFlowName' | 'sourceType' | 'orgContext' | 'projectContext' | 'eventLineName' | 'attachments' | 'memoryHints' | 'backgroundReadiness' | 'linkedFactsPreview'>;
  compact?: boolean;
  viewerRole?: EmployeeRole | null;
  eventLine?: Pick<EventLine, 'id' | 'name' | 'stage' | 'summary' | 'intent' | 'currentBlocker' | 'recentDecision' | 'nextStep' | 'status'> | null;
  contextPreview?: TaskContextPreview | null;
};

type InsightTone = 'neutral' | 'focus' | 'risk' | 'action' | 'opportunity';
type TaskMode = 'relationship' | 'deliverable' | 'materials' | 'decision' | 'analysis' | 'general';
type BusinessCategory = 'business_expansion' | 'delivery' | 'knowledge_base' | 'coordination' | 'analysis' | 'internal';

type InsightItem = {
  label: string;
  value: string;
  tone: InsightTone;
  order: number;
};

function pushUniqueInsight(target: InsightItem[], item: InsightItem | null) {
  if (!item?.value.trim()) return;
  if (target.some((existing) => existing.label === item.label && existing.value === item.value)) return;
  target.push(item);
}

function buildSummaryChips(
  categoryLabel?: string | null,
  projectContext?: TaskProjectContext | null,
  eventLineName?: string | null,
  eventLineStage?: string | null,
) {
  const chips: string[] = [];
  if (categoryLabel) chips.push(categoryLabel);
  if (eventLineName) chips.push(`事件线 · ${eventLineName}`);
  if (projectContext?.clientName) chips.push(`项目 · ${projectContext.clientName}`);
  if (eventLineStage) chips.push(`线索阶段 · ${eventLineStage}`);
  else if (projectContext?.stage) chips.push(`阶段 · ${projectContext.stage}`);
  if (projectContext?.projectModuleName) chips.push(`模块 · ${projectContext.projectModuleName}`);
  else if (projectContext?.projectFlowName) chips.push(`流程 · ${projectContext.projectFlowName}`);
  return chips.slice(0, 3);
}

function normalizeLineText(value?: string | null) {
  return (value || '').replace(/\s+/g, ' ').trim();
}

function isGenericAnalysisLine(value?: string | null, taskTitle?: string | null) {
  const normalized = normalizeLineText(value);
  if (!normalized) return true;
  const genericPatterns = [
    /^当前没有特别突出的阻塞/u,
    /^当前阻塞更像/u,
    /^当前阻塞仍需结合最近/u,
    /^最近进展仍待补充/u,
    /^最近进展：.+\s*\/\s*.+$/u,
    /^当前任务更具体的落点是/u,
    /^当前更具体的推进点是/u,
    /^当前重点仍待补充/u,
    /^下一步动作：先补齐项目背景/u,
    /项目背景、目标和流程线索/u,
    /挂进清晰的项目结构/u,
    /挂进明确模块或流程/u,
    /结构化归属不足/u,
    /可围绕既定目标继续推进/u,
    /已围绕.+持续推进/u,
  ];
  if (genericPatterns.some((pattern) => pattern.test(normalized))) return true;
  const normalizedTitle = normalizeLineText(taskTitle);
  if (normalizedTitle && normalized.includes(normalizedTitle) && normalized.length <= normalizedTitle.length + 24) return true;
  return false;
}

function truncateText(value: string, limit = 48) {
  if (value.length <= limit) return value;
  return `${value.slice(0, limit - 1).trim()}…`;
}

function compactInsightText(value?: string | null, limit = 38) {
  const normalized = normalizeLineText(value)
    .replace(/^(当前任务更具体的推进点是|当前更具体的推进点是|当前推进点是|当前落点是|当前主要风险|当前卡点|当前阻塞|主要阻塞|最近进展|下一步动作|下一步|背景|目标|风险|建议动作|最近已经明确)[:：]\s*/u, '')
    .replace(/^这条线(当前)?在推进[:：]?\s*/u, '')
    .replace(/^对于[^，。；;]+来说[，,]\s*/u, '')
    .replace(/^当前(不是|仍|更像|已经)?/u, '')
    .replace(/如果未来1-2周还不收束[，,]?\s*/u, '')
    .replace(/[。；;]+$/u, '')
    .trim();
  return truncateText(normalized, limit);
}

function splitTaskClauses(value?: string | null) {
  return (value || '')
    .split(/\n|[|｜]|[。；;]/)
    .map((item) => normalizeLineText(item))
    .map((item) => item.replace(/^(内部管理|客户项目|项目背景|背景|说明|备注|关联目标|当前事项|当前阻塞|最近进展|预期输出|下一步动作|下一步|结果|目标)[:：]\s*/u, ''))
    .filter(Boolean);
}

function pickClause(clauses: string[], patterns: RegExp[], fallbackToFirst = false) {
  for (const pattern of patterns) {
    const matched = clauses.find((item) => pattern.test(item));
    if (matched) return matched;
  }
  return fallbackToFirst ? (clauses[0] || '') : '';
}

function inferTaskMode(task: TaskOrgContextPanelProps['task']): TaskMode {
  const source = `${task.title} ${task.desc || ''}`;
  if (/(吃饭|见面|拜访|会谈|沟通|讨论|约见|会面|午餐|晚餐|聊|对接)/u.test(source)) return 'relationship';
  if (/(方案|文稿|报告|清单|框架|PPT|输出|提交|草稿|总结|邮件|交付)/u.test(source)) return 'deliverable';
  if (/(资料|整理|导入|补录|拍照|收集|归档|文件|台账|底稿|素材|信息库)/u.test(source)) return 'materials';
  if (/(确认|拍板|审批|复核|签字|决定|校对|认领)/u.test(source)) return 'decision';
  if (/(调研|分析|诊断|研究|洞察|判断|策略)/u.test(source)) return 'analysis';
  return 'general';
}

function inferBusinessCategory(
  task: TaskOrgContextPanelProps['task'],
  taskMode: TaskMode,
  eventLine?: TaskOrgContextPanelProps['eventLine'],
): BusinessCategory {
  const source = `${task.title} ${task.desc || ''} ${eventLine?.intent || ''} ${eventLine?.summary || ''}`;
  if (taskMode === 'relationship' || /(客户|基金会|合作|拓展|关系|会面|拜访|赋能|对接)/u.test(source)) return 'business_expansion';
  if (taskMode === 'deliverable') return 'delivery';
  if (taskMode === 'materials') return 'knowledge_base';
  if (taskMode === 'analysis') return 'analysis';
  if (taskMode === 'decision' || /(确认|审批|复核|协同|认领|拍板|校对)/u.test(source)) return 'coordination';
  return 'internal';
}

function businessCategoryLabel(category: BusinessCategory) {
  if (category === 'business_expansion') return '业务扩展';
  if (category === 'delivery') return '正式交付';
  if (category === 'knowledge_base') return '资料沉淀';
  if (category === 'coordination') return '协同确认';
  if (category === 'analysis') return '判断提炼';
  return '内部推进';
}

function buildModeFocus(
  category: BusinessCategory,
  taskMode: TaskMode,
  _taskTitle: string,
  moduleName?: string | null,
  flowName?: string | null,
) {
  const scope = flowName || moduleName || '当前事项';
  if (category === 'business_expansion') return `先把这次接触收成业务结论，落点放在${scope}`;
  if (category === 'delivery') return `先把这条线收成正式交付，落点放在${scope}`;
  if (category === 'knowledge_base') return `先把资料补成底盘，落点放在${scope}`;
  if (category === 'coordination') return `先把确认链前移，落点放在${scope}`;
  if (category === 'analysis') return `先把判断压成可执行结论，落点放在${scope}`;
  if (taskMode === 'relationship') return `先把关系推进收成明确结论，落点放在${scope}`;
  return `先把这件事收成明确结果，不再停在泛推进`;
}

function buildModeRisk(category: BusinessCategory, taskMode: TaskMode, taskTitle: string) {
  if (category === 'business_expansion') return `最大风险是只推进关系，没有沉成业务结论`;
  if (category === 'delivery') return `最大风险是口径不定，继续停在反复修改`;
  if (category === 'knowledge_base') return `最大风险是资料不成底盘，后续判断都会偏浅`;
  if (category === 'coordination') return `最大风险是确认链继续拖，后续动作都会顺带卡住`;
  if (category === 'analysis') return `最大风险是边界不清，继续分析却不落地`;
  if (taskMode === 'relationship') return `最大风险是关系在推进，业务没有收口`;
  return `${taskTitle}还缺清晰边界，投入容易继续摊薄`;
}

function buildModeOpportunity(category: BusinessCategory, taskMode: TaskMode, taskTitle: string, attachmentCount: number) {
  if (category === 'business_expansion') return `把会谈结论写实后，这条线就能转成下一步合作`;
  if (category === 'delivery') return `一旦成稿，这条线就会变成可复用交付资产`;
  if (category === 'knowledge_base') return `资料一旦补齐，后续判断会明显变准${attachmentCount > 0 ? `，已有 ${attachmentCount} 份证据可用` : ''}`;
  if (category === 'coordination') return `确认一旦完成，会直接释放后续推进空间`;
  if (category === 'analysis') return `判断一旦写实，后续沟通和决策会明显聚焦`;
  if (taskMode === 'relationship') return `把会谈沉成结论后，容易直接转成下一步合作`;
  return `只要尽快收束成结果，就能从零散动作变成推进线`;
}

function buildModeAction(category: BusinessCategory, taskMode: TaskMode, taskTitle: string) {
  if (category === 'business_expansion') return `先定结论、关键判断和会后跟进动作`;
  if (category === 'delivery') return `先定交付边界、口径和成稿责任`;
  if (category === 'knowledge_base') return `先补关键资料、证据和底层文件`;
  if (category === 'coordination') return `先定谁确认、何时确认、确认后谁推进`;
  if (category === 'analysis') return `先把判断压成一句结论和三个动作`;
  if (taskMode === 'relationship') return `先把会谈沉成结论，不要只停在交流`;
  return `先定义最小结果，再推进`;
}

function buildInsightAnchor(task: TaskOrgContextPanelProps['task']) {
  return [
    task.title,
    task.projectFlowName,
    task.projectModuleName,
    task.eventLineName,
    task.projectContext?.projectFlowName,
    task.projectContext?.projectModuleName,
  ]
    .map((item) => normalizeLineText(item))
    .find(Boolean) || '';
}

function prefixWithAnchor(anchor: string, value?: string | null) {
  const normalized = normalizeLineText(value);
  if (!normalized) return '';
  if (!anchor || normalized.includes(anchor)) return normalized;
  return `${anchor}：${normalized}`;
}

function hasSpecificTaskScope(task: TaskOrgContextPanelProps['task']) {
  return Boolean(
    normalizeLineText(task.eventLineName) ||
    task.projectContext?.projectModuleId ||
    task.projectContext?.projectFlowId,
  );
}

function hasMaterialProgress(task: TaskOrgContextPanelProps['task'], eventLine?: TaskOrgContextPanelProps['eventLine']) {
  return Boolean(
    task.attachments.length > 0 ||
    normalizeLineText(task.projectContext?.recentProgress) ||
    normalizeLineText(task.projectContext?.nextAction) ||
    normalizeLineText(task.projectContext?.currentBlocker) ||
    normalizeLineText(task.projectContext?.currentFocus) ||
    normalizeLineText(eventLine?.summary) ||
    normalizeLineText(eventLine?.currentBlocker) ||
    normalizeLineText(eventLine?.recentDecision) ||
    normalizeLineText(eventLine?.nextStep) ||
    normalizeLineText(eventLine?.intent),
  );
}

function buildContextRisk(
  task: TaskOrgContextPanelProps['task'],
  eventLine: TaskOrgContextPanelProps['eventLine'],
  anchor: string,
  hasSpecificScope: boolean,
) {
  const { projectContext, orgContext } = task;
  const eventLineBlocker = isGenericAnalysisLine(eventLine?.currentBlocker, task.title) ? '' : normalizeLineText(eventLine?.currentBlocker);
  const projectBlocker = isGenericAnalysisLine(projectContext?.currentBlocker, task.title) ? '' : normalizeLineText(projectContext?.currentBlocker);
  if (eventLineBlocker && hasSpecificScope) return prefixWithAnchor(anchor, eventLineBlocker);
  if (projectBlocker && hasSpecificScope) return prefixWithAnchor(anchor, projectBlocker);
  if (eventLine?.status === 'blocked') return `${anchor || '这条任务'}所属事件线当前处于受阻状态，建议先处理卡点再推进。`;
  if (eventLine?.status === 'paused') return `${anchor || '这条任务'}所属事件线当前处于暂停状态，推进前需要先确认是否继续。`;
  if (orgContext?.blockedAtStep) return `${anchor || '这条任务'}卡在 ${orgContext.blockedAtStep}`;
  if (hasSpecificScope && (orgContext?.approvalState === 'pending' || orgContext?.needsReview)) {
    return `${anchor || '这条任务'}仍卡在确认链，推进速度受复核影响`;
  }
  if (hasSpecificScope && orgContext?.isCrossDepartment) return `${anchor || '这条任务'}需要跨部门同步，节奏容易受他方反馈影响`;
  if (hasSpecificScope && projectContext?.infoCompleteness === 'low') return `${anchor || '这条任务'}的项目资料仍偏薄，判断深度和交付精度都受影响`;
  if (projectContext?.riskSummary && hasSpecificScope) return prefixWithAnchor(anchor, projectContext.riskSummary);
  return '';
}

function buildOpportunity(
  task: TaskOrgContextPanelProps['task'],
  eventLine: TaskOrgContextPanelProps['eventLine'],
  anchor: string,
  hasSpecificScope: boolean,
  hasProgressSignal: boolean,
) {
  const { projectContext, orgContext, attachments } = task;
  const projectProgress = isGenericAnalysisLine(projectContext?.recentProgress, task.title) ? '' : normalizeLineText(projectContext?.recentProgress);
  const eventLineSummary = isGenericAnalysisLine(eventLine?.summary, task.title) ? '' : normalizeLineText(eventLine?.summary);
  const eventLineDecision = isGenericAnalysisLine(eventLine?.recentDecision, task.title) ? '' : normalizeLineText(eventLine?.recentDecision);
  const eventLineIntent = isGenericAnalysisLine(eventLine?.intent, task.title) ? '' : normalizeLineText(eventLine?.intent);
  if (attachments.length > 0 && projectProgress) {
    return `${prefixWithAnchor(anchor, projectProgress)}，而且证据已开始沉淀，可继续放大为正式交付`;
  }
  if (projectProgress && hasSpecificScope) return prefixWithAnchor(anchor, projectProgress);
  if (eventLineSummary && hasSpecificScope) return prefixWithAnchor(anchor, eventLineSummary);
  if (attachments.length > 0) return `${anchor || '这条任务'}已沉淀 ${attachments.length} 份任务附件，可从零散动作转为可复用成果`;
  if (projectContext?.goalSummary && hasSpecificScope) return `${anchor || '这条任务'}当前对准：${projectContext.goalSummary}`;
  if (eventLineDecision && hasSpecificScope) return `${anchor || '这条任务'}最近已明确：${eventLineDecision}`;
  if (eventLineIntent && hasSpecificScope) return `${anchor || '这条任务'}正在对准：${eventLineIntent}`;
  if (hasProgressSignal && orgContext?.organizationFocusKey && hasSpecificScope) return `${anchor || '这条任务'}已经贴近机构焦点：${orgContext.organizationFocusKey}`;
  if (hasProgressSignal && orgContext?.departmentFocusKey && hasSpecificScope) return `${anchor || '这条任务'}已经贴近部门焦点：${orgContext.departmentFocusKey}`;
  return '';
}

function buildInsights(
  task: TaskOrgContextPanelProps['task'],
  viewerRole: EmployeeRole | null | undefined,
  compact: boolean,
  eventLine?: TaskOrgContextPanelProps['eventLine'],
) {
  const insights: InsightItem[] = [];
  const { projectContext, orgContext, attachments = [] } = task;
  const isAdminView = viewerRole === 'admin';
  const anchor = buildInsightAnchor(task);
  const taskTitle = truncateText(normalizeLineText(task.title) || '这条任务', 28);
  const taskMode = inferTaskMode(task);
  const category = inferBusinessCategory(task, taskMode, eventLine);
  const clauses = splitTaskClauses(task.desc);
  const hasSpecificScope = hasSpecificTaskScope(task);
  const hasProgressSignal = hasMaterialProgress(task, eventLine);
  const taskFocusText = pickClause(clauses, [/预期输出/u, /推进/u, /形成/u, /梳理/u, /整理/u, /确认/u, /交付/u, /方案/u], true);
  const taskRiskText = pickClause(clauses, [/阻塞/u, /卡/u, /等待/u, /待/u, /未/u, /缺/u, /补/u, /风险/u, /确认/u]);
  const taskOpportunityText = pickClause(clauses, [/预期输出/u, /目标/u, /结果/u, /交付/u, /沉淀/u, /复用/u, /资料/u, /方案/u]);
  const taskNextText = pickClause(clauses, [/下一步/u, /继续/u, /先/u, /补/u, /确认/u, /推进/u]);
  const eventLineFocusText = !isGenericAnalysisLine(eventLine?.summary, task.title)
    ? normalizeLineText(eventLine?.summary)
    : !isGenericAnalysisLine(eventLine?.intent, task.title)
      ? normalizeLineText(eventLine?.intent)
      : '';
  const eventLineRiskText = isGenericAnalysisLine(eventLine?.currentBlocker, task.title) ? '' : normalizeLineText(eventLine?.currentBlocker);
  const eventLineNextText = isGenericAnalysisLine(eventLine?.nextStep, task.title) ? '' : normalizeLineText(eventLine?.nextStep);
  const eventLineDecisionText = isGenericAnalysisLine(eventLine?.recentDecision, task.title) ? '' : normalizeLineText(eventLine?.recentDecision);
  const projectFocusText = isGenericAnalysisLine(projectContext?.currentFocus, task.title) ? '' : normalizeLineText(projectContext?.currentFocus);
  const projectNextText = isGenericAnalysisLine(projectContext?.nextAction, task.title) ? '' : normalizeLineText(projectContext?.nextAction);
  const focusText = taskFocusText || eventLineFocusText || projectFocusText;
  const backgroundText = hasSpecificScope ? normalizeLineText(projectContext?.backgroundSummary) : '';
  const riskText = taskRiskText || eventLineRiskText || buildContextRisk(task, eventLine, anchor, hasSpecificScope);
  const opportunityText = taskOpportunityText || eventLineDecisionText || buildOpportunity(task, eventLine, anchor, hasSpecificScope, hasProgressSignal);
  const nextActionText = hasSpecificScope
    ? (taskNextText || eventLineNextText || projectNextText)
    : '';
  const recentDecisionText = hasSpecificScope ? eventLineDecisionText : '';
  const moduleName = task.projectModuleName || projectContext?.projectModuleName;
  const flowName = task.projectFlowName || projectContext?.projectFlowName;

  pushUniqueInsight(insights, focusText
    ? {
        label: isAdminView ? '核心判断' : '当前重点',
        value: taskFocusText
          ? compactInsightText(taskFocusText, compact ? 28 : 36)
          : eventLineFocusText
            ? compactInsightText(eventLineFocusText, compact ? 28 : 36)
            : (compactInsightText(prefixWithAnchor(anchor, focusText), compact ? 28 : 36) || buildModeFocus(category, taskMode, taskTitle, moduleName, flowName)),
        tone: 'focus',
        order: isAdminView ? 1 : 2,
      }
    : backgroundText
      ? {
          label: isAdminView ? '核心判断' : '当前重点',
          value: compactInsightText(prefixWithAnchor(anchor, backgroundText), compact ? 28 : 36) || buildModeFocus(category, taskMode, taskTitle, moduleName, flowName),
          tone: 'focus',
          order: isAdminView ? 1 : 2,
        }
      : {
          label: isAdminView ? '核心判断' : '当前重点',
          value: buildModeFocus(category, taskMode, taskTitle, moduleName, flowName),
          tone: 'focus',
          order: isAdminView ? 1 : 2,
        });

  pushUniqueInsight(insights, {
    label: isAdminView ? '最大风险' : '当前卡点',
    value: riskText
      ? (taskRiskText
          ? compactInsightText(taskRiskText, compact ? 28 : 36)
          : eventLineRiskText
            ? compactInsightText(eventLineRiskText, compact ? 28 : 36)
            : compactInsightText(riskText, compact ? 28 : 36))
      : buildModeRisk(category, taskMode, taskTitle),
    tone: 'risk',
    order: 0,
  });

  pushUniqueInsight(insights, {
    label: isAdminView ? '可放大点' : '可继续放大',
    value: opportunityText
      ? (taskOpportunityText
          ? compactInsightText(taskOpportunityText, compact ? 28 : 36)
          : eventLineDecisionText
            ? compactInsightText(eventLineDecisionText, compact ? 28 : 36)
            : compactInsightText(opportunityText, compact ? 28 : 36))
      : buildModeOpportunity(category, taskMode, taskTitle, attachments.length),
    tone: 'opportunity',
    order: isAdminView ? 2 : 3,
  });

  pushUniqueInsight(insights, recentDecisionText
    ? {
        label: '最近关键决策',
        value: prefixWithAnchor(anchor, recentDecisionText),
        tone: 'neutral',
        order: isAdminView ? 2 : 3,
      }
    : null);

  pushUniqueInsight(insights, {
    label: '先做什么',
    value: nextActionText
      ? (taskNextText
          ? compactInsightText(taskNextText, compact ? 28 : 36)
          : eventLineNextText
            ? compactInsightText(eventLineNextText, compact ? 28 : 36)
            : compactInsightText(prefixWithAnchor(anchor, nextActionText), compact ? 28 : 36))
      : buildModeAction(category, taskMode, taskTitle),
    tone: 'action',
    order: isAdminView ? 3 : 1,
  });

  return insights
    .sort((left, right) => left.order - right.order)
    .slice(0, 4);
}

function toneClasses(tone: InsightTone) {
  if (tone === 'focus') return 'border-blue-100 bg-blue-50/70 text-blue-700';
  if (tone === 'risk') return 'border-amber-100 bg-amber-50/70 text-amber-700';
  if (tone === 'action') return 'border-emerald-100 bg-emerald-50/70 text-emerald-700';
  if (tone === 'opportunity') return 'border-violet-100 bg-violet-50/70 text-violet-700';
  return 'border-slate-200 bg-white text-slate-700';
}

function memorySourceLabel(value: string) {
  if (value === 'organization_notebook') return '组织笔记';
  if (value === 'event_line_memory') return '事件线记忆';
  if (value === 'task_facts') return '任务事实';
  if (value === 'client_facts') return '客户事实';
  if (value === 'event_line_facts') return '事件线事实';
  return value;
}

function readinessTone(readiness?: BackgroundReadiness | null) {
  if (readiness?.level === 'high') return 'border-emerald-100 bg-emerald-50/70 text-emerald-700';
  if (readiness?.level === 'medium') return 'border-blue-100 bg-blue-50/70 text-blue-700';
  return 'border-amber-100 bg-amber-50/70 text-amber-700';
}

function buildPreviewInsights(preview: TaskContextPreview, compact: boolean, viewerRole?: EmployeeRole | null) {
  const isManagerView = viewerRole === 'admin' || viewerRole === 'department_lead';
  const judgment = preview.judgment;
  const limit = compact ? 34 : 60;
  const happened = compactInsightText(judgment.whatHappened, limit);
  const matters = compactInsightText(judgment.whyItMatters, limit);
  const blocker = compactInsightText(judgment.coreBlocker || judgment.riskIfIgnored, limit);
  const opportunity = compactInsightText(judgment.opportunityIfAmplified || judgment.managerImplication, limit);
  const action = compactInsightText(judgment.minimumAction || judgment.nextWeekFocus, limit);
  return [
    {
      label: isManagerView ? '管理判断' : '本周推进',
      value: isManagerView ? (matters || happened) : (happened || matters),
      tone: 'focus' as const,
      order: isManagerView ? 1 : 2,
    },
    {
      label: isManagerView ? '真正阻碍' : '当前卡点',
      value: blocker,
      tone: 'risk' as const,
      order: 0,
    },
    {
      label: isManagerView ? '可放大点' : '可继续放大',
      value: opportunity,
      tone: 'opportunity' as const,
      order: isManagerView ? 2 : 3,
    },
    {
      label: '先做什么',
      value: action,
      tone: 'action' as const,
      order: isManagerView ? 3 : 1,
    },
  ].filter((item) => item.value);
}

export function TaskOrgContextPanel({ task, compact = false, viewerRole, eventLine, contextPreview }: TaskOrgContextPanelProps) {
  const taskMode = inferTaskMode(task);
  const category = inferBusinessCategory(task, taskMode, eventLine);
  const summaryChips = contextPreview?.summaryChips?.length
    ? contextPreview.summaryChips
    : buildSummaryChips(businessCategoryLabel(category), task.projectContext, task.eventLineName, eventLine?.stage || null);
  const insights = contextPreview
    ? buildPreviewInsights(contextPreview, compact, viewerRole)
    : buildInsights(task, viewerRole, compact, eventLine);
  const memoryHints = contextPreview
    ? [
        contextPreview.judgment.managerImplication,
        contextPreview.judgment.evidenceSummary,
        contextPreview.judgment.riskIfIgnored,
      ].filter(Boolean)
    : (task.memoryHints || []);
  const backgroundReadiness: BackgroundReadiness | null = contextPreview
    ? {
        score: contextPreview.readiness === 'high' ? 1 : contextPreview.readiness === 'medium' ? 0.6 : 0.3,
        level: contextPreview.readiness,
        missingSlots: [],
        backgroundSources: [
          contextPreview.contextBundle.organizationIntro ? 'organization_notebook' : '',
          contextPreview.contextBundle.lineName ? 'event_line_memory' : '',
          contextPreview.contextBundle.taskFacts.length ? 'task_facts' : '',
          contextPreview.contextBundle.attachmentFacts.length ? 'task_facts' : '',
        ].filter(Boolean),
      }
    : (task.backgroundReadiness || null);
  const linkedFactsPreview = contextPreview
    ? [
        ...contextPreview.contextBundle.recentFacts,
        ...contextPreview.contextBundle.clarificationFacts.map((item) => item.summary),
      ].filter(Boolean).slice(0, 4)
    : (task.linkedFactsPreview || []);
  const memorySourceChips = (backgroundReadiness?.backgroundSources || []).map(memorySourceLabel);
  if (summaryChips.length === 0 && insights.length === 0 && memoryHints.length === 0 && memorySourceChips.length === 0) return null;

  return (
    <div className={`rounded-2xl border border-slate-200 bg-slate-50/70 ${compact ? 'mt-3 px-3 py-3' : 'mt-4 px-4 py-3.5'}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[10px] font-bold tracking-[0.18em] text-slate-400">AI 洞察</span>
        {summaryChips.map((chip) => (
          <span
            key={chip}
            className={`rounded-full border border-slate-200 bg-white text-slate-600 ${compact ? 'px-2 py-1 text-[10px]' : 'px-2.5 py-1 text-[11px]'} font-semibold`}
          >
            {chip}
          </span>
        ))}
      </div>
      {(memoryHints.length > 0 || memorySourceChips.length > 0 || (backgroundReadiness?.missingSlots?.length || 0) > 0) && (
        <div className={`mt-3 rounded-xl border px-3 py-2.5 ${readinessTone(backgroundReadiness)}`}>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-semibold opacity-75">
              准备度 {Math.round((backgroundReadiness?.score || 0) * 100)}%
            </span>
            {memorySourceChips.map((chip) => (
              <span key={chip} className="rounded-full bg-white/80 px-2 py-1 text-[10px] font-semibold">
                {chip}
              </span>
            ))}
          </div>
          {memoryHints.length > 0 && (
            <p className={`mt-2 ${compact ? 'text-[11px]' : 'text-[12px]'} leading-5`}>
              {compactInsightText(memoryHints[0], compact ? 44 : 88)}
            </p>
          )}
          {backgroundReadiness?.missingSlots?.length ? (
            <p className="mt-2 text-[11px] leading-5 opacity-80">
              待补：{backgroundReadiness.missingSlots.slice(0, 3).join('、')}
            </p>
          ) : null}
          {linkedFactsPreview.length > 0 ? (
            <p className="mt-1 text-[11px] leading-5 opacity-70">
              已关联 {linkedFactsPreview.length} 条背景事实
            </p>
          ) : null}
        </div>
      )}
      {insights.length > 0 && (
        <div className={`grid gap-2 ${compact ? 'mt-2.5' : 'mt-3'} ${insights.length > 1 ? 'sm:grid-cols-2' : 'grid-cols-1'}`}>
          {insights.map((insight) => (
            <div
              key={`${insight.label}-${insight.value}`}
              className={`rounded-xl border px-3 py-2.5 ${toneClasses(insight.tone)}`}
            >
              <p className="text-[10px] font-semibold opacity-70">{insight.label}</p>
              <p className={`mt-1 ${compact ? 'text-[11px]' : 'text-[12px]'} font-medium leading-5 break-words line-clamp-3`}>
                {insight.value}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
~~~

