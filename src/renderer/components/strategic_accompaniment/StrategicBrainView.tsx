import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  BrainCircuit, Sparkles, FileText, CheckCircle,
  GitBranch, Award, Layers,
  AlertCircle, ClipboardList, Check, Folder, Target, FolderTree,
  Activity, Bot, PenLine, Calendar,
  ArrowLeft, AlertTriangle, ChevronRight, XCircle,
  Users, Flag, AlertOctagon, HelpCircle, CornerDownRight,
  RefreshCw, Star, Trash2, ChevronDown
} from 'lucide-react';
import {
  getClientDigitalAssets,
  getDigitalAssetDashboard,
  getOrganizationDnaV2Snapshot,
  getStrategicThoughts,
  refreshClientDigitalAssetNarrative,
  refreshOrganizationDnaV2,
  refreshStrategicThoughts,
  reviewStrategicThought,
  updateStrategicThoughtState,
  type DigitalAssetClientDetail,
  type DigitalAssetClientSummary,
  type DigitalAssetDashboard,
  type DigitalAssetMaterialMaturityRow,
  type DigitalAssetMapNode,
  type DigitalAssetMetric,
  type DigitalAssetNarrative,
  type DigitalAssetPulse,
  type OrganizationDnaV2Item,
  type OrganizationDnaV2Kind,
  type OrganizationDnaV2Snapshot,
  type StrategicThought,
} from '../../lib/api';

const TABS = [
  { id: 'clients', label: '数字资产中心' },
  { id: 'thoughts', label: '思考与研判' },
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

function isInternalSmokeClient(client: { id?: string; name?: string; alias?: string }) {
  return client.alias === 'workspace-smoke' || client.name === '安装态冒烟客户';
}

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

const STAGE_ORDER = ['资料整理期', '项目画像期', '结构计算期', '机制洞察期', '机会生成期'];
const NODE_STAGE_ORDER = ['整理', '画像', '计算', '洞察', '机会'];

const normalizedAssetStage = (stage: string | null | undefined) => String(stage || '').replace(/^L\d\s*/, '').trim();
const stageRank = (stage: string | null | undefined) => Math.max(0, STAGE_ORDER.indexOf(normalizedAssetStage(stage)));
const assetStageWithLevel = (stage: string | null | undefined) => {
  const normalized = normalizedAssetStage(stage) || '资料整理期';
  const rank = stageRank(normalized);
  return `L${rank + 1} ${normalized}`;
};

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
const materialRowPercent = (row: DigitalAssetMaterialMaturityRow) => Math.max(0, Math.min(100, Math.round(row.percent ?? 0)));

const maturityBarClass = (value: number) => {
  if (value >= 75) return 'bg-emerald-500';
  if (value >= 50) return 'bg-blue-500';
  if (value >= 30) return 'bg-amber-500';
  return 'bg-rose-500';
};

function AssetMaturityRows({ rows }: { rows: DigitalAssetMaterialMaturityRow[] }) {
  const [expanded, setExpanded] = useState(false);
  const visibleRows = expanded ? rows : rows.slice(0, 8);
  return (
    <section className="mt-8">
      <div className="flex items-baseline justify-between mb-4 px-1">
        <div>
          <h2 className="text-[15px] font-bold text-slate-800">资料成熟度进度条</h2>
          <p className="mt-1 text-[12px] text-slate-400">百分比表示资料质量成熟度，不按文件数量直接打分。</p>
        </div>
        <span className="text-[12px] font-bold text-blue-600">资料类型 {rows.length}</span>
      </div>
      <div className="rounded-[24px] border border-slate-100 bg-white p-4 shadow-[0_2px_10px_rgba(0,0,0,0.02)]">
        <div className="space-y-3">
          {visibleRows.map((row) => {
            const maturity = materialRowPercent(row);
            return (
              <div key={row.key} className="rounded-[18px] border border-slate-100 bg-slate-50/50 px-4 py-4">
                <div className="grid grid-cols-1 xl:grid-cols-[200px_minmax(240px,1fr)] gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      {maturity >= 50 ? <CheckCircle size={14} className="text-emerald-500 shrink-0" /> : <AlertCircle size={14} className="text-amber-500 shrink-0" />}
                      <span className="text-[14px] font-bold text-slate-800">{row.label}</span>
                    </div>
                    <p className="mt-1 text-[11px] leading-[1.6] text-slate-400">{row.level}</p>
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
                        <p className="mt-1 text-[12px] leading-[1.75] text-slate-600">{row.seenSummary || '已看到部分资料线索。'}</p>
                      </div>
                      <div>
                        <div className="text-[10px] font-bold text-amber-600">还缺</div>
                        <p className="mt-1 text-[12px] leading-[1.75] text-slate-600">{row.missingSummary || '还缺能持续复盘这类资料的记录。'}</p>
                      </div>
                    </div>
                    {row.unlockedValue && (
                      <div className="mt-3 rounded-[14px] bg-blue-50/70 px-3 py-2 text-[11px] leading-[1.65] text-blue-700">
                        {row.unlockedValue}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        {rows.length > 8 && (
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            className="mt-4 w-full rounded-[14px] border border-slate-100 bg-white px-4 py-2 text-[12px] font-bold text-blue-600 hover:bg-blue-50 transition-colors"
          >
            {expanded ? '收起资料类型' : `查看更多资料类型（${rows.length - 8}）`}
          </button>
        )}
      </div>
    </section>
  );
}

function AssetScoreBreakdownPanel({ detail }: { detail: DigitalAssetClientDetail }) {
  const items = [
    { key: 'structuralCompleteness', label: '结构完整度', value: detail.scoreBreakdown?.structuralCompleteness ?? 0 },
    { key: 'computability', label: '可计算度', value: detail.scoreBreakdown?.computable ?? 0 },
    { key: 'evidenceChain', label: '证据链强度', value: detail.scoreBreakdown?.evidenceChain ?? 0 },
    { key: 'timeContinuity', label: '时间连续性', value: detail.scoreBreakdown?.timeContinuity ?? 0 },
    { key: 'resultFeedbackLoop', label: '反馈结果关系', value: detail.scoreBreakdown?.resultFeedbackLoop ?? 0 },
  ];
  return (
    <section className="mt-6 rounded-[24px] border border-slate-100 bg-white p-5 shadow-[0_2px_10px_rgba(0,0,0,0.02)]">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-[15px] font-bold text-slate-800">成熟度怎么算</h2>
          <p className="mt-1 text-[12px] leading-6 text-slate-400">总成熟度由下面五项加权得到，资料厚度只代表沉淀努力。</p>
        </div>
        <span className="rounded-full bg-slate-50 px-3 py-1 text-[11px] font-bold text-slate-500">{detail.scoreMethodVersion || 'typed-profile-v2'}</span>
      </div>
      <div className="mt-4 grid grid-cols-1 md:grid-cols-5 gap-3">
        {items.map((item) => (
          <div key={item.key} className="rounded-[16px] bg-slate-50 px-3.5 py-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-slate-500">{item.label}</span>
              <span className="text-[12px] font-bold text-slate-800">{item.value}%</span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200">
              <div className={`h-full rounded-full ${maturityBarClass(item.value)}`} style={{ width: `${clampPercent(item.value)}%` }} />
            </div>
          </div>
        ))}
      </div>
      {(detail.scoreRationale || []).length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {(detail.scoreRationale || []).slice(0, 4).map((item, index) => (
            <span key={`${item}-${index}`} className="rounded-full bg-blue-50 px-3 py-1 text-[11px] font-semibold text-blue-600">
              {item}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}

function NextBestDepositPanel({ suggestions }: { suggestions: DigitalAssetClientDetail['nextBestDeposits'] }) {
  const visible = (suggestions || []).slice(0, 4);
  if (!visible.length) return null;
  return (
    <section className="mt-8 rounded-[24px] border border-slate-100 bg-white p-5 shadow-[0_2px_10px_rgba(0,0,0,0.02)]">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-[15px] font-bold text-slate-800">下一步最值得沉淀</h2>
        <span className="text-[12px] font-bold text-slate-400">{visible.length} 项</span>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {visible.map((item) => (
          <div key={`${item.dimensionKey}-${item.title}`} className="rounded-[18px] border border-slate-100 bg-slate-50/50 px-4 py-4">
            <div className="text-[13px] font-bold leading-6 text-slate-800">{item.title}</div>
            <p className="mt-2 text-[12px] leading-[1.75] text-slate-600">{item.reason}</p>
            {item.analysisValueUnlocked && (
              <p className="mt-3 rounded-[14px] bg-blue-50 px-3 py-2 text-[11px] leading-[1.65] text-blue-700">
                {item.analysisValueUnlocked}
              </p>
            )}
          </div>
        ))}
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
  const evidenceCount = metricValue(detail.sourceMetrics, 'evidenceCards');
  const maturityScore = detail.maturityScore ?? detail.stageProgress ?? 0;
  const depositThickness = detail.depositThickness ?? 0;
  const profileType = detail.assetProfileType || detail.assetTrackTitle || '组织战略陪伴型';

  return (
    <div className="animate-in fade-in duration-300">
      <DetailHeader
        clientName={detail.name}
        stageLabel={detail.stage || '待判断'}
        readinessScore={maturityScore}
        assetStage={detail.assetStage}
        assetTrackTitle={profileType}
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
                {assetStageWithLevel(detail.assetStage)} · {profileType}
              </h2>
              <p className="text-[14px] leading-[1.9] text-slate-700 font-medium">
                {detail.understandingStatement}
              </p>
              {depositThickness >= 65 && maturityScore < 55 && (
                <div className="mt-4 inline-flex rounded-full border border-amber-100 bg-amber-50 px-3 py-1.5 text-[11px] font-bold text-amber-700">
                  资料很多，但还缺可计算、可验证的连续资料
                </div>
              )}
            </div>
            <div className="grid grid-cols-3 gap-2.5 min-w-[320px]">
              {[
                { label: '资料厚度', value: `${depositThickness}%`, icon: Award },
                { label: '成熟度', value: `${maturityScore}%`, icon: Activity },
                { label: '下一阶段', value: detail.nextStage || '继续沉淀', icon: Target },
                { label: '沉淀经验', value: `${detail.depositXp} XP`, icon: Layers },
                { label: '证据卡', value: evidenceCount.toLocaleString(), icon: CheckCircle },
                { label: '资料沉淀', value: documentCount.toLocaleString(), icon: FileText },
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

        <AssetScoreBreakdownPanel detail={detail} />
        <AssetMaturityRows rows={detail.materialMaturityRows || []} />
        <NextBestDepositPanel suggestions={detail.nextBestDeposits || []} />
      </div>
    </div>
  );
}


// ================= TAB CONTENT =================

function DigitalAssetPulsePanel({
  pulse,
  onOpenDetail,
}: {
  pulse?: DigitalAssetPulse | null;
  onOpenDetail: (clientId: string) => void;
}) {
  const weeklyStats = [
    { label: '新记忆', value: pulse?.weeklyNewFacts ?? 0 },
    { label: '新资料', value: pulse?.weeklyNewDocuments ?? 0 },
    { label: '新证据卡', value: pulse?.weeklyNewEvidenceCards ?? 0 },
  ];
  const funnel = pulse?.digestionFunnel || [];
  const highlights = (pulse?.learningHighlights || []).slice(0, 3);
  const alerts = (pulse?.assetAlerts || []).slice(0, 3);
  const activeOrganizations = (pulse?.activeOrganizations || []).slice(0, 4);
  const signalClass = (severity?: string) => {
    if (severity === 'critical') return 'border-rose-100 bg-rose-50/70 text-rose-700';
    if (severity === 'warning') return 'border-amber-100 bg-amber-50/70 text-amber-700';
    return 'border-blue-100 bg-blue-50/70 text-blue-700';
  };
  return (
    <section
      className="mb-6 rounded-[28px] border border-blue-100 bg-white p-6 shadow-[0_12px_36px_rgba(15,23,42,0.05)]"
      style={{
        backgroundImage: 'linear-gradient(135deg, rgba(37,99,235,0.08), rgba(20,184,166,0.06) 42%, rgba(255,255,255,0) 78%), linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)',
      }}
    >
      <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
        <div className="max-w-4xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-[12px] font-bold text-blue-600">
            <BrainCircuit size={14} />
            组织大脑脉搏
          </div>
          <h2 className="mt-4 text-[22px] font-bold tracking-tight text-slate-900">
            AI 最近学到了什么
          </h2>
          <p className="mt-2 text-[14px] font-medium leading-[1.85] text-slate-600">
            {pulse?.headline || '正在读取组织数字资产脉搏。'}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <span className="rounded-full border border-slate-100 bg-white/80 px-3 py-1 text-[11px] font-bold text-slate-500">
              已陪伴 {pulse?.daysAccompanied ?? 0} 天
            </span>
            {weeklyStats.map((item) => (
              <span key={item.label} className="rounded-full border border-emerald-100 bg-emerald-50 px-3 py-1 text-[11px] font-bold text-emerald-600">
                本周 +{item.value.toLocaleString()} {item.label}
              </span>
            ))}
          </div>
        </div>
        {activeOrganizations.length > 0 && (
          <div className="grid min-w-[320px] grid-cols-1 gap-2">
            {activeOrganizations.slice(0, 3).map((item) => (
              <button
                key={item.clientId}
                type="button"
                onClick={() => onOpenDetail(item.clientId)}
                className="rounded-[16px] border border-white/80 bg-white/80 px-4 py-3 text-left shadow-sm transition hover:border-blue-200 hover:bg-white"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="truncate text-[13px] font-bold text-slate-800">{item.name}</span>
                  <span className="text-[11px] font-bold text-blue-600">{item.maturityScore}%</span>
                </div>
                <div className="mt-1 truncate text-[11px] font-semibold text-slate-400">{item.assetProfileType}</div>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="mt-6 rounded-[20px] border border-slate-100 bg-white/80 p-4">
        <div className="mb-3 flex items-center gap-2">
          <GitBranch size={15} className="text-blue-500" />
          <span className="text-[13px] font-bold text-slate-800">资料消化状态</span>
        </div>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
          {funnel.map((item, index) => (
            <div key={item.key} className="relative rounded-[16px] bg-slate-50 px-3 py-3">
              <div className="text-[10px] font-bold text-slate-400">{item.label}</div>
              <div className="mt-1 text-[20px] font-bold tabular-nums text-slate-800">{item.value.toLocaleString()}</div>
              {index < funnel.length - 1 && (
                <ChevronRight size={14} className="absolute right-2 top-1/2 hidden -translate-y-1/2 text-slate-300 md:block" />
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div className="rounded-[20px] border border-slate-100 bg-white/80 p-4">
          <div className="mb-3 flex items-center gap-2">
            <Sparkles size={15} className="text-blue-500" />
            <span className="text-[13px] font-bold text-slate-800">本周变聪明的地方</span>
          </div>
          <div className="space-y-2">
            {highlights.length ? highlights.map((item) => (
              <button
                key={`${item.clientId}-${item.title}`}
                type="button"
                onClick={() => item.clientId && onOpenDetail(item.clientId)}
                className="w-full rounded-[16px] border border-blue-100 bg-blue-50/60 px-3 py-3 text-left transition hover:bg-blue-50"
              >
                <div className="text-[12px] font-bold text-blue-700">{item.title}</div>
                <p className="mt-1 line-clamp-2 text-[12px] leading-[1.65] text-slate-600">{item.summary}</p>
              </button>
            )) : (
              <div className="rounded-[16px] bg-slate-50 px-3 py-3 text-[12px] leading-6 text-slate-500">本周还没有明显的新理解，继续沉淀资料后这里会出现变化。</div>
            )}
          </div>
        </div>

        <div className="rounded-[20px] border border-slate-100 bg-white/80 p-4">
          <div className="mb-3 flex items-center gap-2">
            <AlertTriangle size={15} className="text-amber-500" />
            <span className="text-[13px] font-bold text-slate-800">需要处理的信号</span>
          </div>
          <div className="space-y-2">
            {alerts.length ? alerts.map((item) => (
              <button
                key={`${item.clientId}-${item.title}`}
                type="button"
                onClick={() => item.clientId && onOpenDetail(item.clientId)}
                className={`w-full rounded-[16px] border px-3 py-3 text-left transition hover:bg-white ${signalClass(item.severity)}`}
              >
                <div className="text-[12px] font-bold">{item.title}</div>
                <p className="mt-1 line-clamp-2 text-[12px] leading-[1.65] text-slate-600">{item.summary}</p>
              </button>
            )) : (
              <div className="rounded-[16px] bg-slate-50 px-3 py-3 text-[12px] leading-6 text-slate-500">暂时没有明显异常，继续观察资料是否能转成证据和判断。</div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

const ORGANIZATION_DNA_KIND_META: Record<OrganizationDnaV2Kind, { title: string; description: string; icon: React.ReactNode; tone: string }> = {
  stable_dna: {
    title: '稳定画像',
    description: '定位、服务对象、业务体系和表达口径',
    icon: <Layers size={15} />,
    tone: 'border-blue-100 bg-blue-50/70 text-blue-700',
  },
  evolving_dna: {
    title: '近期变化',
    description: '任务、事件线、复盘里的组织能力变化',
    icon: <Activity size={15} />,
    tone: 'border-emerald-100 bg-emerald-50/70 text-emerald-700',
  },
  gap_dna: {
    title: '资料缺口',
    description: '系统还能自动补什么、还缺哪些内部资料',
    icon: <HelpCircle size={15} />,
    tone: 'border-amber-100 bg-amber-50/70 text-amber-700',
  },
  risk_dna: {
    title: '风险边界',
    description: '公开/内部口径、弱证据和事实边界',
    icon: <AlertOctagon size={15} />,
    tone: 'border-rose-100 bg-rose-50/70 text-rose-700',
  },
};

function OrganizationDnaMiniList({ kind, items }: { kind: OrganizationDnaV2Kind; items: OrganizationDnaV2Item[] }) {
  const meta = ORGANIZATION_DNA_KIND_META[kind];
  const visibleItems = items.slice(0, 2);
  return (
    <div className="rounded-[20px] border border-slate-100 bg-white/80 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-[11px] font-bold ${meta.tone}`}>
            {meta.icon}
            {meta.title}
          </div>
          <p className="mt-2 text-[12px] leading-5 text-slate-500">{meta.description}</p>
        </div>
        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-bold text-slate-500">
          {items.length}
        </span>
      </div>
      <div className="mt-4 space-y-2">
        {visibleItems.length ? visibleItems.map((item) => (
          <div key={item.id} className="rounded-[16px] border border-slate-100 bg-slate-50/70 px-3 py-3">
            <div className="line-clamp-1 text-[12px] font-bold text-slate-800">{item.title}</div>
            <p className="mt-1 line-clamp-2 text-[12px] leading-[1.65] text-slate-600">
              {item.summary || '已进入组织 DNA 资料层，等待后续资料刷新。'}
            </p>
          </div>
        )) : (
          <div className="rounded-[16px] border border-dashed border-slate-200 bg-slate-50/70 px-3 py-3 text-[12px] leading-6 text-slate-400">
            暂无内容，生成或刷新后这里会出现新的组织资产。
          </div>
        )}
      </div>
    </div>
  );
}

function OrganizationDnaPanel({
  snapshot,
  loading,
  refreshing,
  error,
  onRefresh,
}: {
  snapshot: OrganizationDnaV2Snapshot | null;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  onRefresh: () => void;
}) {
  const itemCount =
    (snapshot?.stableItems.length ?? 0)
    + (snapshot?.evolvingItems.length ?? 0)
    + (snapshot?.gapItems.length ?? 0)
    + (snapshot?.riskItems.length ?? 0);
  const latestRun = snapshot?.latestRun;
  const actionText = itemCount > 0 ? '刷新组织 DNA' : '生成初版';
  return (
    <section className="mb-6 rounded-[28px] border border-slate-100 bg-white p-6 shadow-[0_12px_36px_rgba(15,23,42,0.05)]">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[12px] font-bold text-slate-600">
            <Bot size={14} />
            组织 DNA v2
          </div>
          <h2 className="mt-4 text-[22px] font-bold tracking-tight text-slate-900">组织级智能资产</h2>
          <p className="mt-2 text-[14px] font-medium leading-[1.85] text-slate-600">
            这里沉淀当前组织自己的定位、近期变化、资料缺口和风险边界。它由系统从组织模型、任务、事件线和复盘中持续刷新，不再作为设置页里的静态文本。
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <span className="rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-[11px] font-bold text-blue-600">
              已稳定 {snapshot?.confirmedCount ?? 0}
            </span>
            <span className="rounded-full border border-amber-100 bg-amber-50 px-3 py-1 text-[11px] font-bold text-amber-600">
              待积累 {snapshot?.candidateCount ?? 0}
            </span>
            <span className="rounded-full border border-slate-100 bg-slate-50 px-3 py-1 text-[11px] font-bold text-slate-500">
              需刷新 {snapshot?.staleCount ?? 0}
            </span>
            <span className="rounded-full border border-slate-100 bg-white px-3 py-1 text-[11px] font-bold text-slate-400">
              最近刷新 {snapshot?.updatedAt || latestRun?.updatedAt || '尚未生成'}
            </span>
          </div>
          {error && (
            <div className="mt-3 rounded-[14px] border border-rose-100 bg-rose-50 px-3 py-2 text-[12px] font-semibold text-rose-600">
              {error}
            </div>
          )}
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading || refreshing}
          className="inline-flex items-center justify-center gap-2 rounded-2xl bg-slate-900 px-4 py-2.5 text-[13px] font-bold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
          {loading ? '读取中' : refreshing ? '刷新中' : actionText}
        </button>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-4">
        <OrganizationDnaMiniList kind="stable_dna" items={snapshot?.stableItems ?? []} />
        <OrganizationDnaMiniList kind="evolving_dna" items={snapshot?.evolvingItems ?? []} />
        <OrganizationDnaMiniList kind="gap_dna" items={snapshot?.gapItems ?? []} />
        <OrganizationDnaMiniList kind="risk_dna" items={snapshot?.riskItems ?? []} />
      </div>
    </section>
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
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const options = useMemo(() => [{ id: '', name: '全部客户' }, ...clients], [clients]);
  const selectedClient = options.find((client) => client.id === selectedClientId) || options[0];

  useEffect(() => {
    if (!open) return;
    const handlePointerDown = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open]);

  const handleSelect = (clientId: string) => {
    onChange(clientId);
    setOpen(false);
  };

  return (
    <div ref={rootRef} className="relative flex items-center gap-2 rounded-2xl border border-slate-200 bg-white/90 px-3 py-2 shadow-sm">
      <Users size={15} className="text-blue-500 shrink-0" />
      <span className="text-[12px] font-semibold text-slate-500 whitespace-nowrap">客户/项目</span>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((value) => !value)}
        className="flex min-w-[130px] max-w-[220px] items-center justify-between gap-2 bg-transparent text-left text-[13px] font-semibold text-slate-700 outline-none disabled:cursor-not-allowed disabled:opacity-50"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="truncate">{selectedClient.name}</span>
        <ChevronDown size={14} className={`shrink-0 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && !disabled && (
        <div
          role="listbox"
          className="absolute right-0 top-full z-50 mt-2 w-[240px] max-h-[360px] overflow-y-auto rounded-2xl border border-slate-200 bg-white p-1.5 shadow-[0_18px_60px_rgba(15,23,42,0.18)]"
        >
          {options.map((client) => {
            const selected = client.id === selectedClientId;
            return (
              <button
                key={client.id || 'all_clients'}
                type="button"
                role="option"
                aria-selected={selected}
                onClick={() => handleSelect(client.id)}
                className={`flex h-9 w-full items-center justify-between gap-2 rounded-xl px-3 text-left text-[13px] font-semibold transition-colors ${
                  selected ? 'bg-blue-500 text-white' : 'text-slate-700 hover:bg-blue-50 hover:text-blue-600'
                }`}
              >
                <span className="truncate">{client.name}</span>
                {selected && <Check size={14} className="shrink-0" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function DigitalAssetsTab({
  onOpenDetail,
  clients,
  pulse,
  organizationDnaSnapshot,
  organizationDnaLoading,
  organizationDnaRefreshing,
  organizationDnaError,
  onRefreshOrganizationDna,
}: {
  onOpenDetail: (clientId: string) => void;
  clients: DigitalAssetClientSummary[];
  pulse?: DigitalAssetPulse | null;
  organizationDnaSnapshot: OrganizationDnaV2Snapshot | null;
  organizationDnaLoading: boolean;
  organizationDnaRefreshing: boolean;
  organizationDnaError: string | null;
  onRefreshOrganizationDna: () => void;
}) {
  const sorted = [...clients].sort((a, b) => {
    const stageDiff = stageRank(b.assetStage) - stageRank(a.assetStage);
    if (stageDiff !== 0) return stageDiff;
    return (b.depositXp || 0) - (a.depositXp || 0);
  });
  if (!clients.length) {
    return (
      <div>
        <OrganizationDnaPanel
          snapshot={organizationDnaSnapshot}
          loading={organizationDnaLoading}
          refreshing={organizationDnaRefreshing}
          error={organizationDnaError}
          onRefresh={onRefreshOrganizationDna}
        />
        <DigitalAssetPulsePanel pulse={pulse} onOpenDetail={onOpenDetail} />
        <div className="bg-white border border-slate-100 rounded-[24px] px-6 py-8">
          <p className="text-[14px] font-bold text-slate-700">还没有可形成数字资产的组织资料</p>
          <p className="text-[13px] leading-7 text-slate-500 mt-2">建议先建立客户/组织空间，并上传项目介绍、流程资料、反馈表和评估材料。</p>
        </div>
      </div>
    );
  }
  return (
    <div>
      <OrganizationDnaPanel
        snapshot={organizationDnaSnapshot}
        loading={organizationDnaLoading}
        refreshing={organizationDnaRefreshing}
        error={organizationDnaError}
        onRefresh={onRefreshOrganizationDna}
      />
      <DigitalAssetPulsePanel pulse={pulse} onOpenDetail={onOpenDetail} />
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        {sorted.map((client) => {
          const documentCount = metricValue(client.metrics, 'documents');
          const memoryCount = metricValue(client.metrics, 'memoryFacts');
          const evidenceCount = metricValue(client.metrics, 'evidenceCards');
          const overviewRows = (client.materialMaturityRows || []).slice(0, 3);
          const weakestRow = [...overviewRows]
            .filter((row) => row.missingSummary)
            .sort((a, b) => materialRowPercent(a) - materialRowPercent(b))[0] || overviewRows[0];
          const missingText = weakestRow?.missingSummary || client.stageBlockers?.[0] || client.criticalGaps?.[0] || '继续沉淀能说明组织、项目、对象、过程和反馈的资料。';
          const maturityScore = client.maturityScore ?? client.stageProgress ?? 0;
          const profileType = client.assetProfileType || client.assetTrackTitle || '组织战略陪伴型';
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
                  {assetStageWithLevel(client.assetStage)}
                </span>
              </div>
            </div>
            <div className="mb-4 flex flex-wrap gap-2">
              <span className="rounded-full bg-slate-50 border border-slate-100 px-2.5 py-1 text-[11px] font-bold text-slate-600">
                {profileType}
              </span>
              <span className="rounded-full bg-blue-50 border border-blue-100 px-2.5 py-1 text-[11px] font-bold text-blue-600">
                资料厚度 {client.depositThickness ?? 0}%
              </span>
              <span className="rounded-full bg-indigo-50 border border-indigo-100 px-2.5 py-1 text-[11px] font-bold text-indigo-600">
                成熟度 {maturityScore}%
              </span>
              <span className="rounded-full bg-emerald-50 border border-emerald-100 px-2.5 py-1 text-[11px] font-bold text-emerald-600">
                {client.growthMode || '均衡成长'}
              </span>
            </div>
            <p className="text-[13px] leading-[1.75] text-slate-600 font-medium mb-4 line-clamp-2">
              {client.understandingStatement || client.intro || 'AI 对这个组织还处在初步理解阶段。'}
            </p>
            <div className="mb-4 rounded-[18px] border border-slate-100 bg-slate-50/50 px-4 py-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-bold text-slate-500">核心资料成熟度</span>
                <span className="text-[11px] font-bold text-slate-300">资料质量</span>
              </div>
              {overviewRows.length ? (
                <div className="space-y-2.5">
                  {overviewRows.map((row) => {
                    const maturity = materialRowPercent(row);
                    return (
                      <div key={row.key} className="grid grid-cols-[92px_1fr_38px] items-center gap-2">
                        <span className="truncate text-[11px] font-bold text-slate-600">{row.label}</span>
                        <div className="h-1.5 overflow-hidden rounded-full bg-slate-200/80">
                          <div
                            className={`h-full rounded-full ${maturityBarClass(maturity)}`}
                            style={{ width: `${clampPercent(maturity)}%` }}
                          />
                        </div>
                        <span className="text-right text-[11px] font-bold tabular-nums text-slate-500">{maturity}%</span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-[12px] leading-6 text-slate-400">资料类型待识别。先补充组织介绍、项目资料、流程记录和反馈材料。</p>
              )}
            </div>
            {(client.depositThickness ?? 0) >= 65 && maturityScore < 55 && (
              <div className="mb-3 rounded-[14px] bg-amber-50 px-3 py-2 text-[11px] leading-[1.6] font-semibold text-amber-700">
                资料沉淀不少，但还缺可计算、可验证的连续资料。
              </div>
            )}
            <div className="mb-5 rounded-[16px] bg-amber-50/70 px-3 py-2.5">
              <div className="text-[10px] font-bold text-amber-600 mb-1">还缺</div>
              <p className="text-[11px] leading-[1.65] text-slate-600 line-clamp-2">{missingText}</p>
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
  currentClientId?: string | null;
  onClientChange?: (clientId: string) => void;
  onCreateTaskFromThought?: (payload: ThoughtTaskPayload) => void;
  flash?: (level: 'success' | 'error' | 'info', message: string) => void;
};

export function StrategicBrainView({
  clients = [],
  currentClientId,
  onClientChange,
  onCreateTaskFromThought,
  flash,
}: StrategicBrainViewProps) {
  const [activeTab, setActiveTab] = useState('clients');
  const [viewState, setViewState] = useState<{ type: 'tabs'; detailId: null } | { type: 'detail'; detailId: string }>({ type: 'tabs', detailId: null });
  const [assetDashboard, setAssetDashboard] = useState<DigitalAssetDashboard | null>(null);
  const [organizationDnaSnapshot, setOrganizationDnaSnapshot] = useState<OrganizationDnaV2Snapshot | null>(null);
  const [organizationDnaLoading, setOrganizationDnaLoading] = useState(false);
  const [organizationDnaRefreshing, setOrganizationDnaRefreshing] = useState(false);
  const [organizationDnaError, setOrganizationDnaError] = useState<string | null>(null);
  const [thoughts, setThoughts] = useState<StrategicThought[]>([]);
  const [thoughtsLoading, setThoughtsLoading] = useState(false);
  const [thoughtsError, setThoughtsError] = useState<string | null>(null);
  const [thoughtClientId, setThoughtClientId] = useState(currentClientId || '');
  const [thoughtsRefreshing, setThoughtsRefreshing] = useState(false);

  const thoughtClientOptions = useMemo(() => {
    const map = new Map<string, { id: string; name: string }>();
    for (const client of assetDashboard?.clients ?? []) {
      if (client.id && client.name && !isInternalSmokeClient(client)) map.set(client.id, { id: client.id, name: client.name });
    }
    for (const client of clients) {
      if (client.id && client.name && !isInternalSmokeClient(client) && !map.has(client.id)) map.set(client.id, { id: client.id, name: client.name });
    }
    return Array.from(map.values());
  }, [clients, assetDashboard?.clients]);

  const selectedThoughtClient = useMemo(
    () => thoughtClientOptions.find((client) => client.id === thoughtClientId) || null,
    [thoughtClientId, thoughtClientOptions],
  );

  const loadOrganizationDnaSnapshot = useCallback(async () => {
    setOrganizationDnaLoading(true);
    setOrganizationDnaError(null);
    try {
      const snapshot = await getOrganizationDnaV2Snapshot();
      setOrganizationDnaSnapshot(snapshot);
    } catch (error) {
      setOrganizationDnaError(error instanceof Error ? error.message : '组织 DNA 读取失败');
      setOrganizationDnaSnapshot(null);
    } finally {
      setOrganizationDnaLoading(false);
    }
  }, []);

  useEffect(() => {
    getDigitalAssetDashboard()
      .then(setAssetDashboard)
      .catch(() => setAssetDashboard(null));
    void loadOrganizationDnaSnapshot();
  }, [loadOrganizationDnaSnapshot]);

  useEffect(() => {
    setThoughtClientId(currentClientId || '');
  }, [currentClientId]);

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

  const handleRefreshOrganizationDna = useCallback(async () => {
    setOrganizationDnaRefreshing(true);
    setOrganizationDnaError(null);
    try {
      const run = await refreshOrganizationDnaV2('digital_asset_center');
      if (run.status === 'failed') {
        throw new Error(run.error || '组织 DNA 刷新失败');
      }
      await loadOrganizationDnaSnapshot();
      flash?.('success', '组织 DNA 已刷新');
    } catch (error) {
      const message = error instanceof Error ? error.message : '组织 DNA 刷新失败';
      setOrganizationDnaError(message);
      flash?.('error', message);
    } finally {
      setOrganizationDnaRefreshing(false);
    }
  }, [flash, loadOrganizationDnaSnapshot]);

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
          {activeTab === 'clients' && (
            <DigitalAssetsTab
              clients={assetDashboard?.clients ?? []}
              pulse={assetDashboard?.pulse ?? null}
              organizationDnaSnapshot={organizationDnaSnapshot}
              organizationDnaLoading={organizationDnaLoading}
              organizationDnaRefreshing={organizationDnaRefreshing}
              organizationDnaError={organizationDnaError}
              onRefreshOrganizationDna={handleRefreshOrganizationDna}
              onOpenDetail={(clientId) => setViewState({ type: 'detail', detailId: clientId })}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default StrategicBrainView;
