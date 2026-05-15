import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  BrainCircuit, Sparkles, FileText, CheckCircle,
  GitBranch, Award, Layers,
  AlertCircle, ClipboardList, Check, Folder, Target, FolderTree,
  Activity, Bot, PenLine, Calendar,
  ArrowLeft, AlertTriangle, ChevronRight, XCircle,
  Users, Flag, AlertOctagon, HelpCircle, CornerDownRight,
  RefreshCw, Star, Trash2, ChevronDown, ExternalLink
} from 'lucide-react';
import { FileTypeIcon } from '../FileTypeIcon';
import {
  getClientContradictions,
  getClientDigitalAssets,
  getClientDuplicateDocuments,
  getClientKnowledgeStatus,
  resolveDuplicateDocuments,
  getDigitalAssetDashboard,
  getOrganizationDnaV2Snapshot,
  getStrategicThoughts,
  refreshClientDigitalAssetNarrative,
  refreshOrganizationDnaV2,
  refreshStrategicThoughts,
  reviewContradiction,
  reviewStrategicThought,
  updateStrategicThoughtState,
  type ClientKnowledgeStatus,
  type DigitalAssetClientDetail,
  type DuplicateDocumentGroup,
  type FactContradictionRow,
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

// Stage 3：战略陪伴信息架构 —— Karpathy 知识页式 5 tab。
// 原本设计了 6 tab（含独立的「最近变化」），但发现客户档案 tab 里的 evolving_dna
// mini list 已经显示了最近变化；独立 tab 反而分散用户注意力。改回 5 tab，
// 客户档案 mini list 内部用滚动条让用户能看更多 evolving 条目即可。
const TABS = [
  { id: 'clients', label: '客户档案' },         // 客户卡 + 知识画像（含 evolving mini list 可滚动）
  { id: 'thoughts', label: '判断 & 思考' },      // 研判 + 已采纳判断
  { id: 'contradictions', label: '矛盾 & 待确认' }, // fact_contradictions UI
  { id: 'health', label: '资料健康' },           // 4 数字总览 + lint 结果 (Stage 5 补全)
  { id: 'outputs', label: '输出沉淀' },          // proposals + 已采纳判断
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
  // 5 项评分指标改用业务语言。原工程语言（结构完整度/可计算度/证据链强度/时间连续性/反馈结果关系）
  // 对非技术读者太陌生。这里翻译成「组织信息是否齐全 / AI 能否给出可计算判断 / 证据是否找得到 /
  // 时间线是否连贯 / 做完是否回灌系统」—— 用户能直接读懂该改进什么。
  const items = [
    { key: 'structuralCompleteness', label: '组织信息齐不齐', hint: '组织、项目、对象、过程、反馈 5 类资料的覆盖', value: detail.scoreBreakdown?.structuralCompleteness ?? 0 },
    { key: 'computability', label: 'AI 能不能给出准确判断', hint: '资料是否含有可被检索、可被引用的结构化片段', value: detail.scoreBreakdown?.computable ?? 0 },
    { key: 'evidenceChain', label: '证据找不找得到', hint: '判断和决策能否追溯到具体原文段落', value: detail.scoreBreakdown?.evidenceChain ?? 0 },
    { key: 'timeContinuity', label: '时间线连不连续', hint: '不同时期的资料是否能串成演进脉络', value: detail.scoreBreakdown?.timeContinuity ?? 0 },
    { key: 'resultFeedbackLoop', label: '做完有没有回灌系统', hint: '任务执行结果、复盘、反馈是否进入了知识库', value: detail.scoreBreakdown?.resultFeedbackLoop ?? 0 },
  ];
  return (
    <section className="mt-6 rounded-[24px] border border-slate-100 bg-white p-5 shadow-[0_2px_10px_rgba(0,0,0,0.02)]">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-[15px] font-bold text-slate-800">AI 学习能力体检</h2>
          <p className="mt-1 text-[12px] leading-6 text-slate-400">这 5 项决定了 AI 能不能针对你的组织给出靠谱判断。颜色越深，AI 在这一项越自信。</p>
        </div>
        <span className="rounded-full bg-slate-50 px-3 py-1 text-[11px] font-bold text-slate-500" title={detail.scoreMethodVersion || 'typed-profile-v2'}>体检维度</span>
      </div>
      <div className="mt-4 grid grid-cols-1 md:grid-cols-5 gap-3">
        {items.map((item) => (
          <div key={item.key} className="rounded-[16px] bg-slate-50 px-3.5 py-3" title={item.hint}>
            <div className="flex items-start justify-between gap-2">
              <span className="text-[11px] font-bold text-slate-600 leading-tight">{item.label}</span>
              <span className="text-[12px] font-bold text-slate-800 shrink-0">{item.value}%</span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200">
              <div className={`h-full rounded-full ${maturityBarClass(item.value)}`} style={{ width: `${clampPercent(item.value)}%` }} />
            </div>
            <p className="mt-2 text-[10px] leading-[1.5] text-slate-400">{item.hint}</p>
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
  const [knowledgeStatus, setKnowledgeStatus] = useState<ClientKnowledgeStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [narrativeLoading, setNarrativeLoading] = useState(false);
  const [narrativeError, setNarrativeError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);
    setNarrativeError(null);
    // 并行 fetch：digital asset detail（重型，含 narrative / breakdown 等）
    // + knowledge status（轻量，Karpathy 4 数字）—— 后者快，让 hero 区先有数字可见。
    void Promise.all([
      getClientDigitalAssets(clientId).then((result) => {
        if (!mounted) return;
        setDetail(result);
      }).catch((err) => {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : '加载失败');
        setDetail(null);
      }),
      getClientKnowledgeStatus(clientId).then((result) => {
        if (!mounted) return;
        setKnowledgeStatus(result);
      }).catch((err) => {
        // 知识状态拉不到不阻塞主面板渲染
        console.warn('[strategic] knowledge-status failed', err);
      }),
    ]).finally(() => {
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
                // 4 个 Karpathy 语义数字代替百分比成熟度。学习没有尽头，所以这里是绝对数 + 颜色，没有 100%。
                {
                  label: '已确认事实',
                  value: knowledgeStatus ? knowledgeStatus.confirmedFacts.toLocaleString() : '—',
                  icon: CheckCircle,
                  tone: 'text-emerald-700',
                  bg: 'bg-emerald-50/70',
                  hint: knowledgeStatus && knowledgeStatus.weeklyDelta.confirmedFacts > 0
                    ? `本周 +${knowledgeStatus.weeklyDelta.confirmedFacts}`
                    : '',
                },
                {
                  label: '待确认思考',
                  value: knowledgeStatus ? knowledgeStatus.pendingThoughts.toLocaleString() : '—',
                  icon: HelpCircle,
                  tone: knowledgeStatus && knowledgeStatus.pendingThoughts > 0 ? 'text-amber-700' : 'text-slate-500',
                  bg: knowledgeStatus && knowledgeStatus.pendingThoughts > 0 ? 'bg-amber-50/70' : 'bg-white/80',
                  hint: knowledgeStatus && knowledgeStatus.weeklyDelta.newThoughts > 0
                    ? `本周 +${knowledgeStatus.weeklyDelta.newThoughts}`
                    : '',
                },
                {
                  label: '矛盾点',
                  value: knowledgeStatus ? knowledgeStatus.activeContradictions.toLocaleString() : '—',
                  icon: AlertOctagon,
                  tone: knowledgeStatus && knowledgeStatus.activeContradictions > 0 ? 'text-rose-700' : 'text-slate-500',
                  bg: knowledgeStatus && knowledgeStatus.activeContradictions > 0 ? 'bg-rose-50/70' : 'bg-white/80',
                  hint: knowledgeStatus && knowledgeStatus.activeContradictions > 0 ? '待你确认' : '暂无打架',
                },
                {
                  label: '信息缺口',
                  value: knowledgeStatus ? knowledgeStatus.knowledgeGaps.toLocaleString() : '—',
                  icon: Layers,
                  tone: knowledgeStatus && knowledgeStatus.knowledgeGaps > 0 ? 'text-amber-700' : 'text-slate-500',
                  bg: 'bg-white/80',
                  hint: knowledgeStatus && knowledgeStatus.weeklyDelta.confirmedJudgments > 0
                    ? `本周 +${knowledgeStatus.weeklyDelta.confirmedJudgments} 判断`
                    : '',
                },
                // 保留 2 个原有指标作为辅助
                {
                  label: '下一阶段',
                  value: detail.nextStage || '继续沉淀',
                  icon: Target,
                  tone: 'text-slate-700',
                  bg: 'bg-white/80',
                  hint: '',
                },
                {
                  label: '已学资料',
                  value: documentCount.toLocaleString(),
                  icon: FileText,
                  tone: 'text-slate-700',
                  bg: 'bg-white/80',
                  hint: `${evidenceCount} 张证据卡`,
                },
              ].map((item) => (
                <div key={item.label} className={`rounded-[18px] border border-slate-100 px-4 py-3 shadow-sm ${item.bg}`}>
                  <div className="flex items-center gap-1.5 text-[10px] font-bold text-slate-400">
                    <item.icon size={12} />
                    {item.label}
                  </div>
                  <div className={`mt-1 text-[20px] font-bold tabular-nums ${item.tone}`}>{item.value}</div>
                  {item.hint && <div className="mt-0.5 text-[10px] font-semibold text-slate-500">{item.hint}</div>}
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
  // 之前 slice(0, 2) 把 evolving/stable/gap/risk 都强制只显示 2 条，
  // 用户看到列表里压着「N」但只见 2 条很委屈。改成内部滚动：
  // 前 2 条始终可见，超过后整个列表区可上下滚动，让用户能看到全部。
  // 这也回应了"最近变化用滑动条而不是独立 tab"的设计。
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
      <div
        className="mt-4 space-y-2 max-h-[220px] overflow-y-auto pr-1"
        style={{ scrollbarGutter: 'stable' }}
      >
        {items.length ? items.map((item) => (
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
      {items.length > 3 && (
        <p className="mt-2 text-[10px] text-slate-400 text-right">↕ 上下滑动查看全部 {items.length} 条</p>
      )}
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

// ───────────────────────────────────────────────────────────────────────────
// Stage 3 新增的 4 个 tab 组件
// 信息架构改造：从「数字资产中心 + 思考研判」2 tab 重构为 Karpathy 知识页式 6 tab。
// 这 4 个新组件消费已存在的后端数据，让「矛盾 / 资料健康 / 输出沉淀 / 最近变化」
// 这些 Karpathy 启示提到的知识页类型变成独立的可访问 tab。
// ───────────────────────────────────────────────────────────────────────────

// 备注：原 RecentChangesTab 已删除。最近变化信息保留在客户档案 tab 内
// 的 OrganizationDnaMiniList「近期变化」mini list 里，那里改成可滚动容器
// 让用户能看到更多 evolving 条目。独立 tab 反而和客户档案 mini list 重复，
// 让信息架构臃肿。

function TabClientPicker({
  clientOptions,
  selectedClientId,
  onClientChange,
}: {
  clientOptions: Array<{ id: string; name: string }>;
  selectedClientId: string;
  onClientChange: (id: string) => void;
}) {
  return (
    <select
      value={selectedClientId}
      onChange={(e) => onClientChange(e.target.value)}
      className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[12px] font-bold text-slate-700 focus:outline-none focus:border-blue-300"
    >
      <option value="">— 选择客户 —</option>
      {clientOptions.map((c) => (
        <option key={c.id} value={c.id}>{c.name}</option>
      ))}
    </select>
  );
}

// 注意：原 DuplicateResolveModal 已删除，改为直接在 DuplicateDocumentsSection
// 里把每组的卡片横向铺开，用户在卡片上直接点🗑删 / 📂打开，不再有二级弹窗。
function _DEPRECATED_DuplicateResolveModal({
  group,
  clientId,
  onClose,
  onResolved,
  flash,
}: {
  group: DuplicateDocumentGroup;
  clientId: string;
  onClose: () => void;
  onResolved: () => void;
  flash?: (level: 'success' | 'error' | 'info', message: string) => void;
}) {
  const totalRefs = useCallback((doc: DuplicateDocumentItem) =>
    doc.refTaskAttachmentCount + doc.refEvidenceCardCount + doc.refAtomicFactCount,
  []);
  const recommendedKeepId = useMemo(() => {
    if (group.documents.length === 0) return null;
    const sorted = [...group.documents].sort((a, b) => {
      const dr = totalRefs(b) - totalRefs(a);
      if (dr !== 0) return dr;
      return (a.importedAt || '').localeCompare(b.importedAt || '');
    });
    return sorted[0].id;
  }, [group, totalRefs]);

  const [keepIds, setKeepIds] = useState<Set<string>>(() => {
    const initial = new Set<string>();
    if (recommendedKeepId) initial.add(recommendedKeepId);
    return initial;
  });
  const [migrateRefs, setMigrateRefs] = useState(true);
  const [busy, setBusy] = useState(false);

  const toggleKeep = (id: string) => {
    setKeepIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        if (next.size === 1) return next; // 至少保留 1 份
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const keepList = group.documents.filter((d) => keepIds.has(d.id));
  const deleteList = group.documents.filter((d) => !keepIds.has(d.id));

  const handleKeepAll = async () => {
    setBusy(true);
    try {
      await resolveDuplicateDocuments(clientId, {
        groupKey: group.groupKey,
        action: 'keep_all',
        keepV2DocumentIds: group.documents.map((d) => d.id),
        deleteV2DocumentIds: [],
        migrateReferences: false,
        note: '用户选择全部保留',
      });
      flash?.('success', '已标记为「全部保留」，下次扫描不再提示这组');
      onResolved();
      onClose();
    } catch (e) {
      flash?.('error', e instanceof Error ? e.message : '操作失败');
    } finally {
      setBusy(false);
    }
  };

  const handleDeleteOthers = async () => {
    if (deleteList.length === 0) return;
    setBusy(true);
    try {
      const result = await resolveDuplicateDocuments(clientId, {
        groupKey: group.groupKey,
        action: 'delete_others',
        keepV2DocumentIds: keepList.map((d) => d.id),
        deleteV2DocumentIds: deleteList.map((d) => d.id),
        migrateReferences: migrateRefs,
      });
      const refMigrated = result.migratedTaskAttachments + result.migratedEvidenceRefs + result.migratedAtomicFacts;
      flash?.('success', `已删除 ${result.deletedCount} 份（进回收站），迁移 ${refMigrated} 个引用`);
      onResolved();
      onClose();
    } catch (e) {
      flash?.('error', e instanceof Error ? e.message : '操作失败');
    } finally {
      setBusy(false);
    }
  };

  const handleOpenFile = async (doc: DuplicateDocumentItem) => {
    const target = doc.originalPath || doc.managedPath;
    if (!target) {
      flash?.('error', '文件路径缺失，无法预览');
      return;
    }
    try {
      await window.yiyuWorkbench.openPath(target);
    } catch (e) {
      flash?.('error', e instanceof Error ? e.message : '打开失败');
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-[80] flex items-center justify-center animate-in fade-in p-4">
      <div className="w-[min(96vw,1280px)] max-h-[92vh] rounded-[24px] bg-white shadow-[0_24px_80px_rgba(0,0,0,0.18)] overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="px-6 py-4 border-b border-slate-100 bg-amber-50/40">
          <div className="flex items-center justify-between">
            <h2 className="text-[16px] font-bold text-slate-900">对比 {group.count} 份重复文件</h2>
            <button type="button" onClick={onClose} className="rounded-full p-1 text-slate-400 hover:text-slate-700 hover:bg-white">
              <X size={18} />
            </button>
          </div>
          <p className="mt-1 text-[13px] text-slate-700 font-medium truncate" title={group.fileName}>📄 {group.fileName}</p>
          <p className="text-[11px] text-slate-500 mt-0.5">
            {group.groupType === 'same_content_hash' ? 'content_hash 完全一致（100% 真重复）' : '同文件名不同内容（可能是版本演进）'}
            <span className="mx-2">·</span>
            选择保留哪些（可多选，至少留 1 份）
          </p>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {group.documents.map((doc, idx) => {
              const isRec = doc.id === recommendedKeepId;
              const isKept = keepIds.has(doc.id);
              const refTotal = totalRefs(doc);
              return (
                <div
                  key={doc.id}
                  className={`rounded-[16px] border-2 p-4 transition-all ${
                    isKept ? 'border-emerald-300 bg-emerald-50/40' : 'border-slate-100 bg-white'
                  }`}
                >
                  <div className="flex items-baseline justify-between mb-3">
                    <span className="text-[11px] font-bold text-slate-500">#{idx + 1}</span>
                    {isRec && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-700">⭐ 推荐</span>}
                  </div>

                  <div className="space-y-2.5 text-[11px]">
                    <div>
                      <div className="text-[10px] text-slate-400 mb-0.5">📅 上传时间</div>
                      <div className="font-bold text-slate-800">{doc.importedAt ? doc.importedAt.slice(0, 16).replace('T', ' ') : '—'}</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-slate-400 mb-0.5">✓ 解析状态</div>
                      <div className="text-slate-700">{doc.parseStatus || '—'} · {doc.chunkCount} 段</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-slate-400 mb-0.5">📎 被引用</div>
                      {refTotal === 0 ? (
                        <div className="text-slate-400">— 暂无引用</div>
                      ) : (
                        <div className="space-y-0.5 text-slate-700">
                          {doc.refTaskAttachmentCount > 0 && <div>· {doc.refTaskAttachmentCount} 个任务附件</div>}
                          {doc.refEvidenceCardCount > 0 && <div>· {doc.refEvidenceCardCount} 张证据卡</div>}
                          {doc.refAtomicFactCount > 0 && <div>· {doc.refAtomicFactCount} 条原子事实</div>}
                        </div>
                      )}
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => void handleOpenFile(doc)}
                    className="mt-3 w-full inline-flex items-center justify-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-[11px] font-bold text-slate-600 hover:border-slate-300 hover:bg-slate-50"
                  >
                    🔍 打开预览
                  </button>

                  <label className={`mt-2 flex items-center justify-center gap-2 rounded-lg px-2 py-1.5 cursor-pointer select-none transition-colors ${isKept ? 'bg-emerald-100' : 'bg-slate-50 hover:bg-slate-100'}`}>
                    <input
                      type="checkbox"
                      className="cursor-pointer"
                      checked={isKept}
                      onChange={() => toggleKeep(doc.id)}
                    />
                    <span className={`text-[12px] font-bold ${isKept ? 'text-emerald-700' : 'text-slate-600'}`}>
                      {isKept ? '✓ 保留这份' : '保留这份'}
                    </span>
                  </label>
                </div>
              );
            })}
          </div>
        </div>

        <div className="px-6 py-4 border-t border-slate-100 bg-slate-50/60">
          <div className="text-[13px] text-slate-700 mb-2">
            当前选择：保留 <span className="font-bold text-emerald-700">{keepList.length}</span> 份
            {deleteList.length > 0 && (
              <span className="text-slate-600">
                {' · '}删除 <span className="font-bold text-rose-700">{deleteList.length}</span> 份
                <span className="ml-1 text-[11px] text-slate-400">（进回收站，30 天内可恢复）</span>
              </span>
            )}
          </div>
          {deleteList.length > 0 && (
            <label className="flex items-center gap-2 text-[12px] text-slate-700 mb-3 cursor-pointer select-none">
              <input type="checkbox" checked={migrateRefs} onChange={(e) => setMigrateRefs(e.target.checked)} />
              <span>自动把要删除文件上的引用搬到保留的版本</span>
              <span className="text-[10px] text-slate-400">（不勾会导致任务附件 / 证据卡断链）</span>
            </label>
          )}
          <div className="flex justify-between gap-2">
            <button
              type="button"
              onClick={() => void handleKeepAll()}
              disabled={busy}
              className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-[12px] font-bold text-slate-600 hover:border-slate-300 disabled:opacity-50"
            >
              全部保留（不再提示）
            </button>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={onClose}
                disabled={busy}
                className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-[12px] font-bold text-slate-600 hover:border-slate-300 disabled:opacity-50"
              >
                暂不处理
              </button>
              <button
                type="button"
                onClick={() => void handleDeleteOthers()}
                disabled={busy || deleteList.length === 0}
                className="rounded-xl bg-rose-600 px-4 py-2 text-[12px] font-bold text-white hover:bg-rose-700 disabled:opacity-50"
              >
                {busy ? '处理中…' : `删除 ${deleteList.length} 份，保留 ${keepList.length} 份`}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// 仅显示用户可编辑的业务文件类型。
// 排除：
// - .md / .txt（系统生成的客户档案、事件线快照、元数据等）
// - 没有扩展名的（如 client_overview / 事件线快照名）
// 这些是数据中心内部使用的"系统标识"，用户不应在重复管理界面看到/删除它们。
const USER_EDITABLE_FILE_EXTENSIONS = new Set([
  'doc', 'docx',
  'xls', 'xlsx', 'csv',
  'ppt', 'pptx',
  'pdf',
  'png', 'jpg', 'jpeg', 'webp', 'gif',
]);

function isUserEditableFile(fileName: string): boolean {
  const lastDot = fileName.lastIndexOf('.');
  if (lastDot < 0 || lastDot === fileName.length - 1) return false;
  return USER_EDITABLE_FILE_EXTENSIONS.has(fileName.slice(lastDot + 1).toLowerCase());
}

function filterUserEditableGroups(groups: DuplicateDocumentGroup[]): DuplicateDocumentGroup[] {
  return groups
    .map((g) => {
      // 任一份不是用户文件 → 整组隐藏（混杂业务+系统的组先放过，避免误操作）
      const docs = g.documents.filter((d) => isUserEditableFile(d.fileName));
      return { ...g, documents: docs, count: docs.length };
    })
    .filter((g) => g.documents.length >= 2);
}

function DuplicateDocumentsSection({ clientId, flash }: { clientId: string; flash?: (level: 'success' | 'error' | 'info', message: string) => void }) {
  const [groups, setGroups] = useState<DuplicateDocumentGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busyGroupKey, setBusyGroupKey] = useState<string>('');
  const [busyDocId, setBusyDocId] = useState<string>('');

  const reload = useCallback(() => {
    if (!clientId) { setGroups([]); return; }
    setLoading(true);
    setErr(null);
    getClientDuplicateDocuments(clientId)
      .then((raw) => setGroups(filterUserEditableGroups(raw)))
      .catch((e) => setErr(e instanceof Error ? e.message : '加载重复文件失败'))
      .finally(() => setLoading(false));
  }, [clientId]);

  useEffect(() => { reload(); }, [reload]);

  const totalRefsOf = (d: DuplicateDocumentItem) =>
    d.refTaskAttachmentCount + d.refEvidenceCardCount + d.refAtomicFactCount;

  // 单卡片上 🗑 删除一份：
  // - 不 reload（避免整个 list 重排，让用户找不到下一个想删的卡片）
  // - 直接在本地 state 把这份移除，其他卡片位置保持不变
  // - 引用自动迁到剩下的版本（migrateReferences=true）
  const handleDeleteOne = async (g: DuplicateDocumentGroup, doc: DuplicateDocumentItem) => {
    const remaining = g.documents.filter((d) => d.id !== doc.id);
    if (remaining.length === 0) {
      flash?.('error', '这是该组最后一份文件，无法单删 —— 请用整组「全部删除」');
      return;
    }
    if (!window.confirm(`删除「${doc.fileName.slice(0, 40)}」？\n\n文件进回收站，30 天内可恢复。\n关联到这份的任务附件/证据卡会自动迁移到剩下的版本。`)) return;
    setBusyDocId(doc.id);
    try {
      await resolveDuplicateDocuments(clientId, {
        groupKey: g.groupKey,
        action: 'delete_others',
        keepV2DocumentIds: remaining.map((d) => d.id),
        deleteV2DocumentIds: [doc.id],
        migrateReferences: true,
      });
      flash?.('success', '已删除，文件进回收站');
      // 不 reload —— 直接在本地 state 移除这份，保持其他卡片相对位置稳定
      setGroups((prev) =>
        prev
          .map((grp) => {
            if (grp.groupKey !== g.groupKey) return grp;
            const newDocs = grp.documents.filter((d) => d.id !== doc.id);
            return { ...grp, documents: newDocs, count: newDocs.length };
          })
          .filter((grp) => grp.documents.length >= 2),
      );
    } catch (e) {
      flash?.('error', e instanceof Error ? e.message : '删除失败');
    } finally {
      setBusyDocId('');
    }
  };

  // 整组「全部删除」：所有重复文件进回收站，引用自动 SET NULL（无目标可迁）
  const handleDeleteAll = async (g: DuplicateDocumentGroup) => {
    if (!window.confirm(
      `确认全部删除「${g.fileName.slice(0, 40)}」的 ${g.count} 份重复文件？\n\n所有文件进回收站，30 天内可恢复。\n关联到这些文件的任务附件 / 证据卡会变成「附件缺失」。`,
    )) return;
    setBusyGroupKey(g.groupKey);
    try {
      await resolveDuplicateDocuments(clientId, {
        groupKey: g.groupKey,
        action: 'delete_others',
        keepV2DocumentIds: [],
        deleteV2DocumentIds: g.documents.map((d) => d.id),
        migrateReferences: false,
      });
      flash?.('success', `已全部删除 ${g.count} 份（进回收站）`);
      // 整组消失了，直接从本地移除，避免 reload 重排其他 group
      setGroups((prev) => prev.filter((grp) => grp.groupKey !== g.groupKey));
    } catch (e) {
      flash?.('error', e instanceof Error ? e.message : '操作失败');
    } finally {
      setBusyGroupKey('');
    }
  };

  // 整组「保留最新」：自动按 importedAt 找最晚的那份，其他全删
  // 处理完后这组只剩 1 份不再是"重复"，直接从本地 state 移除该组，
  // 避免 reload 让其他 group 重新排序。
  const handleKeepLatest = async (g: DuplicateDocumentGroup) => {
    const sorted = [...g.documents].sort((a, b) => (b.importedAt || '').localeCompare(a.importedAt || ''));
    const latest = sorted[0];
    const toDelete = sorted.slice(1);
    if (toDelete.length === 0) return;
    if (!window.confirm(`保留最新版（${latest.importedAt.slice(0, 16).replace('T', ' ')}），其他 ${toDelete.length} 份进回收站？`)) return;
    setBusyGroupKey(g.groupKey);
    try {
      await resolveDuplicateDocuments(clientId, {
        groupKey: g.groupKey,
        action: 'delete_others',
        keepV2DocumentIds: [latest.id],
        deleteV2DocumentIds: toDelete.map((d) => d.id),
        migrateReferences: true,
      });
      flash?.('success', `已保留最新版，其他 ${toDelete.length} 份进回收站`);
      setGroups((prev) => prev.filter((grp) => grp.groupKey !== g.groupKey));
    } catch (e) {
      flash?.('error', e instanceof Error ? e.message : '操作失败');
    } finally {
      setBusyGroupKey('');
    }
  };

  // 「全部保留」：标记 group_key，下次扫描跳过
  const handleKeepAll = async (g: DuplicateDocumentGroup) => {
    setBusyGroupKey(g.groupKey);
    try {
      await resolveDuplicateDocuments(clientId, {
        groupKey: g.groupKey,
        action: 'keep_all',
        keepV2DocumentIds: g.documents.map((d) => d.id),
        deleteV2DocumentIds: [],
        migrateReferences: false,
      });
      flash?.('success', '已标记「全部保留」，下次不再提示这组');
      setGroups((prev) => prev.filter((grp) => grp.groupKey !== g.groupKey));
    } catch (e) {
      flash?.('error', e instanceof Error ? e.message : '操作失败');
    } finally {
      setBusyGroupKey('');
    }
  };

  const handleOpenFile = async (doc: DuplicateDocumentItem) => {
    const target = doc.originalPath || doc.managedPath;
    if (!target) { flash?.('error', '文件路径缺失'); return; }
    try { await window.yiyuWorkbench.openPath(target); }
    catch (e) { flash?.('error', e instanceof Error ? e.message : '打开失败'); }
  };

  if (!clientId) return null;
  if (loading) {
    return (
      <div className="mb-6 rounded-2xl border border-dashed border-slate-200 bg-slate-50/60 px-4 py-3 text-[12px] text-slate-400">
        正在扫描重复文件…
      </div>
    );
  }
  if (err) {
    return <div className="mb-6 rounded-xl border border-rose-100 bg-rose-50 px-3 py-2 text-[12px] text-rose-700">{err}</div>;
  }
  if (groups.length === 0) {
    return (
      <div className="mb-6 rounded-2xl border border-emerald-100 bg-emerald-50/60 px-4 py-3 text-[12px] text-emerald-700">
        ✓ 未发现重复文件 —— 资料库里没有同内容或同文件名被上传多次的情况。
      </div>
    );
  }
  const totalCopies = groups.reduce((sum, g) => sum + g.count, 0);
  const wasted = totalCopies - groups.length;

  return (
    <section className="mb-6 rounded-[24px] border border-slate-100 bg-white p-5 sm:p-6 shadow-[0_2px_10px_rgba(0,0,0,0.02)]">
      {/* Header —— 跟 AssetScoreBreakdownPanel 风格一致 */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between mb-5">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full border border-amber-100 bg-amber-50 px-2.5 py-1 text-[11px] font-bold text-amber-700 mb-2">
            <Layers size={12} />
            重复文件 {groups.length} 组
          </div>
          <h3 className="text-[15px] font-bold text-slate-800">同名 / 同内容文件待整理</h3>
          <p className="mt-1 text-[12px] leading-6 text-slate-400">
            AI 通过内容指纹发现同一份文件被上传多次。逐张卡片选择打开预览或移入回收站（30 天可恢复）。
          </p>
        </div>
        <div className="rounded-full bg-slate-50 px-3 py-1 text-[11px] font-bold text-slate-500 self-start tabular-nums">
          {totalCopies} 份 · 多余 {wasted}
        </div>
      </div>

      <div className="space-y-5">
        {groups.map((g) => {
          const isGroupBusy = busyGroupKey === g.groupKey;
          // 推荐策略简化：只标"最新"（importedAt 最晚的那份）。
          // 用户原话"只需要知道哪个是最新的就好了" —— 不再用引用计数做复杂的"推荐"。
          const latestSorted = [...g.documents].sort((a, b) => (b.importedAt || '').localeCompare(a.importedAt || ''));
          const latestId = latestSorted[0]?.id;
          return (
            <div key={g.groupKey} className="rounded-[18px] border border-slate-100 bg-slate-50/40 p-4">
              {/* Group header */}
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1.5">
                    <span
                      className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${
                        g.groupType === 'same_content_hash'
                          ? 'border border-rose-100 bg-rose-50 text-rose-700'
                          : 'border border-amber-100 bg-amber-50 text-amber-700'
                      }`}
                    >
                      {g.groupType === 'same_content_hash' ? `完全重复 × ${g.count}` : `同名 × ${g.count}`}
                    </span>
                  </div>
                  <div className="text-[14px] font-bold text-slate-800 truncate" title={g.fileName}>
                    {g.fileName}
                  </div>
                </div>
                <div className="flex gap-2 shrink-0 flex-wrap">
                  <button
                    type="button"
                    onClick={() => void handleKeepLatest(g)}
                    disabled={isGroupBusy}
                    className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-[11px] font-bold text-emerald-700 transition-colors hover:bg-emerald-100 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    保留最新
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleKeepAll(g)}
                    disabled={isGroupBusy}
                    className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-bold text-slate-600 transition-colors hover:border-slate-300 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    全部保留
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleDeleteAll(g)}
                    disabled={isGroupBusy}
                    className="inline-flex items-center gap-1.5 rounded-full border border-rose-200 bg-rose-50 px-3 py-1.5 text-[11px] font-bold text-rose-700 transition-colors hover:bg-rose-100 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    全部删除
                  </button>
                </div>
              </div>

              {/* Cards grid —— 参考客户工作台文件卡片：文件类型图标 + 文件名 + 大小 + 日期 */}
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                {g.documents.map((d) => {
                  const isLatest = d.id === latestId;
                  const isDocBusy = busyDocId === d.id;
                  const iconPath = d.originalPath || d.managedPath || d.fileName;
                  const dateStr = d.importedAt
                    ? d.importedAt.slice(0, 10).replace(/-/g, '·')
                    : '—';
                  return (
                    <div
                      key={d.id}
                      className={`group flex flex-col rounded-[16px] bg-white p-4 transition-all hover:shadow-[0_4px_16px_rgba(15,23,42,0.06)] ${
                        isLatest
                          ? 'border border-emerald-200 ring-1 ring-emerald-100'
                          : 'border border-slate-100'
                      }`}
                    >
                      {/* Top: file icon + 「最新」chip */}
                      <div className="flex items-start justify-between mb-3">
                        <FileTypeIcon path={iconPath} size={44} />
                        {isLatest && (
                          <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700">
                            <Star size={9} className="fill-emerald-700" />
                            最新
                          </span>
                        )}
                      </div>

                      {/* File name */}
                      <div
                        className="text-[12.5px] font-bold text-slate-800 leading-[1.5] line-clamp-2 mb-2 min-h-[38px]"
                        title={d.fileName}
                      >
                        {d.fileName}
                      </div>

                      {/* Meta: size + date */}
                      <div className="text-[11px] text-slate-500 tabular-nums mb-3 flex-1">
                        <span className="font-semibold">{formatFileSizeBytes(d.fileSizeBytes)}</span>
                        <span className="mx-1.5 text-slate-300">·</span>
                        <span>{dateStr}</span>
                      </div>

                      {/* Actions */}
                      <div className="flex gap-1.5">
                        <button
                          type="button"
                          onClick={() => void handleOpenFile(d)}
                          className="flex-1 inline-flex items-center justify-center gap-1 rounded-lg border border-slate-200 bg-white py-1.5 text-[11px] font-bold text-slate-600 transition-colors hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
                          title="用系统应用打开（Word / WPS / Pages）"
                        >
                          <ExternalLink size={11} />
                          打开
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleDeleteOne(g, d)}
                          disabled={isDocBusy || isGroupBusy}
                          className="inline-flex items-center justify-center rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-slate-400 transition-colors hover:border-rose-200 hover:bg-rose-50 hover:text-rose-600 disabled:opacity-40 disabled:cursor-not-allowed"
                          title="移到回收站（30 天可恢复）"
                          aria-label="移到回收站"
                        >
                          {isDocBusy ? <span className="text-[11px]">…</span> : <Trash2 size={12} />}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

// 文件大小格式化：B / KB / MB / GB
function formatFileSizeBytes(bytes: number | null | undefined): string {
  if (!bytes || bytes <= 0) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function ContradictionsTab({
  clientOptions,
  selectedClientId,
  onClientChange,
  flash,
}: {
  clientOptions: Array<{ id: string; name: string }>;
  selectedClientId: string;
  onClientChange: (id: string) => void;
  flash?: (level: 'success' | 'error' | 'info', message: string) => void;
}) {
  const [contradictions, setContradictions] = useState<FactContradictionRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string>('');

  const reload = useCallback(async () => {
    if (!selectedClientId) {
      setContradictions([]);
      return;
    }
    setLoading(true);
    setErr(null);
    try {
      const resp = await getClientContradictions(selectedClientId, { status: 'pending', limit: 50 });
      setContradictions(resp.contradictions);
    } catch (e) {
      setErr(e instanceof Error ? e.message : '加载矛盾失败');
      setContradictions([]);
    } finally {
      setLoading(false);
    }
  }, [selectedClientId]);

  useEffect(() => { void reload(); }, [reload]);

  const handleReview = async (id: string, status: 'dismissed' | 'resolved') => {
    try {
      setBusy(id);
      await reviewContradiction(id, { reviewStatus: status });
      flash?.('success', status === 'resolved' ? '矛盾已标为已解决' : '矛盾已忽略');
      await reload();
    } catch (e) {
      flash?.('error', e instanceof Error ? e.message : '处理矛盾失败');
    } finally {
      setBusy('');
    }
  };

  return (
    <section className="rounded-[28px] border border-slate-100 bg-white p-6 shadow-[0_8px_28px_rgba(15,23,42,0.05)]">
      <div className="flex items-center justify-between mb-5">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-rose-100 bg-rose-50 px-3 py-1 text-[11px] font-bold text-rose-700 mb-2">
            <AlertOctagon size={13} />
            矛盾 & 待确认
          </div>
          <p className="text-[12px] text-slate-500">AI 在你们资料里发现的「同一件事说法不一」—— Karpathy 说：矛盾是资产，不是错误。</p>
        </div>
        <TabClientPicker clientOptions={clientOptions} selectedClientId={selectedClientId} onClientChange={onClientChange} />
      </div>
      {!selectedClientId && (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/60 px-4 py-8 text-center text-[12px] text-slate-400">
          先选一个客户，查看 AI 检测到的重复文件和事实矛盾。
        </div>
      )}
      <DuplicateDocumentsSection clientId={selectedClientId} flash={flash} />
      {err && <div className="mb-4 rounded-xl border border-rose-100 bg-rose-50 px-3 py-2 text-[12px] text-rose-700">{err}</div>}
      {selectedClientId && !loading && contradictions.length === 0 && !err && (
        <div className="rounded-2xl border border-dashed border-emerald-100 bg-emerald-50/40 px-4 py-8 text-center text-[12px] text-emerald-700">
          ✓ 暂无待确认的事实矛盾。AI 觉得这位客户的资料内部一致。
        </div>
      )}
      {selectedClientId && loading && (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/60 px-4 py-8 text-center text-[12px] text-slate-400">扫描中…</div>
      )}
      {contradictions.length > 0 && (
        <div className="space-y-4">
          {contradictions.map((c) => (
            <div key={c.id} className="rounded-[20px] border border-rose-100/80 bg-rose-50/30 px-5 py-4">
              <div className="flex items-baseline justify-between mb-3">
                <div className="text-[13px] font-bold text-slate-800">
                  <span className="text-rose-700">{c.subjectText}</span> 的 <span className="text-rose-700">{c.attribute}</span>
                </div>
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${c.severity === 'high' ? 'bg-rose-100 text-rose-700' : c.severity === 'medium' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-600'}`}>
                  {c.severity === 'high' ? '严重' : c.severity === 'medium' ? '中等' : '一般'}
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                <div className="rounded-[14px] border border-slate-200 bg-white px-3 py-2.5">
                  <div className="text-[10px] font-bold text-slate-400 mb-1">说法 A</div>
                  <div className="text-[12px] font-bold text-slate-800 mb-1.5">{c.valueA}</div>
                  <div className="text-[10px] text-slate-500 line-clamp-2 leading-[1.6]">{c.evidenceA}</div>
                  {c.docAFileName && <div className="mt-1.5 text-[10px] text-slate-400 truncate" title={c.docAFileName}>来源：{c.docAFileName}</div>}
                </div>
                <div className="rounded-[14px] border border-slate-200 bg-white px-3 py-2.5">
                  <div className="text-[10px] font-bold text-slate-400 mb-1">说法 B</div>
                  <div className="text-[12px] font-bold text-slate-800 mb-1.5">{c.valueB}</div>
                  <div className="text-[10px] text-slate-500 line-clamp-2 leading-[1.6]">{c.evidenceB}</div>
                  {c.docBFileName && <div className="mt-1.5 text-[10px] text-slate-400 truncate" title={c.docBFileName}>来源：{c.docBFileName}</div>}
                </div>
              </div>
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  disabled={busy === c.id}
                  onClick={() => void handleReview(c.id, 'dismissed')}
                  className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] font-bold text-slate-600 hover:border-slate-300 disabled:opacity-50"
                >
                  假告警，忽略
                </button>
                <button
                  type="button"
                  disabled={busy === c.id}
                  onClick={() => void handleReview(c.id, 'resolved')}
                  className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[11px] font-bold text-emerald-700 hover:bg-emerald-100 disabled:opacity-50"
                >
                  {busy === c.id ? '处理中…' : '已确认正解'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function KnowledgeHealthTab({
  clientOptions,
  selectedClientId,
  onClientChange,
}: {
  clientOptions: Array<{ id: string; name: string }>;
  selectedClientId: string;
  onClientChange: (id: string) => void;
}) {
  const [status, setStatus] = useState<ClientKnowledgeStatus | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selectedClientId) { setStatus(null); return; }
    setLoading(true);
    getClientKnowledgeStatus(selectedClientId)
      .then(setStatus)
      .catch((e) => console.warn('[strategic] knowledge status failed', e))
      .finally(() => setLoading(false));
  }, [selectedClientId]);

  return (
    <section className="rounded-[28px] border border-slate-100 bg-white p-6 shadow-[0_8px_28px_rgba(15,23,42,0.05)]">
      <div className="flex items-center justify-between mb-5">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-amber-100 bg-amber-50 px-3 py-1 text-[11px] font-bold text-amber-700 mb-2">
            <BrainCircuit size={13} />
            资料健康
          </div>
          <p className="text-[12px] text-slate-500">这位客户的知识库目前状态。学习没有尽头 —— 看的是绝对数和颜色，不是百分比。</p>
        </div>
        <TabClientPicker clientOptions={clientOptions} selectedClientId={selectedClientId} onClientChange={onClientChange} />
      </div>
      {!selectedClientId && (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/60 px-4 py-8 text-center text-[12px] text-slate-400">
          先选一个客户。
        </div>
      )}
      {selectedClientId && !loading && status && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
            <div className="rounded-[18px] border border-emerald-100 bg-emerald-50/60 px-4 py-3">
              <div className="text-[10px] font-bold text-emerald-700">已确认事实</div>
              <div className="text-[24px] font-bold text-emerald-800 mt-1">{status.confirmedFacts}</div>
              {status.weeklyDelta.confirmedFacts > 0 && <div className="text-[10px] text-emerald-600 mt-0.5">本周 +{status.weeklyDelta.confirmedFacts}</div>}
            </div>
            <div className={`rounded-[18px] border px-4 py-3 ${status.pendingThoughts > 0 ? 'border-amber-100 bg-amber-50/60' : 'border-slate-100 bg-white'}`}>
              <div className="text-[10px] font-bold text-slate-500">待确认思考</div>
              <div className={`text-[24px] font-bold mt-1 ${status.pendingThoughts > 0 ? 'text-amber-700' : 'text-slate-700'}`}>{status.pendingThoughts}</div>
              {status.weeklyDelta.newThoughts > 0 && <div className="text-[10px] text-amber-600 mt-0.5">本周 +{status.weeklyDelta.newThoughts}</div>}
            </div>
            <div className={`rounded-[18px] border px-4 py-3 ${status.activeContradictions > 0 ? 'border-rose-100 bg-rose-50/60' : 'border-slate-100 bg-white'}`}>
              <div className="text-[10px] font-bold text-slate-500">矛盾点</div>
              <div className={`text-[24px] font-bold mt-1 ${status.activeContradictions > 0 ? 'text-rose-700' : 'text-slate-700'}`}>{status.activeContradictions}</div>
              <div className="text-[10px] text-slate-500 mt-0.5">{status.activeContradictions > 0 ? '待你拍板' : '暂无打架'}</div>
            </div>
            <div className={`rounded-[18px] border px-4 py-3 ${status.knowledgeGaps > 0 ? 'border-amber-100 bg-amber-50/40' : 'border-slate-100 bg-white'}`}>
              <div className="text-[10px] font-bold text-slate-500">信息缺口</div>
              <div className={`text-[24px] font-bold mt-1 ${status.knowledgeGaps > 0 ? 'text-amber-700' : 'text-slate-700'}`}>{status.knowledgeGaps}</div>
              {status.weeklyDelta.confirmedJudgments > 0 && <div className="text-[10px] text-emerald-600 mt-0.5">本周采纳 +{status.weeklyDelta.confirmedJudgments}</div>}
            </div>
          </div>

          {/* AI 待办 —— Stage B 扇出真正暴露给用户看 */}
          {(status.pendingActions && status.pendingActions.length > 0) ? (
            <div className="mb-5 rounded-[20px] border border-blue-100 bg-blue-50/40 p-4">
              <div className="flex items-baseline justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className="inline-flex items-center gap-1.5 rounded-full bg-blue-100 px-2.5 py-1 text-[11px] font-bold text-blue-800">
                    🤖 AI 待办 {status.pendingActions.length}
                  </div>
                  <span className="text-[11px] text-blue-700">
                    {status.recentFanoutCount > 0 ? `近 7 天因新资料触发了 ${status.recentFanoutCount} 次扇出` : '等你拍板的事项'}
                  </span>
                </div>
              </div>
              <p className="mb-3 text-[11px] leading-[1.7] text-blue-700/80">
                新资料 ingest 时 AI 自动识别到「这些事可能需要你看一下」，标记后等你在原位置拍板。
              </p>
              <div className="space-y-2">
                {status.pendingActions.map((act, idx) => (
                  <div key={`${act.actionType}-${act.entityId}-${idx}`} className="rounded-[14px] border border-blue-100 bg-white px-3 py-2.5">
                    <div className="flex items-baseline justify-between gap-2 mb-1">
                      <div className="flex items-center gap-2">
                        {act.actionType === 'judgment_needs_reevaluation' && (
                          <span className="rounded-full border border-rose-100 bg-rose-50 px-2 py-0.5 text-[10px] font-bold text-rose-700">⚠️ 判断需重审</span>
                        )}
                        {act.actionType === 'profile_needs_review' && (
                          <span className="rounded-full border border-amber-100 bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700">📝 客户画像需复审</span>
                        )}
                        {act.actionType === 'thought_refresh_pending' && (
                          <span className="rounded-full border border-violet-100 bg-violet-50 px-2 py-0.5 text-[10px] font-bold text-violet-700">💭 思考待刷新</span>
                        )}
                      </div>
                      {act.triggeredAt && (
                        <span className="text-[10px] text-slate-400 tabular-nums shrink-0">{act.triggeredAt.slice(0, 10)}</span>
                      )}
                    </div>
                    <div className="text-[12px] font-bold text-slate-800 line-clamp-1 mb-1" title={act.entityLabel}>{act.entityLabel}</div>
                    <p className="text-[11px] leading-[1.6] text-slate-600 line-clamp-2" title={act.reason}>{act.reason}</p>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-[10px] text-blue-700/60">
                💡 处理方式：判断需重审 → 在「判断 & 思考」tab 编辑；客户画像 → 客户档案页修订；思考 → 战略陪伴主动「刷新研判」。
              </p>
            </div>
          ) : (
            <div className="mb-5 rounded-2xl border border-emerald-100 bg-emerald-50/40 px-4 py-3 text-[12px] text-emerald-700">
              ✓ 暂无 AI 待办 —— 新资料 ingest 时如有触发，会出现在这一区。
            </div>
          )}

          <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/60 px-4 py-4 text-[12px] leading-[1.7] text-slate-500">
            <div className="font-bold text-slate-700 mb-1">Stage 5 即将补全</div>
            陈旧事实检测 · 孤立实体扫描 · 知识健康度趋势 — 这些 lint 报告会出现在这一区。
          </div>
        </>
      )}
    </section>
  );
}

function OutputsTab({
  clientOptions,
  selectedClientId,
  onClientChange,
}: {
  clientOptions: Array<{ id: string; name: string }>;
  selectedClientId: string;
  onClientChange: (id: string) => void;
}) {
  return (
    <section className="rounded-[28px] border border-slate-100 bg-white p-6 shadow-[0_8px_28px_rgba(15,23,42,0.05)]">
      <div className="flex items-center justify-between mb-5">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-violet-100 bg-violet-50 px-3 py-1 text-[11px] font-bold text-violet-700 mb-2">
            <FileText size={13} />
            输出沉淀
          </div>
          <p className="text-[12px] text-slate-500">从问答和思考流转出来的产出：已采纳判断 / proposal 草稿 / 任务 — 闭环的"果实"区。</p>
        </div>
        <TabClientPicker clientOptions={clientOptions} selectedClientId={selectedClientId} onClientChange={onClientChange} />
      </div>
      {!selectedClientId && (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/60 px-4 py-8 text-center text-[12px] text-slate-400">
          先选一个客户。
        </div>
      )}
      {selectedClientId && (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/60 px-4 py-4 text-[12px] leading-[1.7] text-slate-500">
          <div className="font-bold text-slate-700 mb-1">即将上线</div>
          这里会聚合：已采纳的 judgment_versions（来自工作台「采纳为判断」+ 战略陪伴 thoughts 采纳）<br />
          + proposal_records 草稿 / 待审 / 已批准全周期<br />
          + 从答案生成的任务 + 转事件线
        </div>
      )}
    </section>
  );
}

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
      .catch((error) => {
        // 数字资产 dashboard 拉不到时 UI 会回退到空态，不弹错误打扰用户；
        // 但 console.warn 保留 debug 信号，比裸 () => null 强
        console.warn('[strategic] getDigitalAssetDashboard failed', error);
        setAssetDashboard(null);
      });
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
      try {
        await reviewStrategicThought(thoughtId, { action, note, createJudgment: action === 'confirm' });
        await loadThoughts();
      } catch (error) {
        const msg = error instanceof Error ? error.message : '研判评审失败';
        flash?.('error', msg);
      }
    },
    [flash, loadThoughts],
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
      try {
        await updateStrategicThoughtState(thought.id, { action: thought.isFavorite ? 'unfavorite' : 'favorite' });
        await loadThoughts();
      } catch (error) {
        const msg = error instanceof Error ? error.message : '收藏状态更新失败';
        flash?.('error', msg);
      }
    },
    [flash, loadThoughts],
  );

  const handleDeleteThought = useCallback(
    async (thought: StrategicThought) => {
      try {
        await updateStrategicThoughtState(thought.id, { action: 'delete' });
        await loadThoughts();
      } catch (error) {
        const msg = error instanceof Error ? error.message : '删除研判失败';
        flash?.('error', msg);
      }
    },
    [flash, loadThoughts],
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
          {activeTab === 'contradictions' && (
            <ContradictionsTab
              clientOptions={thoughtClientOptions}
              selectedClientId={thoughtClientId}
              onClientChange={(id) => {
                setThoughtClientId(id);
                if (id) onClientChange?.(id);
              }}
              flash={flash}
            />
          )}
          {activeTab === 'health' && (
            <KnowledgeHealthTab
              clientOptions={thoughtClientOptions}
              selectedClientId={thoughtClientId}
              onClientChange={(id) => {
                setThoughtClientId(id);
                if (id) onClientChange?.(id);
              }}
            />
          )}
          {activeTab === 'outputs' && (
            <OutputsTab
              clientOptions={thoughtClientOptions}
              selectedClientId={thoughtClientId}
              onClientChange={(id) => {
                setThoughtClientId(id);
                if (id) onClientChange?.(id);
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default StrategicBrainView;
