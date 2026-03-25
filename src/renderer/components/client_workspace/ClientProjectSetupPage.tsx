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
                className={`h-full rounded-full bg-[linear-gradient(90deg,#5B7BFE,#7B93FF)] transition-all duration-500 ${isIndeterminateProgress ? 'animate-pulse' : ''}`}
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
