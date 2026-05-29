import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  ChevronRight,
  Download,
  FileText,
  Loader2,
  RefreshCw,
  Sparkles,
  X,
} from 'lucide-react';
import type {
  ReportBlueprint,
  ReportFileFormat,
  ReportRunSummary,
  ReportSectionStatus,
  SectionPlan,
} from '../../../shared/types.js';
import {
  draftReportBlueprint,
  draftReportSections,
  getReportFileDownloadUrl,
  getReportRun,
  renderReport,
} from '../../lib/api.js';

type Phase =
  | 'intent'
  | 'reviewing-blueprint'
  | 'drafting-sections'
  | 'rendered'
  | 'failed';

interface AIReportGeneratorModalProps {
  eventLineId: string;
  eventLineName?: string;
  clientName?: string;
  onClose: () => void;
  /**
   * 可选：让外层接管下载（例如 Electron 的 saveFileAs 系统对话框）。
   * 不提供则默认走 <a download> 浏览器下载。
   */
  onDownload?: (url: string, fileName: string) => Promise<void>;
}

interface IntentForm {
  periodStart: string;
  periodEnd: string;
  intentHint: string;
  audienceHint: string;
  toneHint: string;
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return '未知错误，请重试';
}

function defaultPeriod(): { start: string; end: string } {
  const now = new Date();
  const month = now.getMonth();
  const quarterStartMonth = Math.floor(month / 3) * 3;
  const start = new Date(now.getFullYear(), quarterStartMonth, 1);
  const end = new Date(now.getFullYear(), quarterStartMonth + 3, 0);
  const fmt = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return { start: fmt(start), end: fmt(end) };
}

function sanitizeFileName(raw: string): string {
  return raw.replace(/[\\/:*?"<>|\s]+/g, '_').slice(0, 80) || 'report';
}

export default function AIReportGeneratorModal({
  eventLineId,
  eventLineName,
  clientName,
  onClose,
  onDownload,
}: AIReportGeneratorModalProps): JSX.Element {
  const [phase, setPhase] = useState<Phase>('intent');
  const [intent, setIntent] = useState<IntentForm>(() => {
    const p = defaultPeriod();
    return {
      periodStart: p.start,
      periodEnd: p.end,
      intentHint: '',
      audienceHint: '客户决策层',
      toneHint: '客观、克制、可执行',
    };
  });
  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [run, setRun] = useState<ReportRunSummary | null>(null);
  const [pollEnabled, setPollEnabled] = useState(false);
  const pollRef = useRef<number | null>(null);

  const handleStart = useCallback(async () => {
    setErrorMsg(null);
    setBusy(true);
    try {
      const result = await draftReportBlueprint({
        event_line_id: eventLineId,
        period_start: intent.periodStart || null,
        period_end: intent.periodEnd || null,
        intent_hint: intent.intentHint || null,
        audience_hint: intent.audienceHint || null,
        tone_hint: intent.toneHint || null,
      });
      setRun(result);
      if (result.status === 'failed') {
        setPhase('failed');
        setErrorMsg('LLM 草拟骨架失败，请重试');
      } else {
        setPhase('reviewing-blueprint');
      }
    } catch (e) {
      setErrorMsg(getErrorMessage(e));
    } finally {
      setBusy(false);
    }
  }, [eventLineId, intent]);

  const handleConfirmBlueprint = useCallback(async () => {
    if (!run) return;
    setErrorMsg(null);
    setBusy(true);
    try {
      const result = await draftReportSections(run.id, { max_workers: 4 });
      setRun(result);
      setPhase('drafting-sections');
      setPollEnabled(true);
    } catch (e) {
      setErrorMsg(getErrorMessage(e));
    } finally {
      setBusy(false);
    }
  }, [run]);

  const handleRender = useCallback(
    async (format: ReportFileFormat) => {
      if (!run) return;
      setErrorMsg(null);
      setBusy(true);
      try {
        const result = await renderReport(run.id, format);
        setRun(result);
        setPhase('rendered');
      } catch (e) {
        setErrorMsg(getErrorMessage(e));
      } finally {
        setBusy(false);
      }
    },
    [run],
  );

  const handleDownload = useCallback(
    async (format: ReportFileFormat) => {
      if (!run) return;
      const url = getReportFileDownloadUrl(run.id, format);
      const baseName = sanitizeFileName(run.blueprint?.title || 'report');
      const fileName = `${baseName}.${format}`;
      if (onDownload) {
        try {
          await onDownload(url, fileName);
        } catch (e) {
          setErrorMsg(getErrorMessage(e));
        }
        return;
      }
      const link = document.createElement('a');
      link.href = url;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    },
    [run, onDownload],
  );

  const handleRestart = useCallback(() => {
    setPhase('intent');
    setRun(null);
    setErrorMsg(null);
    setPollEnabled(false);
  }, []);

  useEffect(() => {
    if (!pollEnabled || !run) return;
    const runId = run.id;
    const tick = async () => {
      try {
        const updated = await getReportRun(runId);
        setRun(updated);
        const statuses = updated.sections_status || [];
        if (updated.status === 'failed') {
          setPhase('failed');
          setErrorMsg(updated.intent_hint ? null : '章节起草失败');
          setPollEnabled(false);
          return;
        }
        const stillRunning = statuses.some((s) => s === 'drafting' || s === 'pending');
        if (!stillRunning) {
          setPollEnabled(false);
        }
      } catch {
        // 网络抖动，下个 tick 再试
      }
    };
    void tick();
    pollRef.current = window.setInterval(tick, 3000);
    return () => {
      if (pollRef.current !== null) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [pollEnabled, run?.id]);

  useEffect(() => {
    if (phase === 'rendered' || phase === 'failed') {
      setPollEnabled(false);
    }
  }, [phase]);

  const allSectionsDone = useMemo(() => {
    if (!run) return false;
    const statuses = run.sections_status || [];
    return statuses.length > 0 && statuses.every((s) => s === 'done');
  }, [run]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="flex h-[85vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        <Header
          eventLineName={eventLineName}
          clientName={clientName}
          phase={phase}
          onClose={onClose}
        />
        <div className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
          {errorMsg && (
            <ErrorBanner
              message={errorMsg}
              onDismiss={() => setErrorMsg(null)}
            />
          )}

          {phase === 'intent' && (
            <IntentFormBlock
              intent={intent}
              onChange={setIntent}
              onSubmit={handleStart}
              busy={busy}
            />
          )}

          {phase === 'reviewing-blueprint' && run?.blueprint && (
            <BlueprintReviewBlock
              blueprint={run.blueprint}
              onConfirm={handleConfirmBlueprint}
              onRestart={handleRestart}
              busy={busy}
            />
          )}

          {phase === 'drafting-sections' && run && run.blueprint && (
            <DraftingProgressBlock
              run={run}
              onRender={() => void handleRender('docx')}
              allDone={allSectionsDone}
              busy={busy}
            />
          )}

          {phase === 'rendered' && run && run.blueprint && (
            <RenderedBlock
              run={run}
              onDownload={handleDownload}
              onRenderOther={(format) => void handleRender(format)}
              busy={busy}
              onRestart={handleRestart}
            />
          )}

          {phase === 'failed' && (
            <FailedBlock onRestart={handleRestart} message={errorMsg} />
          )}
        </div>
      </div>
    </div>
  );
}

interface HeaderProps {
  eventLineName?: string;
  clientName?: string;
  phase: Phase;
  onClose: () => void;
}

function Header({ eventLineName, clientName, phase, onClose }: HeaderProps) {
  return (
    <div className="flex items-start justify-between border-b border-gray-100 bg-gradient-to-br from-blue-50 to-white px-6 py-4">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600 text-white">
          <Sparkles size={18} />
        </div>
        <div>
          <h2 className="text-[15px] font-bold text-gray-900">AI 报告生成器</h2>
          <p className="mt-0.5 text-[12px] text-gray-500">
            {eventLineName && <span className="font-medium text-gray-700">{eventLineName}</span>}
            {clientName && <> · {clientName}</>}
            <> · {phaseLabel(phase)}</>
          </p>
        </div>
      </div>
      <button
        type="button"
        onClick={onClose}
        className="rounded-lg p-1.5 text-gray-400 transition hover:bg-gray-100 hover:text-gray-700"
        aria-label="关闭"
      >
        <X size={18} />
      </button>
    </div>
  );
}

function phaseLabel(phase: Phase): string {
  switch (phase) {
    case 'intent':
      return '步骤 1/4 · 设置报告意图';
    case 'reviewing-blueprint':
      return '步骤 2/4 · 审阅骨架';
    case 'drafting-sections':
      return '步骤 3/4 · 起草章节';
    case 'rendered':
      return '步骤 4/4 · 已完成';
    case 'failed':
      return '生成失败';
  }
}

interface ErrorBannerProps {
  message: string;
  onDismiss: () => void;
}

function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
      <AlertCircle size={16} className="mt-0.5 flex-shrink-0 text-red-500" />
      <p className="flex-1 text-[12px] text-red-700">{message}</p>
      <button
        type="button"
        onClick={onDismiss}
        className="text-red-400 transition hover:text-red-600"
        aria-label="关闭"
      >
        <X size={14} />
      </button>
    </div>
  );
}

interface IntentFormBlockProps {
  intent: IntentForm;
  onChange: (next: IntentForm) => void;
  onSubmit: () => void;
  busy: boolean;
}

function IntentFormBlock({ intent, onChange, onSubmit, busy }: IntentFormBlockProps) {
  return (
    <div className="space-y-4">
      <p className="text-[12.5px] leading-relaxed text-gray-600">
        告诉 AI 主理人这份报告的用途，它会先推一份骨架给你审阅。骨架确认后才会调豆包写正文 + 生成图表。
      </p>

      <div className="grid grid-cols-2 gap-3">
        <Field label="报告期间起" required>
          <input
            type="date"
            value={intent.periodStart}
            onChange={(e) => onChange({ ...intent, periodStart: e.target.value })}
            className="w-full rounded-lg border border-gray-200 px-3 py-2 text-[12px] focus:border-blue-500 focus:outline-none"
          />
        </Field>
        <Field label="报告期间止" required>
          <input
            type="date"
            value={intent.periodEnd}
            onChange={(e) => onChange({ ...intent, periodEnd: e.target.value })}
            className="w-full rounded-lg border border-gray-200 px-3 py-2 text-[12px] focus:border-blue-500 focus:outline-none"
          />
        </Field>
      </div>

      <Field label="报告意图（告诉 AI 这份报告要回答什么）">
        <textarea
          value={intent.intentHint}
          onChange={(e) => onChange({ ...intent, intentHint: e.target.value })}
          rows={2}
          placeholder="如：给客户的 Q1 战略陪伴报告，对外可呈交"
          className="w-full resize-none rounded-lg border border-gray-200 px-3 py-2 text-[12px] focus:border-blue-500 focus:outline-none"
        />
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label="目标读者">
          <input
            type="text"
            value={intent.audienceHint}
            onChange={(e) => onChange({ ...intent, audienceHint: e.target.value })}
            placeholder="如：客户决策层"
            className="w-full rounded-lg border border-gray-200 px-3 py-2 text-[12px] focus:border-blue-500 focus:outline-none"
          />
        </Field>
        <Field label="期望基调">
          <input
            type="text"
            value={intent.toneHint}
            onChange={(e) => onChange({ ...intent, toneHint: e.target.value })}
            placeholder="如：客观、克制、可执行"
            className="w-full rounded-lg border border-gray-200 px-3 py-2 text-[12px] focus:border-blue-500 focus:outline-none"
          />
        </Field>
      </div>

      <div className="flex items-center justify-between border-t border-gray-100 pt-4">
        <p className="text-[11px] text-gray-400">
          预计耗时：骨架 30 秒，全文 2-4 分钟
        </p>
        <button
          type="button"
          onClick={onSubmit}
          disabled={busy || !intent.periodStart || !intent.periodEnd}
          className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-[12.5px] font-medium text-white transition hover:bg-blue-700 disabled:bg-gray-300"
        >
          {busy ? (
            <>
              <Loader2 size={14} className="animate-spin" /> 草拟中…
            </>
          ) : (
            <>
              开始草拟骨架 <ChevronRight size={14} />
            </>
          )}
        </button>
      </div>
    </div>
  );
}

interface FieldProps {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}

function Field({ label, required, children }: FieldProps) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[11.5px] font-medium text-gray-600">
        {label}
        {required && <span className="ml-1 text-red-500">*</span>}
      </span>
      {children}
    </label>
  );
}

interface BlueprintReviewBlockProps {
  blueprint: ReportBlueprint;
  onConfirm: () => void;
  onRestart: () => void;
  busy: boolean;
}

function BlueprintReviewBlock({
  blueprint,
  onConfirm,
  onRestart,
  busy,
}: BlueprintReviewBlockProps) {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-blue-100 bg-blue-50/50 p-4">
        <h3 className="text-[14px] font-bold text-gray-900">{blueprint.title}</h3>
        {blueprint.subtitle && (
          <p className="mt-1 text-[12px] italic text-gray-600">{blueprint.subtitle}</p>
        )}
        <div className="mt-3 grid grid-cols-2 gap-2 text-[11.5px] text-gray-600">
          <div>
            <span className="text-gray-400">类型：</span>
            {blueprint.report_kind}
          </div>
          <div>
            <span className="text-gray-400">置信度：</span>
            <span className={confidenceColor(blueprint.confidence)}>
              {(blueprint.confidence * 100).toFixed(0)}%
            </span>
          </div>
          <div>
            <span className="text-gray-400">受众：</span>
            {blueprint.audience}
          </div>
          <div>
            <span className="text-gray-400">基调：</span>
            {blueprint.tone}
          </div>
          <div className="col-span-2">
            <span className="text-gray-400">推导主题：</span>
            {blueprint.inferred_theme}
          </div>
        </div>
      </div>

      <div>
        <h4 className="mb-2 text-[12px] font-medium text-gray-700">
          章节安排（共 {blueprint.sections.length} 节）
        </h4>
        <div className="space-y-2">
          {blueprint.sections.map((sec, i) => (
            <SectionPlanCard key={i} idx={i} plan={sec} />
          ))}
        </div>
      </div>

      {blueprint.open_questions_for_human.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
          <h4 className="mb-2 text-[12px] font-bold text-amber-900">
            主理人需要确认（{blueprint.open_questions_for_human.length}）
          </h4>
          <ul className="space-y-1">
            {blueprint.open_questions_for_human.map((q, i) => (
              <li key={i} className="text-[12px] text-amber-800">
                • {q}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[10.5px] text-amber-700/70">
            这些问题不会阻塞起草；AI 会基于现有素材尽量回答，缺失信息会在章节里 raise warning。
          </p>
        </div>
      )}

      <div className="flex items-center justify-between border-t border-gray-100 pt-4">
        <button
          type="button"
          onClick={onRestart}
          disabled={busy}
          className="text-[12px] text-gray-500 hover:text-gray-700"
        >
          ← 重新设置意图
        </button>
        <button
          type="button"
          onClick={onConfirm}
          disabled={busy}
          className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-[12.5px] font-medium text-white transition hover:bg-blue-700 disabled:bg-gray-300"
        >
          {busy ? (
            <>
              <Loader2 size={14} className="animate-spin" /> 启动中…
            </>
          ) : (
            <>
              确认骨架，开始起草 <ChevronRight size={14} />
            </>
          )}
        </button>
      </div>
    </div>
  );
}

function confidenceColor(confidence: number): string {
  if (confidence >= 0.8) return 'text-green-700 font-medium';
  if (confidence >= 0.6) return 'text-amber-700 font-medium';
  return 'text-red-700 font-medium';
}

interface SectionPlanCardProps {
  idx: number;
  plan: SectionPlan;
}

function SectionPlanCard({ idx, plan }: SectionPlanCardProps) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <h5 className="text-[12.5px] font-medium text-gray-900">
            {idx + 1}. {plan.title}
          </h5>
          {plan.goal && (
            <p className="mt-1 text-[11.5px] text-gray-500">{plan.goal}</p>
          )}
        </div>
        <span className="flex-shrink-0 text-[10.5px] text-gray-400">
          ≈ {plan.estimated_words} 字
        </span>
      </div>
      {(plan.chart_hints.length > 0 || plan.data_sources.length > 0) && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {plan.data_sources.map((ds, i) => (
            <span
              key={`ds-${i}`}
              className="rounded bg-gray-100 px-1.5 py-0.5 text-[10.5px] text-gray-600"
            >
              {ds}
            </span>
          ))}
          {plan.chart_hints.map((ch, i) => (
            <span
              key={`ch-${i}`}
              className="rounded bg-blue-100 px-1.5 py-0.5 text-[10.5px] text-blue-700"
            >
              📊 {ch.kind}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

interface DraftingProgressBlockProps {
  run: ReportRunSummary;
  onRender: () => void;
  allDone: boolean;
  busy: boolean;
}

function DraftingProgressBlock({
  run,
  onRender,
  allDone,
  busy,
}: DraftingProgressBlockProps) {
  const sections = run.blueprint?.sections || [];
  const statuses = run.sections_status || [];
  const doneCount = statuses.filter((s) => s === 'done').length;
  const failedCount = statuses.filter((s) => s === 'failed').length;

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-blue-100 bg-blue-50/50 p-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-[13px] font-bold text-gray-900">
              {run.blueprint?.title}
            </h3>
            <p className="mt-0.5 text-[11.5px] text-gray-500">
              共 {sections.length} 节 · 已完成 {doneCount} 节
              {failedCount > 0 && (
                <span className="text-red-600"> · {failedCount} 节失败</span>
              )}
            </p>
          </div>
          <ProgressBadge done={doneCount} total={sections.length} />
        </div>
      </div>

      <div className="space-y-2">
        {sections.map((sec, i) => (
          <SectionRow
            key={i}
            idx={i}
            plan={sec}
            status={statuses[i] || 'pending'}
          />
        ))}
      </div>

      <div className="flex items-center justify-between border-t border-gray-100 pt-4">
        <p className="text-[11px] text-gray-400">
          {allDone
            ? '全部章节已起草完成，可以渲染下载'
            : '章节正在并行起草，约需 2-4 分钟'}
        </p>
        <button
          type="button"
          onClick={onRender}
          disabled={!allDone || busy}
          className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-[12.5px] font-medium text-white transition hover:bg-blue-700 disabled:bg-gray-300"
        >
          {busy ? (
            <>
              <Loader2 size={14} className="animate-spin" /> 渲染中…
            </>
          ) : (
            <>
              <FileText size={14} />
              生成 docx
            </>
          )}
        </button>
      </div>
    </div>
  );
}

interface ProgressBadgeProps {
  done: number;
  total: number;
}

function ProgressBadge({ done, total }: ProgressBadgeProps) {
  const pct = total === 0 ? 0 : Math.round((done / total) * 100);
  return (
    <div className="text-right">
      <div className="text-[18px] font-bold text-blue-600">{pct}%</div>
      <div className="text-[10px] text-gray-400">
        {done}/{total}
      </div>
    </div>
  );
}

interface SectionRowProps {
  idx: number;
  plan: SectionPlan;
  status: ReportSectionStatus;
}

function SectionRow({ idx, plan, status }: SectionRowProps) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-gray-100 bg-white px-3 py-2.5">
      <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center">
        <SectionStatusIcon status={status} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[12px] font-medium text-gray-800">
          {idx + 1}. {plan.title}
        </p>
        <p className="truncate text-[10.5px] text-gray-400">{plan.goal}</p>
      </div>
      <span className={`flex-shrink-0 text-[10.5px] ${statusColor(status)}`}>
        {statusLabel(status)}
      </span>
    </div>
  );
}

function SectionStatusIcon({ status }: { status: ReportSectionStatus }) {
  switch (status) {
    case 'pending':
      return <div className="h-3 w-3 rounded-full bg-gray-300" />;
    case 'drafting':
      return <Loader2 size={16} className="animate-spin text-blue-500" />;
    case 'done':
      return <CheckCircle2 size={18} className="text-green-500" />;
    case 'failed':
      return <AlertCircle size={18} className="text-red-500" />;
  }
}

function statusLabel(status: ReportSectionStatus): string {
  switch (status) {
    case 'pending':
      return '排队中';
    case 'drafting':
      return '起草中';
    case 'done':
      return '已完成';
    case 'failed':
      return '失败';
  }
}

function statusColor(status: ReportSectionStatus): string {
  switch (status) {
    case 'pending':
      return 'text-gray-400';
    case 'drafting':
      return 'text-blue-600';
    case 'done':
      return 'text-green-600';
    case 'failed':
      return 'text-red-600';
  }
}

interface RenderedBlockProps {
  run: ReportRunSummary;
  onDownload: (format: ReportFileFormat) => void;
  onRenderOther: (format: ReportFileFormat) => void;
  busy: boolean;
  onRestart: () => void;
}

function RenderedBlock({
  run,
  onDownload,
  onRenderOther,
  busy,
  onRestart,
}: RenderedBlockProps) {
  const blueprint = run.blueprint!;
  const haveDocx = !!run.output_files?.docx;
  const haveMd = !!run.output_files?.md;
  const havePdf = !!run.output_files?.pdf;

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-green-200 bg-green-50/60 p-4">
        <div className="flex items-start gap-3">
          <CheckCircle2 size={22} className="mt-0.5 flex-shrink-0 text-green-600" />
          <div>
            <h3 className="text-[14px] font-bold text-gray-900">
              报告已生成
            </h3>
            <p className="mt-1 text-[12px] text-gray-600">
              {blueprint.title}（{blueprint.sections.length} 节）
            </p>
          </div>
        </div>
      </div>

      <div className="space-y-2">
        <FileRow
          label="Word 文档（.docx）"
          ready={haveDocx}
          onDownload={() => onDownload('docx')}
          onGenerate={() => onRenderOther('docx')}
          busy={busy}
        />
        <FileRow
          label="Markdown 归档（含 base64 内嵌图）"
          ready={haveMd}
          onDownload={() => onDownload('md')}
          onGenerate={() => onRenderOther('md')}
          busy={busy}
        />
        <FileRow
          label="PDF（需机器装 LibreOffice）"
          ready={havePdf}
          onDownload={() => onDownload('pdf')}
          onGenerate={() => onRenderOther('pdf')}
          busy={busy}
        />
      </div>

      <div className="flex items-center justify-between border-t border-gray-100 pt-4">
        <button
          type="button"
          onClick={onRestart}
          className="flex items-center gap-1 text-[12px] text-gray-500 hover:text-gray-700"
        >
          <RefreshCw size={12} /> 再生成一份
        </button>
        <p className="text-[10.5px] text-gray-400">
          report_id: {run.id.slice(0, 8)}…
        </p>
      </div>
    </div>
  );
}

interface FileRowProps {
  label: string;
  ready: boolean;
  onDownload: () => void;
  onGenerate: () => void;
  busy: boolean;
}

function FileRow({ label, ready, onDownload, onGenerate, busy }: FileRowProps) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-gray-200 bg-white px-3 py-2.5">
      <div className="flex items-center gap-3">
        <FileText size={16} className={ready ? 'text-blue-500' : 'text-gray-300'} />
        <span className={`text-[12px] ${ready ? 'text-gray-800' : 'text-gray-400'}`}>
          {label}
        </span>
      </div>
      {ready ? (
        <button
          type="button"
          onClick={onDownload}
          className="flex items-center gap-1 rounded-md bg-blue-50 px-2.5 py-1 text-[11.5px] font-medium text-blue-700 transition hover:bg-blue-100"
        >
          <Download size={12} /> 下载
        </button>
      ) : (
        <button
          type="button"
          onClick={onGenerate}
          disabled={busy}
          className="flex items-center gap-1 rounded-md border border-gray-200 px-2.5 py-1 text-[11.5px] text-gray-500 transition hover:bg-gray-50 disabled:opacity-50"
        >
          {busy ? <Loader2 size={12} className="animate-spin" /> : '生成'}
        </button>
      )}
    </div>
  );
}

interface FailedBlockProps {
  onRestart: () => void;
  message: string | null;
}

function FailedBlock({ onRestart, message }: FailedBlockProps) {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-red-200 bg-red-50 p-4">
        <div className="flex items-start gap-3">
          <AlertCircle size={22} className="mt-0.5 flex-shrink-0 text-red-600" />
          <div>
            <h3 className="text-[14px] font-bold text-gray-900">生成失败</h3>
            {message && (
              <p className="mt-1 text-[12px] text-gray-600">{message}</p>
            )}
            <p className="mt-2 text-[11px] text-gray-500">
              常见原因：豆包 API 暂时不可用、事件线数据为空、单节超时。可重试。
            </p>
          </div>
        </div>
      </div>
      <div className="flex justify-end">
        <button
          type="button"
          onClick={onRestart}
          className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-[12.5px] font-medium text-white transition hover:bg-blue-700"
        >
          <RefreshCw size={14} /> 重新开始
        </button>
      </div>
    </div>
  );
}
