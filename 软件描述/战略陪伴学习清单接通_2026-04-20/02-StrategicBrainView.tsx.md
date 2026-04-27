# src/renderer/components/strategic_accompaniment/StrategicBrainView.tsx

```tsx
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
```
