import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  BrainCircuit, Sparkles, FileText, CheckCircle, MessageCircle,
  GitBranch, BookOpen, Award, Layers,
  AlertCircle, ClipboardList, Check, Folder, Target, FolderTree,
  Activity, Bot, Clock, PenLine, Calendar,
  ArrowLeft, AlertTriangle, ChevronRight, XCircle,
  Users, Flag, AlertOctagon, HelpCircle, CornerDownRight,
  RefreshCw, Star, Trash2
} from 'lucide-react';
import {
  getBrainDashboard,
  getClientDigitalAssets,
  getDigitalAssetDashboard,
  getStrategicThoughts,
  refreshClientDigitalAssetNarrative,
  refreshStrategicThoughts,
  reviewStrategicThought,
  updateStrategicThoughtState,
  type BrainDashboard,
  type BrainPulse,
  type DigitalAssetClientDetail,
  type DigitalAssetClientSummary,
  type DigitalAssetDashboard,
  type DigitalAssetMapNode,
  type DigitalAssetMetric,
  type DigitalAssetNarrative,
  type StrategicThought,
} from '../../lib/api';
import type { GrowthContextLink, Task } from '../../../shared/types';
import { StrategicLearningListPanel, type StrategicLearningTaskPayload } from './StrategicLearningListPanel';

const TABS = [
  { id: 'pulse', label: '大脑脉搏' },
  { id: 'thoughts', label: '思考与研判' },
  { id: 'clients', label: '数字资产中心' },
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

// --- Detail View Components ---

function DetailHeader({
  clientName,
  stageLabel,
  readinessScore,
  assetStage,
  assetTrackTitle,
  onBack,
}: {
  clientName: string;
  stageLabel: string;
  readinessScore: number | null;
  assetStage?: string;
  assetTrackTitle?: string;
  onBack: () => void;
}) {
  const badgeText = assetStage ? `${assetStage} · ${assetTrackTitle || '组织资产型'}` : `数字资产进度 ${readinessScore ?? '--'}%`;
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
          {badgeText}
        </div>
      </div>
    </header>
  );
}

const clampPercent = (value: number | null | undefined) => Math.max(0, Math.min(100, Number(value || 0)));

const metricValue = (metrics: DigitalAssetMetric[], key: string) => metrics.find((item) => item.key === key)?.value ?? 0;

const STAGE_ORDER = ['资料整理期', '组织画像期', '结构计算期', '机制洞察期', '机会生成期'];
const NODE_STAGE_ORDER = ['整理', '画像', '计算', '洞察', '机会'];

const stageRank = (stage: string | null | undefined) => Math.max(0, STAGE_ORDER.indexOf(stage || ''));

function AbilityLadder({ currentStage }: { currentStage: string }) {
  const current = stageRank(currentStage);
  return (
    <div className="flex flex-wrap items-center gap-2">
      {NODE_STAGE_ORDER.map((label, index) => (
        <div key={label} className="flex items-center gap-2">
          <span className={`rounded-full border px-2.5 py-1 text-[11px] font-bold ${
            index <= current
              ? 'border-blue-100 bg-blue-50 text-blue-600'
              : 'border-slate-100 bg-white text-slate-400'
          }`}>
            {label}
          </span>
          {index < NODE_STAGE_ORDER.length - 1 && <ChevronRight size={12} className="text-slate-300" />}
        </div>
      ))}
    </div>
  );
}

const nodeMaturityPercent = (node: DigitalAssetMapNode) => Math.max(0, Math.min(100, Math.round(node.maturityPercent ?? node.coverageScore ?? 0)));

const maturityBarClass = (value: number) => {
  if (value >= 75) return 'bg-emerald-500';
  if (value >= 50) return 'bg-blue-500';
  if (value >= 30) return 'bg-amber-500';
  return 'bg-rose-500';
};

function AssetMaturityRows({ nodes }: { nodes: DigitalAssetMapNode[] }) {
  const [expanded, setExpanded] = useState(false);
  const visibleNodes = expanded ? nodes : nodes.slice(0, 8);
  return (
    <section className="mt-8">
      <div className="flex items-baseline justify-between mb-4 px-1">
        <div>
          <h2 className="text-[15px] font-bold text-slate-800">资料成熟度进度条</h2>
          <p className="mt-1 text-[12px] text-slate-400">百分比表示资料质量成熟度，不按文件数量直接打分。</p>
        </div>
        <span className="text-[12px] font-bold text-blue-600">资料类型 {nodes.length}</span>
      </div>
      <div className="rounded-[24px] border border-slate-100 bg-white p-4 shadow-[0_2px_10px_rgba(0,0,0,0.02)]">
        <div className="space-y-3">
          {visibleNodes.map((node) => {
            const maturity = nodeMaturityPercent(node);
            return (
              <div key={node.key} className="rounded-[18px] border border-slate-100 bg-slate-50/50 px-4 py-4">
                <div className="grid grid-cols-1 xl:grid-cols-[200px_minmax(240px,1fr)] gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      {maturity >= 50 ? <CheckCircle size={14} className="text-emerald-500 shrink-0" /> : <AlertCircle size={14} className="text-amber-500 shrink-0" />}
                      <span className="text-[14px] font-bold text-slate-800">{node.label}</span>
                    </div>
                    <p className="mt-1 text-[11px] leading-[1.6] text-slate-400">{node.description}</p>
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-3">
                      <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-200/70">
                        <div className={`h-full rounded-full ${maturityBarClass(maturity)}`} style={{ width: `${maturity}%` }} />
                      </div>
                      <span className="w-11 text-right text-[13px] font-bold tabular-nums text-slate-800">{maturity}%</span>
                    </div>
                    <div className="mt-3 grid grid-cols-1 lg:grid-cols-2 gap-3">
                      <div>
                        <div className="text-[10px] font-bold text-emerald-600">已看到</div>
                        <p className="mt-1 text-[12px] leading-[1.75] text-slate-600">{node.seenSummary || '已看到部分资料线索。'}</p>
                      </div>
                      <div>
                        <div className="text-[10px] font-bold text-amber-600">还缺</div>
                        <p className="mt-1 text-[12px] leading-[1.75] text-slate-600">{node.missingSummary || '还缺一份能持续复盘这类资料的整理表。'}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        {nodes.length > 8 && (
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            className="mt-4 w-full rounded-[14px] border border-slate-100 bg-white px-4 py-2 text-[12px] font-bold text-blue-600 hover:bg-blue-50 transition-colors"
          >
            {expanded ? '收起资料类型' : `查看更多资料类型（${nodes.length - 8}）`}
          </button>
        )}
      </div>
    </section>
  );
}

function DigitalAssetMetricStrip({ metrics }: { metrics: DigitalAssetMetric[] }) {
  const visible = metrics.filter((metric) => ['documents', 'memoryFacts', 'eventLines', 'evidenceCards', 'themeClusters', 'openQuestions', 'judgments'].includes(metric.key));
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-2.5">
      {visible.map((metric) => (
        <div key={metric.key} className="rounded-[16px] border border-slate-100 bg-white/80 px-3.5 py-3">
          <div className="text-[10px] font-bold text-slate-400">{metric.label}</div>
          <div className="mt-1 flex items-baseline gap-1.5">
            <span className="text-[20px] font-bold text-slate-800 tabular-nums">{metric.value}</span>
            {metric.hint && <span className="text-[10px] font-semibold text-slate-400">{metric.hint}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

function formatNarrativeTime(value?: string | null) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function narrativeAuditCounts(narrative?: DigitalAssetNarrative | null) {
  const counts = narrative?.materialAudit?.counts;
  if (!counts || typeof counts !== 'object') return [];
  const source = counts as Record<string, unknown>;
  const items = [
    ['documents', '原始资料'],
    ['v2Documents', '结构化资料'],
    ['v2Ready', '已解析'],
    ['eventLines', '事件线'],
    ['tasks', '任务'],
    ['meetings', '会议'],
    ['judgmentVersions', '判断版本'],
  ] as const;
  return items
    .map(([key, label]) => ({ key, label, value: Number(source[key] || 0) }))
    .filter((item) => item.value > 0);
}

function DigitalAssetNarrativeMarkdown({ content }: { content: string }) {
  const lines = content.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (!lines.length) return null;
  return (
    <div className="space-y-3 text-[14px] leading-[1.9] text-slate-700">
      {lines.map((line, index) => {
        const heading = line.replace(/^#{1,3}\s*/, '');
        if (/^#{1,3}\s+/.test(line)) {
          return <h4 key={`${line}-${index}`} className="pt-2 text-[13px] font-bold text-slate-900">{heading}</h4>;
        }
        const bullet = line.replace(/^[-*]\s+/, '').replace(/^\d+[.、]\s*/, '');
        if (bullet !== line) {
          return (
            <p key={`${line}-${index}`} className="pl-3 border-l-2 border-blue-100 text-slate-700">
              {bullet}
            </p>
          );
        }
        return <p key={`${line}-${index}`}>{line}</p>;
      })}
    </div>
  );
}

function DigitalAssetNarrativePanel({
  narrative,
  loading,
  error,
  onRefresh,
}: {
  narrative?: DigitalAssetNarrative | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}) {
  const counts = narrativeAuditCounts(narrative);
  const hasContent = Boolean(narrative?.contentMarkdown?.trim());
  return (
    <section className="rounded-[24px] border border-blue-100 bg-white px-5 py-5 sm:px-6 shadow-[0_8px_28px_rgba(15,23,42,0.04)]">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-blue-600" />
            <h3 className="text-[15px] font-bold text-slate-900">系统读完资料后的判断</h3>
          </div>
          <p className="mt-1 text-[12px] text-slate-400">
            {hasContent ? `生成时间 ${formatNarrativeTime(narrative?.generatedAt)}` : '还没有生成资料体检内容'}
          </p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className="inline-flex h-9 items-center justify-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-4 text-[12px] font-bold text-blue-600 transition-colors hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          {hasContent ? '重新生成' : '生成内容'}
        </button>
      </div>

      {error && (
        <div className="mt-4 rounded-[16px] border border-amber-100 bg-amber-50 px-4 py-3 text-[12px] font-medium leading-relaxed text-amber-700">
          {error}
        </div>
      )}

      {hasContent ? (
        <div className="mt-5 space-y-5">
          {counts.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {counts.map((item) => (
                <span key={item.key} className="rounded-full bg-slate-50 px-3 py-1 text-[11px] font-semibold text-slate-500">
                  {item.label} {item.value.toLocaleString()}
                </span>
              ))}
            </div>
          )}
          <DigitalAssetNarrativeMarkdown content={narrative?.contentMarkdown || ''} />
          {(narrative?.qualityWarnings || []).length > 0 && (
            <div className="border-t border-slate-100 pt-4">
              <div className="mb-2 text-[12px] font-bold text-slate-500">资料质量提示</div>
              <div className="space-y-1.5">
                {(narrative?.qualityWarnings || []).slice(0, 4).map((warning, index) => (
                  <p key={`${warning}-${index}`} className="text-[12px] leading-relaxed text-slate-500">
                    {warning}
                  </p>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="mt-5 rounded-[18px] bg-slate-50 px-4 py-4 text-[13px] leading-relaxed text-slate-500">
          点击生成内容后，系统会读取当前客户的数据中心资料，给出一段更直白的资料体检说明。
        </div>
      )}
    </section>
  );
}

function DigitalAssetDetailView({ clientId, onBack }: { clientId: string; onBack: () => void }) {
  const [detail, setDetail] = useState<DigitalAssetClientDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [narrativeLoading, setNarrativeLoading] = useState(false);
  const [narrativeError, setNarrativeError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);
    setNarrativeError(null);
    getClientDigitalAssets(clientId)
      .then((result) => {
        if (!mounted) return;
        setDetail(result);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : '加载失败');
        setDetail(null);
      })
      .finally(() => {
        if (!mounted) return;
        setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [clientId]);

  const handleRefreshNarrative = useCallback(async () => {
    setNarrativeLoading(true);
    setNarrativeError(null);
    try {
      const narrative = await refreshClientDigitalAssetNarrative(clientId);
      setDetail((current) => current ? { ...current, aiNarrative: narrative } : current);
    } catch (err) {
      setNarrativeError(err instanceof Error ? err.message : '生成失败，已保留旧内容。');
    } finally {
      setNarrativeLoading(false);
    }
  }, [clientId]);

  if (loading) {
    return (
      <div className="animate-in fade-in duration-300">
        <DetailHeader clientName="数字资产中心" stageLabel="加载中" readinessScore={null} onBack={onBack} />
        <div className="max-w-full mx-auto px-6 py-8 pb-24 text-[13px] text-slate-500">正在计算组织数字资产...</div>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="animate-in fade-in duration-300">
        <DetailHeader clientName="数字资产中心" stageLabel="资料不足" readinessScore={null} onBack={onBack} />
        <div className="max-w-full mx-auto px-6 py-8 pb-24">
          <div className="rounded-2xl border border-amber-100 bg-amber-50 px-5 py-4">
            <p className="text-[14px] font-bold text-amber-700">暂时无法生成数字资产中心</p>
            <p className="text-[13px] mt-2 text-amber-700/80">建议先补充资料或稍后重试。{error ? `（${error}）` : ''}</p>
          </div>
        </div>
      </div>
    );
  }

  const documentCount = metricValue(detail.sourceMetrics, 'documents');
  const memoryCount = metricValue(detail.sourceMetrics, 'memoryFacts');
  const evidenceCount = metricValue(detail.sourceMetrics, 'evidenceCards');

  return (
    <div className="animate-in fade-in duration-300">
      <DetailHeader
        clientName={detail.name}
        stageLabel={detail.stage || '待判断'}
        readinessScore={detail.stageProgress}
        assetStage={detail.assetStage}
        assetTrackTitle={detail.assetTrackTitle}
        onBack={onBack}
      />
      <div className="max-w-full mx-auto px-6 py-8 pb-24">
        <section
          className="rounded-[28px] border border-blue-100 p-6 sm:p-8 relative overflow-hidden"
          style={{
            backgroundImage: 'linear-gradient(135deg, rgba(37,99,235,0.08), rgba(20,184,166,0.06) 42%, rgba(255,255,255,0) 78%), linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)',
            boxShadow: '0 10px 40px -10px rgba(15,23,42,0.08)'
          }}
        >
          <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-8">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-1.5 bg-blue-50/80 border border-blue-100/80 rounded-full px-3.5 py-1.5 mb-5 shadow-sm">
                <BrainCircuit size={14} className="text-blue-600" />
                <span className="text-[12px] font-bold text-blue-600 tracking-wide">组织资产阶段</span>
              </div>
              <h2 className="text-[24px] font-bold text-slate-900 tracking-tight mb-3">
                {detail.assetStage} · {detail.assetTrackTitle}
              </h2>
              <p className="text-[14px] leading-[1.9] text-slate-700 font-medium">
                {detail.understandingStatement}
              </p>
            </div>
            <div className="grid grid-cols-3 gap-2.5 min-w-[320px]">
              {[
                { label: '沉淀经验', value: `${detail.depositXp} XP`, icon: Award },
                { label: '下一阶段', value: detail.nextStage || '继续沉淀', icon: Target },
                { label: '成长模式', value: detail.growthMode || '均衡成长', icon: Layers },
                { label: '证据卡', value: evidenceCount.toLocaleString(), icon: CheckCircle },
                { label: '资料沉淀', value: documentCount.toLocaleString(), icon: FileText },
                { label: '组织记忆', value: memoryCount.toLocaleString(), icon: BrainCircuit },
              ].map((item) => (
                <div key={item.label} className="rounded-[18px] bg-white/80 border border-slate-100 px-4 py-3 shadow-sm">
                  <div className="flex items-center gap-1.5 text-[10px] font-bold text-slate-400">
                    <item.icon size={12} />
                    {item.label}
                  </div>
                  <div className="mt-1 text-[20px] font-bold text-slate-800 tabular-nums">{item.value}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mt-6">
          <DigitalAssetNarrativePanel
            narrative={detail.aiNarrative}
            loading={narrativeLoading}
            error={narrativeError}
            onRefresh={handleRefreshNarrative}
          />
        </section>

        <section className="mt-6">
          <DigitalAssetMetricStrip metrics={detail.sourceMetrics} />
        </section>

        <AssetMaturityRows nodes={detail.assetMapNodes || []} />
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

const getThoughtStatusMeta = (thought: StrategicThought): { text: string; className: string } | null => {
  if (thought.status === 'confirmed') return { text: '已确认', className: 'bg-emerald-50 text-emerald-600 border border-emerald-100' };
  if (thought.status === 'task_created') return { text: '已转任务', className: 'bg-blue-50 text-blue-600 border border-blue-100' };
  if (thought.isSystem || thought.scope === 'system') return { text: '系统观察', className: 'bg-slate-100 text-slate-500 border border-slate-200' };
  return null;
};

const INSIGHT_TYPE_META: Record<string, { text: string; className: string }> = {
  strategic_shift: { text: '战略转型', className: 'bg-blue-50 text-blue-600 border border-blue-100' },
  risk_signal: { text: '风险研判', className: 'bg-rose-50 text-rose-600 border border-rose-100' },
  opportunity_window: { text: '机会窗口', className: 'bg-emerald-50 text-emerald-600 border border-emerald-100' },
  execution_bottleneck: { text: '执行瓶颈', className: 'bg-amber-50 text-amber-600 border border-amber-100' },
  narrative_upgrade: { text: '叙事升级', className: 'bg-violet-50 text-violet-600 border border-violet-100' },
  operating_model: { text: '运营模型', className: 'bg-cyan-50 text-cyan-600 border border-cyan-100' },
};

const getInsightTypeMeta = (thought: StrategicThought): { text: string; className: string } => {
  if (thought.insightType && INSIGHT_TYPE_META[thought.insightType]) return INSIGHT_TYPE_META[thought.insightType];
  return { text: '分析信号', className: 'bg-slate-50 text-slate-500 border border-slate-100' };
};

function ThoughtCard({
  thought,
  onCreateTask,
  onReview,
  onToggleFavorite,
  onDelete,
}: {
  thought: StrategicThought;
  onCreateTask?: (payload: ThoughtTaskPayload) => void;
  onReview: (thoughtId: string, action: 'confirm' | 'dismiss', note: string) => Promise<void>;
  onToggleFavorite: (thought: StrategicThought) => Promise<void>;
  onDelete: (thought: StrategicThought) => Promise<void>;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [reviewText, setReviewText] = useState(thought.review?.note || '');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const statusMeta = getThoughtStatusMeta(thought);
  const typeMeta = getInsightTypeMeta(thought);
  const normalizedLine = _normalizeTextForUI(thought.line) || '系统发现一条分析信号';
  const normalizedInsight = _normalizeTextForUI(thought.insightText || thought.observation) || '系统发现一条值得关注的客户洞察。';
  const normalizedFuture = _normalizeTextForUI(thought.futureJudgment || thought.whyItMatters || '');
  const normalizedAction = _normalizeTextForUI(thought.recommendedAction || thought.suggestion) || '建议将这条洞察转成下一步行动。';

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
      suggestion: normalizedAction,
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
          <div className="w-2 h-2 rounded-full mt-1.5 bg-blue-500" />
          <div>
            <span className={`text-[13px] font-bold ${thought.isSystem ? 'text-slate-600' : 'text-slate-800'}`}>{normalizedLine}</span>
            {thought.clientName && thought.clientName !== '系统观察' && (
              <p className="text-[11px] text-slate-400 mt-1">{thought.clientName}</p>
            )}
          </div>
        </div>
        <div className="flex flex-wrap justify-end items-center gap-2 shrink-0">
          <div className={`px-2.5 py-1 rounded-lg text-[10px] font-bold tracking-wide ${typeMeta.className}`}>
            {typeMeta.text}
          </div>
          {statusMeta && (
            <div className={`px-2.5 py-1 rounded-lg text-[10px] font-bold tracking-wide ${statusMeta.className}`}>
              {statusMeta.text}
            </div>
          )}
          <button
            type="button"
            onClick={() => void onToggleFavorite(thought)}
            className={`h-7 w-7 inline-flex items-center justify-center rounded-full border transition-colors ${
              thought.isFavorite
                ? 'border-amber-200 bg-amber-50 text-amber-500'
                : 'border-slate-200 bg-white text-slate-400 hover:text-amber-500 hover:border-amber-200'
            }`}
            title={thought.isFavorite ? '取消收藏' : '收藏'}
            aria-label={thought.isFavorite ? '取消收藏' : '收藏'}
          >
            <Star size={14} fill={thought.isFavorite ? 'currentColor' : 'none'} />
          </button>
          <button
            type="button"
            onClick={() => void onDelete(thought)}
            className="h-7 w-7 inline-flex items-center justify-center rounded-full border border-slate-200 bg-white text-slate-400 hover:text-rose-500 hover:border-rose-200 transition-colors"
            title="删除"
            aria-label="删除"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>
      <div className="mb-5">
        <p className="text-[13px] leading-[1.9] text-slate-700 font-medium">{normalizedInsight}</p>
      </div>
      {(normalizedFuture || normalizedAction) && (
        <div className="grid grid-cols-1 gap-3 mb-5">
          {normalizedFuture && (
            <div className="rounded-[16px] bg-slate-50 px-4 py-3">
              <div className="text-[10px] font-bold text-slate-400 mb-1">未来判断</div>
              <p className="text-[12px] leading-[1.7] text-slate-700">{normalizedFuture}</p>
            </div>
          )}
          {normalizedAction && (
            <div className="rounded-[16px] bg-blue-50/70 px-4 py-3">
              <div className="text-[10px] font-bold text-blue-500 mb-1">建议动作</div>
              <p className="text-[12px] leading-[1.7] text-slate-700">{normalizedAction}</p>
            </div>
          )}
        </div>
      )}

      <div className="mt-5 pt-4 border-t border-slate-50 space-y-3">
        {(thought.review?.note || reviewText) && (
          <div className="bg-slate-50 rounded-[14px] px-4 py-3">
            <div className="text-[11px] font-semibold text-slate-500 mb-1">
              {thought.review?.status === 'confirmed' ? '我的已确认判断' : '我的备注'}
            </div>
            <div className="text-[12px] leading-[1.7] text-slate-700">{thought.review?.note || reviewText}</div>
          </div>
        )}

        {isEditing ? (
          <div className="bg-slate-50 rounded-[18px] p-4">
            <textarea
              className="w-full min-h-[72px] border border-slate-200 rounded-[14px] p-3 text-[13px] text-slate-700 bg-white resize-y outline-none focus:border-blue-300 focus:ring-1 focus:ring-blue-100"
              placeholder="补充你对这条洞察的判断..."
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
                不准确
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
                采纳为判断
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
              采纳/备注...
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
  selectedClientName,
  selectedProjectModuleId,
  selectedProjectModuleName,
  onReview,
  onCreateTask,
  onRetry,
  onRefresh,
  onToggleFavorite,
  onDelete,
  refreshing,
}: {
  thoughts: StrategicThought[];
  loading: boolean;
  error: string | null;
  selectedClientId: string | null;
  selectedClientName?: string | null;
  selectedProjectModuleId?: string | null;
  selectedProjectModuleName?: string | null;
  onReview: (thoughtId: string, action: 'confirm' | 'dismiss', note: string) => Promise<void>;
  onCreateTask?: (payload: ThoughtTaskPayload) => void;
  onRetry: () => void;
  onRefresh: () => Promise<void>;
  onToggleFavorite: (thought: StrategicThought) => Promise<void>;
  onDelete: (thought: StrategicThought) => Promise<void>;
  refreshing: boolean;
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
      <div className="bg-white border border-slate-100 rounded-[20px] px-5 py-6">
        <p className="text-[13px] leading-7 text-slate-500">
          {selectedClientId
            ? `${selectedProjectModuleName || selectedClientName || '这个客户'}当前还没有足够材料形成高价值研判。`
            : '当前还没有足够材料形成高价值研判。'}
        </p>
        {selectedClientId && (
          <button
            type="button"
            onClick={() => void onRefresh()}
            disabled={refreshing}
            className="mt-3 inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-4 py-2 text-[12px] font-bold text-blue-600 hover:bg-blue-100 disabled:opacity-60"
          >
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            {refreshing ? '正在刷新研判' : '刷新研判'}
          </button>
        )}
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between gap-3 px-1">
        <div className="text-[12px] text-slate-400">
          {selectedProjectModuleId
            ? `${selectedProjectModuleName || '当前项目'} · ${thoughts.length} 条洞察`
            : selectedClientId
              ? `${selectedClientName || '当前客户'} · ${thoughts.length} 条洞察`
              : `全部客户 · ${thoughts.length} 条洞察`}
        </div>
        {selectedClientId && (
          <button
            type="button"
            onClick={() => void onRefresh()}
            disabled={refreshing}
            className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-white px-4 py-2 text-[12px] font-bold text-blue-600 hover:bg-blue-50 disabled:opacity-60"
          >
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            {refreshing ? '刷新中' : '刷新研判'}
          </button>
        )}
      </div>
      <div className="columns-1 md:columns-2 gap-5 space-y-5">
        {thoughts.map((thought) => (
          <ThoughtCard
            key={thought.id}
            thought={thought}
            onCreateTask={onCreateTask}
            onReview={onReview}
            onToggleFavorite={onToggleFavorite}
            onDelete={onDelete}
          />
        ))}
      </div>
    </div>
  );
}

function ThoughtScopeSelect({
  clients,
  selectedClientId,
  onChange,
  disabled,
}: {
  clients: Array<{ id: string; name: string }>;
  selectedClientId: string;
  onChange: (clientId: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white/90 px-3 py-2 shadow-sm">
      <Users size={15} className="text-blue-500 shrink-0" />
      <span className="text-[12px] font-semibold text-slate-500 whitespace-nowrap">客户/项目</span>
      <select
        value={selectedClientId}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        className="min-w-[130px] max-w-[220px] bg-transparent text-[13px] font-semibold text-slate-700 outline-none disabled:opacity-50"
      >
        <option value="">全部客户</option>
        {clients.map((client) => (
          <option key={client.id} value={client.id}>
            {client.name}
          </option>
        ))}
      </select>
    </div>
  );
}

function DigitalAssetsTab({ onOpenDetail, clients }: { onOpenDetail: (clientId: string) => void; clients: DigitalAssetClientSummary[] }) {
  const sorted = [...clients].sort((a, b) => {
    const stageDiff = stageRank(b.assetStage) - stageRank(a.assetStage);
    if (stageDiff !== 0) return stageDiff;
    return (b.depositXp || 0) - (a.depositXp || 0);
  });
  if (!clients.length) {
    return (
      <div className="bg-white border border-slate-100 rounded-[24px] px-6 py-8">
        <p className="text-[14px] font-bold text-slate-700">还没有可形成数字资产的组织资料</p>
        <p className="text-[13px] leading-7 text-slate-500 mt-2">建议先建立客户/组织空间，并上传项目介绍、流程资料、反馈表和评估材料。</p>
      </div>
    );
  }
  return (
    <div>
      <div className="rounded-[28px] border border-blue-100 bg-white p-6 mb-6 shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
        <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
          <div>
            <h2 className="text-[18px] font-bold text-slate-900 flex items-center gap-2">
              <FolderTree size={19} className="text-blue-500" /> 组织数字资产概览
            </h2>
            <p className="text-[13px] leading-7 text-slate-500 mt-2 max-w-3xl">
              这里展示每个组织已经沉淀了哪些长期可复用资产，以及下一步该补什么，才能让 AI 更理解组织。
            </p>
          </div>
          <div className="flex items-center gap-2 text-[12px] font-bold text-slate-400">
            <Layers size={14} />
            目前收录 {clients.length} 个组织空间
          </div>
        </div>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        {sorted.map((client) => {
          const documentCount = metricValue(client.metrics, 'documents');
          const memoryCount = metricValue(client.metrics, 'memoryFacts');
          const evidenceCount = metricValue(client.metrics, 'evidenceCards');
          const primaryGap = client.criticalGaps[0] || '继续提高资料的连续性和结构化程度。';
          const primaryDeposit = client.nextBestDeposits?.[0]?.title || client.nextDeposits[0] || '持续沉淀项目介绍、流程、反馈和评估材料。';
          return (
          <div
            key={client.id}
            onClick={() => onOpenDetail(client.id)}
            className="bg-white rounded-[24px] border border-slate-100 p-6 shadow-[0_2px_10px_rgba(0,0,0,0.02)] hover:shadow-[0_8px_30px_rgba(0,0,0,0.05)] hover:border-blue-200 transition-all duration-300 cursor-pointer group"
          >
            <div className="flex flex-col mb-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-[16px] font-bold text-slate-800 group-hover:text-blue-600 transition-colors">{client.name}</h3>
                <span className="bg-blue-50 border border-blue-100 text-blue-600 text-[11px] font-bold px-2.5 py-1 rounded-lg">
                  {client.assetStage || '资料整理期'}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <div className="min-w-[112px] rounded-full border border-slate-100 bg-slate-50 px-2.5 py-1 text-[11px] font-bold text-slate-600">
                  {client.assetTrackTitle || '组织资产型'}
                </div>
                <div className="h-1.5 bg-slate-100 rounded-full w-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-1000 ease-out"
                    style={{ width: `${clampPercent(client.stageProgress)}%`, backgroundColor: getConfColor(client.stageProgress) }}
                  />
                </div>
                <span className="text-[12px] font-bold tabular-nums w-10 text-right" style={{ color: getConfColor(client.stageProgress) }}>
                  {client.stageProgress}%
                </span>
              </div>
            </div>
            <div className="mb-4 flex flex-wrap gap-2">
              <span className="rounded-full bg-blue-50 border border-blue-100 px-2.5 py-1 text-[11px] font-bold text-blue-600">
                沉淀经验 {client.depositXp || 0} XP
              </span>
              <span className="rounded-full bg-emerald-50 border border-emerald-100 px-2.5 py-1 text-[11px] font-bold text-emerald-600">
                {client.growthMode || '均衡成长'}
              </span>
              <span className="rounded-full bg-amber-50 border border-amber-100 px-2.5 py-1 text-[11px] font-bold text-amber-600">
                下一阶段 {client.nextStage || '继续沉淀'}
              </span>
              {client.strongestDimensions.slice(0, 2).map((dimension) => (
                <span key={dimension} className="rounded-full bg-slate-50 border border-slate-100 px-2.5 py-1 text-[11px] font-bold text-slate-500">
                  {dimension}
                </span>
              ))}
            </div>
            <p className="text-[13px] leading-[1.8] text-slate-600 font-medium mb-5 line-clamp-3">
              {client.understandingStatement || client.intro || 'AI 对这个组织还处在初步理解阶段。'}
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5 mb-5">
              <div className="rounded-[16px] bg-emerald-50/70 px-3 py-2.5">
                <div className="text-[10px] font-bold text-emerald-600 mb-1">已形成价值</div>
                <p className="text-[11px] leading-[1.6] text-slate-600 line-clamp-3">{client.highValueSignals[0] || '等待更多资料形成长期价值判断。'}</p>
              </div>
              <div className="rounded-[16px] bg-amber-50/80 px-3 py-2.5">
                <div className="text-[10px] font-bold text-amber-600 mb-1">关键缺口</div>
                <p className="text-[11px] leading-[1.6] text-slate-600 line-clamp-3">{client.stageBlockers?.[0] || primaryGap}</p>
              </div>
              <div className="rounded-[16px] bg-blue-50/70 px-3 py-2.5">
                <div className="text-[10px] font-bold text-blue-600 mb-1">下一步沉淀</div>
                <p className="text-[11px] leading-[1.6] text-slate-600 line-clamp-3">{primaryDeposit}</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-2 pt-4 border-t border-slate-50">
              {[
                { icon: Folder, label: `${documentCount} 资料` },
                { icon: BrainCircuit, label: `${memoryCount} 记忆` },
                { icon: CheckCircle, label: `${evidenceCount} 证据卡` },
                { icon: ChevronRight, label: '查看详情' },
              ].map((metric, idx) => (
                <span key={idx} className="text-[11px] font-bold text-slate-400 flex items-center gap-1.5">
                  <metric.icon size={12} className="text-slate-300" />
                  {metric.label}
                </span>
              ))}
            </div>
          </div>
          );
        })}
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
  clients = [],
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
  const [activeTab, setActiveTab] = useState('pulse');
  const [viewState, setViewState] = useState<{ type: 'tabs'; detailId: null } | { type: 'detail'; detailId: string }>({ type: 'tabs', detailId: null });
  const [dashboard, setDashboard] = useState<BrainDashboard | null>(null);
  const [assetDashboard, setAssetDashboard] = useState<DigitalAssetDashboard | null>(null);
  const [thoughts, setThoughts] = useState<StrategicThought[]>([]);
  const [thoughtsLoading, setThoughtsLoading] = useState(false);
  const [thoughtsError, setThoughtsError] = useState<string | null>(null);
  const [thoughtClientId, setThoughtClientId] = useState(currentClientId || '');
  const [thoughtsRefreshing, setThoughtsRefreshing] = useState(false);

  const thoughtClientOptions = useMemo(() => {
    const map = new Map<string, { id: string; name: string }>();
    for (const client of dashboard?.clients ?? []) {
      if (client.id && client.name) map.set(client.id, { id: client.id, name: client.name });
    }
    for (const client of clients) {
      if (client.id && client.name && !map.has(client.id)) map.set(client.id, { id: client.id, name: client.name });
    }
    return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name, 'zh-Hans-CN'));
  }, [clients, dashboard?.clients]);

  const selectedThoughtClient = useMemo(
    () => thoughtClientOptions.find((client) => client.id === thoughtClientId) || null,
    [thoughtClientId, thoughtClientOptions],
  );

  useEffect(() => {
    getBrainDashboard()
      .then(setDashboard)
      .catch(() => setDashboard(null));
    getDigitalAssetDashboard()
      .then(setAssetDashboard)
      .catch(() => setAssetDashboard(null));
  }, []);

  useEffect(() => {
    if (currentClientId && !thoughtClientId) {
      setThoughtClientId(currentClientId);
    }
  }, [currentClientId, thoughtClientId]);

  const loadThoughts = useCallback(async () => {
    setThoughtsLoading(true);
    setThoughtsError(null);
    try {
      const response = await getStrategicThoughts({
        clientId: thoughtClientId || null,
        limit: thoughtClientId ? 12 : 24,
      });
      setThoughts(response.items || []);
    } catch (error) {
      setThoughtsError(error instanceof Error ? error.message : '未知错误');
      setThoughts([]);
    } finally {
      setThoughtsLoading(false);
    }
  }, [thoughtClientId]);

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

  const handleRefreshThoughts = useCallback(async () => {
    if (!thoughtClientId) return;
    setThoughtsRefreshing(true);
    setThoughtsError(null);
    try {
      const response = await refreshStrategicThoughts({
        clientId: thoughtClientId,
        limit: 8,
      });
      setThoughts(response.items || []);
      flash?.('success', '研判已刷新');
    } catch (error) {
      setThoughtsError(error instanceof Error ? error.message : '刷新失败');
    } finally {
      setThoughtsRefreshing(false);
    }
  }, [flash, thoughtClientId]);

  const handleToggleFavoriteThought = useCallback(
    async (thought: StrategicThought) => {
      await updateStrategicThoughtState(thought.id, { action: thought.isFavorite ? 'unfavorite' : 'favorite' });
      await loadThoughts();
    },
    [loadThoughts],
  );

  const handleDeleteThought = useCallback(
    async (thought: StrategicThought) => {
      await updateStrategicThoughtState(thought.id, { action: 'delete' });
      await loadThoughts();
    },
    [loadThoughts],
  );

  if (viewState.type === 'detail') {
    return (
      <div className="h-full flex flex-col bg-white/50 overflow-y-auto">
        <DigitalAssetDetailView clientId={viewState.detailId} onBack={() => setViewState({ type: 'tabs', detailId: null })} />
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
          {activeTab === 'thoughts' && (
            <ThoughtScopeSelect
              clients={thoughtClientOptions}
              selectedClientId={thoughtClientId}
              disabled={thoughtsLoading && !thoughtClientOptions.length}
              onChange={(clientId) => {
                setThoughtClientId(clientId);
                if (clientId) onClientChange?.(clientId);
              }}
            />
          )}
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
              selectedClientId={thoughtClientId || null}
              selectedClientName={selectedThoughtClient?.name || null}
              selectedProjectModuleId={null}
              selectedProjectModuleName={null}
              onReview={handleThoughtReview}
              onCreateTask={onCreateTaskFromThought}
              onRetry={() => void loadThoughts()}
              onRefresh={handleRefreshThoughts}
              onToggleFavorite={handleToggleFavoriteThought}
              onDelete={handleDeleteThought}
              refreshing={thoughtsRefreshing}
            />
          )}
          {activeTab === 'clients' && <DigitalAssetsTab clients={assetDashboard?.clients ?? []} onOpenDetail={(clientId) => setViewState({ type: 'detail', detailId: clientId })} />}
          {activeTab === 'learning' && (
            <StrategicLearningListPanel
              currentClientId={null}
              currentClientName={null}
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
