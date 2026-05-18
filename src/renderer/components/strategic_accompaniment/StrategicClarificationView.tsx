/**
 * 战略陪伴 · 事实澄清面板（Phase 1.5c — 6 维度故事网）
 *
 * 替换原"矛盾&待确认"Tab。主体改为 AI 写的 6 段叙事 (云端共享, 共同编织),
 * 旧 5 区块 db dump 降为"AI 引用源·字典层"折叠在底部。
 *
 * 设计原则 (顾源源 2026/5/16 原话):
 *   - "看到整个故事 (关键人/角色/这是一件什么事/承诺)" → 6 段叙事
 *   - "用户语音/打字澄清 → AI 更新故事网" → 每段含澄清入口
 *   - "凡是跟项目有关的人都关联到这个面板共同编织" → contributors 追溯
 *   - "数据中心要把关键信息串成一张网, 在功能界面发挥作用" → 加工层缺口诚实暴露
 *
 * 6 维度:
 *   1. essence       项目本质
 *   2. people        关键人物网
 *   3. history       来龙去脉
 *   4. commitments   承诺网
 *   5. risks         卡点与风险
 *   6. next          下一步
 */

import { useCallback, useEffect, useState } from 'react';
import {
  Users, Target, Clock, AlertCircle, CheckCircle, HelpCircle,
  Mic, Type, ExternalLink, ChevronDown, FileSearch, Briefcase,
  Sparkles, MessageCircle, Building2, RefreshCw, Database, GitBranch,
  Compass, Network, History, Handshake, AlertTriangle, ArrowRight,
  UploadCloud,
} from 'lucide-react';
import {
  getClientClarificationContext,
  getClientDuplicateDocuments,
  resolveDuplicateDocuments,
  getClientNarrative,
  listClientNarrativeClarifications,
  submitClientNarrativeClarification,
  regenerateClientNarrative,
  type ClarificationContext,
  type ClarificationEventLine,
  type ClarificationTimelineItem,
  type ClarificationPerson,
  type ClarificationCommitment,
  type ClarificationNeed,
  type ClarificationProfile,
  type DuplicateDocumentGroup,
  type ClientNarrative,
  type NarrativeDimensionRecord,
  type NarrativeDimensionKey,
  type NarrativeClarification,
} from '../../lib/api';
import { GlossaryAttributeReviewSection } from './GlossaryAttributeReviewSection';
import { UnifiedTodoSection } from './UnifiedTodoSection';

interface StrategicClarificationViewProps {
  clientOptions: Array<{ id: string; name: string }>;
  selectedClientId: string;
  onClientChange: (id: string) => void;
  flash?: (level: 'success' | 'error' | 'info', message: string) => void;
}

type Confidence = 'high' | 'medium' | 'low';

const CONFIDENCE_META: Record<Confidence, { label: string; bg: string; text: string; icon: typeof CheckCircle }> = {
  high: { label: '已更新', bg: 'bg-emerald-50', text: 'text-emerald-700', icon: CheckCircle },
  medium: { label: '部分确认', bg: 'bg-amber-50', text: 'text-amber-700', icon: AlertCircle },
  low: { label: '待补充', bg: 'bg-slate-100', text: 'text-slate-500', icon: HelpCircle },
};

export function StrategicClarificationView({
  clientOptions,
  selectedClientId,
  onClientChange,
  flash,
}: StrategicClarificationViewProps) {
  const [narrative, setNarrative] = useState<ClientNarrative | null>(null);
  const [clarifications, setClarifications] = useState<NarrativeClarification[]>([]);
  const [ctx, setCtx] = useState<ClarificationContext | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [regenerating, setRegenerating] = useState(false);
  const [refreshTodoKey, setRefreshTodoKey] = useState(0);

  const loadAll = useCallback(async (clientId: string) => {
    setLoading(true);
    setError(null);
    try {
      const [n, c, x] = await Promise.all([
        getClientNarrative(clientId),
        listClientNarrativeClarifications(clientId),
        getClientClarificationContext(clientId).catch(() => null),
      ]);
      setNarrative(n);
      setClarifications(c.clarifications);
      setCtx(x);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败');
      setNarrative(null);
      setClarifications([]);
      setCtx(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedClientId) {
      setNarrative(null);
      setClarifications([]);
      setCtx(null);
      return;
    }
    let mounted = true;
    void loadAll(selectedClientId).then(() => { if (!mounted) return; });
    return () => { mounted = false; };
  }, [selectedClientId, loadAll]);

  const handleClarify = async (dimension: NarrativeDimensionKey, answer: string, question?: string) => {
    if (!selectedClientId || !answer.trim()) return;
    try {
      await submitClientNarrativeClarification(selectedClientId, {
        dimension,
        answer: answer.trim(),
        question,
      });
      flash?.('success', '已提交澄清, 点"重新生成"让 AI 更新故事网。');
      const c = await listClientNarrativeClarifications(selectedClientId);
      setClarifications(c.clarifications);
      setNarrative((cur) =>
        cur ? { ...cur, openClarificationsCount: cur.openClarificationsCount + 1 } : cur,
      );
    } catch (err) {
      flash?.('error', err instanceof Error ? err.message : '提交失败');
    }
  };

  const handleRegenerate = async () => {
    if (!selectedClientId) return;
    setRegenerating(true);
    try {
      const fresh = await regenerateClientNarrative(selectedClientId, { trigger: 'manual', force: true });
      setNarrative(fresh);
      const c = await listClientNarrativeClarifications(selectedClientId);
      setClarifications(c.clarifications);
      flash?.('success', `已重新生成 v${fresh.rev} (生成方: ${fresh.generator})`);
    } catch (err) {
      flash?.('error', err instanceof Error ? err.message : '生成失败');
    } finally {
      setRegenerating(false);
    }
  };

  return (
    <section className="rounded-[28px] border border-slate-100 bg-white p-6 shadow-[0_8px_28px_rgba(15,23,42,0.05)]">
      {/* 顶部: 客户名 + 极简精选 4 项 (左) + 客户选择器 (右), 同行平齐 */}
      <div className="flex items-baseline justify-between gap-4 mb-5 flex-wrap">
        <div className="flex items-baseline gap-3 min-w-0 flex-1 flex-wrap">
          <h2 className="text-[20px] font-bold text-slate-900 shrink-0">
            {clientOptions.find((c) => c.id === selectedClientId)?.name ?? ''}
          </h2>
          {(() => {
            const aiLine = narrative?.dataLayerGaps.find((g) => g.startsWith('✓ AI 本次看到'));
            if (!aiLine) return null;
            const pick = (re: RegExp): string | null => {
              const m = aiLine.match(re);
              return m ? m[1] : null;
            };
            const docs = pick(/(\d+)\s*份原始资料/);
            const persons = pick(/(\d+)\s*人物/);
            const dates = pick(/(\d+)\s*关键日期/);
            const moneys = pick(/(\d+)\s*金额/);
            const Item = ({ n, unit }: { n: string; unit: string }) => (
              <span>
                <span className="font-semibold text-slate-700">{n}</span>
                <span className="text-slate-400 ml-0.5">{unit}</span>
              </span>
            );
            return (
              <span className="text-[12px] text-slate-500 leading-relaxed">
                基于
                {docs && <> <Item n={docs} unit="份资料" /> · </>}
                {persons && <Item n={persons} unit="位人物" />}
                {dates && <> · <Item n={dates} unit="个时间节点" /></>}
                {moneys && <> · <Item n={moneys} unit="笔金额" /></>}
              </span>
            );
          })()}
        </div>
        <ClientPicker clientOptions={clientOptions} selectedClientId={selectedClientId} onClientChange={onClientChange} />
      </div>

      {!selectedClientId && <EmptyState text="先选一个客户, 看 AI 当前对它的理解。" />}
      {selectedClientId && loading && <EmptyState text="加载中..." />}
      {selectedClientId && error && (
        <div className="rounded-2xl border border-rose-100 bg-rose-50 px-4 py-3 text-[12px] text-rose-700">
          {error}
        </div>
      )}

      {selectedClientId && narrative && !loading && (
        <NarrativePanel
          narrative={narrative}
          clarifications={clarifications}
          onClarify={handleClarify}
          onRegenerate={handleRegenerate}
          regenerating={regenerating}
          clientName={clientOptions.find((c) => c.id === selectedClientId)?.name ?? ''}
          refreshTodoKey={refreshTodoKey}
        />
      )}

      {/* M1 · 字典待审 (学霸笔记本入口) — 在 6 段叙事下方, 引用源折叠之上 */}
      {selectedClientId && (
        <GlossaryAttributeReviewSection
          clientId={selectedClientId}
          flash={flash}
          onChanged={() => {
            // 字典 date 类点 [已完成] 后, 后端启发式联动 task done; 这里触发 UnifiedTodoSection 重新拉
            setRefreshTodoKey((k) => k + 1);
          }}
        />
      )}

      {/* 底部 · AI 引用源·字典层 (旧 5 区块折叠) */}
      {selectedClientId && ctx && (
        <div className="mt-6">
          <ReferenceLayerSection ctx={ctx} />
        </div>
      )}

      {/* 数据卫生折叠 */}
      {selectedClientId && (
        <div className="mt-4">
          <DataHygieneSection clientId={selectedClientId} flash={flash} />
        </div>
      )}
    </section>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 6 维度故事网主面板
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const DIMENSION_META: Record<NarrativeDimensionKey, {
  label: string;
  icon: typeof Compass;
  hint: string;
}> = {
  // v1.0 新 6 层
  essence:        { label: '项目介绍',     icon: Compass,       hint: '客户机构是谁 / 赛道 / 行业定位 / 影响力' },
  cooperation:    { label: '合作关系',     icon: Handshake,     hint: '益语跟客户的服务关系 / 合作周期 / 核心交付' },
  business_intro: { label: '业务介绍',     icon: Briefcase,     hint: '客户机构内含项目逐个详介' },
  people:         { label: '关键人物',     icon: Network,       hint: '益语方 + 客户方 + 每个项目对应角色' },
  timeline:       { label: '时间线',       icon: History,       hint: '合作里程碑 (起点→转折→现状)' },
  next_steps:     { label: '承诺与下一步', icon: ArrowRight,    hint: '已有承诺 + 顾问推荐的下一步' },
  // 兼容旧 rev (废弃但仍可能从云端拿到)
  history:        { label: '来龙去脉 (旧)',     icon: History,       hint: '已废弃, 见时间线' },
  commitments:    { label: '承诺网 (旧)',       icon: Handshake,     hint: '已废弃, 见承诺与下一步' },
  risks:          { label: '卡点与风险 (旧)',   icon: AlertTriangle, hint: '已废弃, 隐含在下一步里' },
  next:           { label: '下一步 (旧)',       icon: ArrowRight,    hint: '已废弃, 见承诺与下一步' },
};

const DIMENSION_ORDER: NarrativeDimensionKey[] = [
  // 业务介绍 在 合作关系 之上 (用户要求: 先了解业务, 再看合作)
  'essence', 'business_intro', 'cooperation', 'people', 'timeline', 'next_steps',
  // 旧 dim 兼容显示在最后, 实际新 rev 不会有
  'history', 'commitments', 'risks', 'next',
];

// ────────────────────────────────────────────────────────────
// 业务介绍 — 启发式分段渲染
// 策略 (按优先级尝试): markdown headings → 数字列表 → bullet → 大段中按"项目名:" 切
// ────────────────────────────────────────────────────────────
interface Segment {
  title: string;
  body: string;
  source?: string;  // 从 body 末尾 [来自: X] 抽出
}

function parseBusinessIntro(text: string): Segment[] | null {
  const t = (text || '').trim();
  if (!t) return null;

  // 1. Markdown headings (## XX / ### XX)
  const headingRe = /^#{1,6}\s+(.+)$/gm;
  const headingMatches = Array.from(t.matchAll(headingRe));
  if (headingMatches.length >= 2) {
    const segs: Segment[] = [];
    for (let i = 0; i < headingMatches.length; i++) {
      const m = headingMatches[i];
      const start = (m.index ?? 0) + m[0].length;
      const end = i + 1 < headingMatches.length ? headingMatches[i + 1].index ?? t.length : t.length;
      segs.push({ title: m[1].trim(), body: t.slice(start, end).trim() });
    }
    return segs;
  }

  // 2. 数字编号列表 — 行内或跨行都能切
  //    "1. 心灵魔法学院：xxx 2. 心盛计划：xxx 3. ..." (一段) 或 "1. xxx\n2. yyy" (多行)
  //    不再用 ^ 行首锚定, 用 lookbehind (开头/句号/换行/空格 后) + 数字
  const numberRe = /(?:^|[。\n]|\s)(\d+|[①②③④⑤⑥⑦⑧⑨⑩])[\.、)]\s*([^：:0-9]{2,30})[：:]([^]+?)(?=(?:[。\n\s]\d+[\.、)]|[①②③④⑤⑥⑦⑧⑨⑩][\.、)]?)|$)/g;
  const numberMatches = Array.from(t.matchAll(numberRe));
  if (numberMatches.length >= 2) {
    const segs: Segment[] = [];
    const sourceRe = /\s*\[来自[::]\s*([^\]]+)\]\s*$/;
    for (const m of numberMatches) {
      const title = m[2].trim();
      let body = m[3].trim().replace(/^[。,，;；]\s*/, '').replace(/[。,,;；]\s*\d+[\.、)].*$/, '');
      let source: string | undefined;
      const srcMatch = body.match(sourceRe);
      if (srcMatch) {
        source = srcMatch[1].trim();
        body = body.replace(sourceRe, '').trim();
      }
      if (title && (title.length <= 30)) {
        segs.push({ title, body, source });
      }
    }
    if (segs.length >= 2) return segs;
  }

  // 3. Bullet points (· - * • 开头)
  const bulletRe = /^[\s]*[·\-\*•]\s+([^\n]+)/gm;
  const bulletMatches = Array.from(t.matchAll(bulletRe));
  if (bulletMatches.length >= 3) {
    const segs: Segment[] = [];
    for (const m of bulletMatches) {
      const line = m[1].trim();
      const colonIdx = line.search(/[:：]/);
      if (colonIdx > 0 && colonIdx < 30) {
        segs.push({ title: line.slice(0, colonIdx).trim(), body: line.slice(colonIdx + 1).trim() });
      } else {
        segs.push({ title: line.slice(0, 30), body: '' });
      }
    }
    return segs;
  }

  // 4. 段落级 "项目名: 描述" — 中文流水文里常见的格式
  // 例: "心盛计划是日慈核心项目, 服务 18-24 青年. 教师赋能项目..."
  // 用句号+疑似项目名启发, 但太脆弱, 留作未来 LLM 二次抽取
  return null;
}

function BusinessIntroSegmented({ text }: { text: string }) {
  const segs = parseBusinessIntro(text);
  if (!segs || segs.length === 0) {
    return <span className="whitespace-pre-wrap">{text}</span>;
  }
  return (
    <div className="space-y-3">
      {segs.map((s, idx) => (
        <div
          key={idx}
          className="rounded-lg bg-slate-50/70 border border-slate-100 px-3 py-2"
        >
          <div className="text-[13px] font-bold text-slate-800 mb-1">
            {s.title}
          </div>
          {s.body && (
            <div className="text-[12px] text-slate-600 leading-[1.7] whitespace-pre-wrap">
              {s.body}
            </div>
          )}
          {s.source && (
            <div className="mt-1.5 text-[10px] text-slate-400 italic">
              来自: {s.source}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function NarrativePanel({
  narrative,
  clarifications,
  onClarify,
  onRegenerate,
  regenerating,
  clientName,
  refreshTodoKey,
}: {
  narrative: ClientNarrative;
  clarifications: NarrativeClarification[];
  onClarify: (dim: NarrativeDimensionKey, answer: string, question?: string) => void;
  onRegenerate: () => void;
  regenerating: boolean;
  clientName: string;
  refreshTodoKey: number;
}) {
  const dimsByKey = new Map<NarrativeDimensionKey, NarrativeDimensionRecord>(
    narrative.dimensions.map((d) => [d.dimension, d]),
  );
  const pending = clarifications.filter((c) => c.status === 'pending');
  const applied = clarifications.filter((c) => c.status === 'applied');
  // 真生成: ai_doubao (云端) / backend_local_ai (本地, Plan A); 其它带 stub_ 前缀或空都视为降级
  const isStub = !narrative.generator
    || narrative.generator.startsWith('stub')
    || narrative.generator === 'stub_clarification_append';
  const generatorLabel = isStub
    ? `降级 (${narrative.generator})`
    : narrative.generator === 'backend_local_ai'
      ? '本地 AI 真生成 (消费 atomic_facts+entities)'
      : 'AI 真生成';
  const overallPct = Math.round(narrative.overallConfidence * 100);

  // (客户名 + AI 本次看到 由父组件 StrategicClarificationView 顶部渲染, 不在这里重复)

  return (
    <div>
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-5">
      <div className="space-y-4 min-w-0">
        {/* (状态条 + 加工层缺口 已按需求删除, 主体直接进入 6 段叙事) */}

        {/* 6 段叙事 */}
        {DIMENSION_ORDER.map((key) => {
          const dim = dimsByKey.get(key);
          if (!dim) return null;
          const dimClars = applied.filter((c) => c.dimension === key);
          return (
            <NarrativeDimensionCard
              key={key}
              dim={dim}
              appliedClarifications={dimClars}
              onClarify={(answer, question) => onClarify(key, answer, question)}
            />
          );
        })}
      </div>

      {/* 右侧 — 把握度卡片 + 澄清记录流 (共同编织追溯) */}
      <div className="space-y-3">
        {/* 顶部: 整体把握度 + 重新生成 */}
        <section className="rounded-2xl border border-slate-100 bg-slate-50/60 px-4 py-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-[10px] text-slate-500 mb-0.5">整体把握度</div>
              <div className="text-[22px] font-bold text-slate-800 leading-none">{overallPct}%</div>
            </div>
            <button
              type="button"
              onClick={onRegenerate}
              disabled={regenerating}
              className="inline-flex items-center gap-1.5 rounded-full bg-blue-600 text-white px-3 py-1.5 text-[11px] font-bold hover:bg-blue-700 disabled:opacity-50"
            >
              <RefreshCw size={12} className={regenerating ? 'animate-spin' : ''} />
              {regenerating ? '生成中...' : '重新生成'}
            </button>
          </div>
        </section>
        <UnifiedTodoSection key={refreshTodoKey} clientId={narrative.clientId} />
        <PendingClarificationsCard pending={pending} />
        <AppliedClarificationsCard applied={applied} />
      </div>
      </div>
    </div>
  );
}

function NarrativeDimensionCard({
  dim,
  appliedClarifications,
  onClarify,
}: {
  dim: NarrativeDimensionRecord;
  appliedClarifications: NarrativeClarification[];
  onClarify: (answer: string, question?: string) => void;
}) {
  const meta = DIMENSION_META[dim.dimension];
  const Icon = meta.icon;
  const confidenceMeta = CONFIDENCE_META[dim.confidence];
  const CIcon = confidenceMeta.icon;
  const [refsOpen, setRefsOpen] = useState(false);
  const [clarifyOpen, setClarifyOpen] = useState(false);
  const [clarifyText, setClarifyText] = useState('');
  const [clarifyQuestion, setClarifyQuestion] = useState('');

  const handleSubmit = () => {
    if (!clarifyText.trim()) return;
    onClarify(clarifyText, clarifyQuestion || undefined);
    setClarifyText('');
    setClarifyQuestion('');
    setClarifyOpen(false);
  };

  const handleUploadClick = () => {
    // TODO(post-M1): 接 backend POST /clients/{id}/documents/upload-binary?dimension=${dim.dimension}
    alert(
      `📤 上传 ${meta.label} 相关资料\n\n` +
      `请先把文件 (例: 合作合同/项目说明书/财报) 拖入"工作台 → 客户文件夹".\n` +
      `系统会自动 OCR + ingest + 抽取字典 candidate, 替代你逐条澄清.\n\n` +
      `下一版会直接在这里上传, 一键到这个客户的"${meta.label}"专属目录.`
    );
  };

  return (
    <article className="rounded-2xl border border-slate-100 bg-white px-5 py-4 shadow-[0_2px_8px_rgba(15,23,42,0.03)]">
      <div className="flex items-center justify-between mb-2 gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <Icon size={15} className="text-slate-500" />
          <h3 className="text-[14px] font-bold text-slate-900">{meta.label}</h3>
          <span className="text-[10px] text-slate-400 hidden md:inline">{meta.hint}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 ${confidenceMeta.bg} ${confidenceMeta.text}`}>
            <CIcon size={11} />
            <span className="text-[10px] font-bold">{confidenceMeta.label}</span>
          </div>
          <button
            type="button"
            onClick={handleUploadClick}
            className="inline-flex items-center justify-center w-6 h-6 rounded-full text-slate-400 hover:text-blue-600 hover:bg-blue-50 transition"
            title={`上传 ${meta.label} 相关资料 (例: 合同/项目说明书), 自动替代逐条澄清`}
          >
            <UploadCloud size={14} />
          </button>
        </div>
      </div>

      <div className="text-[13px] text-slate-700 leading-[1.8] mb-2">
        {dim.narrative
          ? (dim.dimension === 'business_intro'
              ? <BusinessIntroSegmented text={dim.narrative} />
              : <span className="whitespace-pre-wrap">{dim.narrative}</span>)
          : <span className="text-slate-400">⏳ AI 暂未生成此段</span>}
      </div>

      {/* "为什么把握度是 X" 已按需求隐藏 — confidenceReason 仅作后台调试用 */}

      {dim.dataLayerGap && (
        <div className="text-[11px] text-amber-700 bg-amber-50/60 rounded px-2 py-1 mb-2 inline-flex items-center gap-1">
          <Database size={11} />
          数据中心缺: {dim.dataLayerGap}
        </div>
      )}

      {dim.openClarifications.length > 0 && (
        <div className="mt-2 mb-2 space-y-1">
          {dim.openClarifications.map((q, i) => (
            <button
              key={i}
              type="button"
              onClick={() => {
                setClarifyQuestion(q);
                setClarifyOpen(true);
              }}
              className="block text-left w-full rounded-lg border border-blue-100 bg-blue-50/40 px-3 py-2 text-[12px] text-blue-700 hover:bg-blue-50"
            >
              <span className="inline-flex items-center gap-1.5">
                <MessageCircle size={11} />
                AI 想问: {q}
              </span>
            </button>
          ))}
        </div>
      )}

      {/* 引用源折叠 */}
      {dim.references.length > 0 && (
        <button
          type="button"
          onClick={() => setRefsOpen((v) => !v)}
          className="text-[11px] text-slate-500 hover:text-slate-700 inline-flex items-center gap-1"
        >
          <GitBranch size={11} />
          {dim.references.length} 条引用源
          <ChevronDown size={11} className={`transition-transform ${refsOpen ? 'rotate-180' : ''}`} />
        </button>
      )}
      {refsOpen && dim.references.length > 0 && (
        <ul className="mt-2 space-y-1 text-[11px] text-slate-600">
          {dim.references.map((r, i) => (
            <li key={i} className="flex items-start gap-1.5">
              <ExternalLink size={10} className="text-slate-400 mt-0.5" />
              <span>
                <span className="text-slate-800 font-mono">{r.sourceType}#{r.sourceId}</span>
                {r.label && <span className="text-slate-500"> · {r.label}</span>}
              </span>
            </li>
          ))}
        </ul>
      )}

      {/* 历史澄清贡献 */}
      {appliedClarifications.length > 0 && (
        <div className="mt-2 pt-2 border-t border-slate-100">
          <div className="text-[10px] text-slate-400 uppercase tracking-wide mb-1">共同编织</div>
          <ul className="space-y-1">
            {appliedClarifications.slice(0, 3).map((c) => (
              <li key={c.id} className="text-[11px] text-slate-600">
                <span className="font-semibold text-slate-700">{c.answeredByDisplayName}</span>
                <span className="text-slate-400"> {c.answeredAt.split('T')[0]}</span>
                <span className="text-slate-500"> · {c.answer.slice(0, 80)}{c.answer.length > 80 ? '...' : ''}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 澄清输入 */}
      <div className="mt-3 pt-3 border-t border-slate-100">
        {!clarifyOpen ? (
          <button
            type="button"
            onClick={() => setClarifyOpen(true)}
            className="inline-flex items-center gap-1.5 text-[11px] text-blue-700 hover:text-blue-900 font-semibold"
          >
            <Type size={11} />
            这里 AI 理解的对/不对, 我来补充
          </button>
        ) : (
          <div className="space-y-2">
            {clarifyQuestion && (
              <div className="text-[11px] text-slate-500 italic">
                回答: {clarifyQuestion}
              </div>
            )}
            <textarea
              value={clarifyText}
              onChange={(e) => setClarifyText(e.target.value)}
              rows={3}
              placeholder={`你想补充/纠正的内容 (会被 AI 在下次生成时吸纳进 ${meta.label})`}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-[12px] resize-none focus:outline-none focus:border-blue-400"
            />
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleSubmit}
                disabled={!clarifyText.trim()}
                className="rounded-full bg-blue-600 text-white px-3 py-1 text-[11px] font-bold hover:bg-blue-700 disabled:opacity-50"
              >
                提交澄清
              </button>
              <button
                type="button"
                onClick={() => {
                  setClarifyOpen(false);
                  setClarifyText('');
                  setClarifyQuestion('');
                }}
                className="text-[11px] text-slate-500 hover:text-slate-700"
              >
                取消
              </button>
            </div>
          </div>
        )}
      </div>
    </article>
  );
}

function PendingClarificationsCard({ pending }: { pending: NarrativeClarification[] }) {
  return (
    <section className="rounded-2xl border border-amber-100 bg-amber-50/40 px-4 py-3">
      <div className="flex items-center gap-2 mb-2">
        <MessageCircle size={13} className="text-amber-600" />
        <h3 className="text-[12px] font-bold text-amber-800">待应用澄清</h3>
        <span className="text-[10px] text-amber-700 bg-amber-100 rounded-full px-2 py-0.5 font-bold">
          {pending.length}
        </span>
      </div>
      {pending.length === 0 ? (
        <div className="text-[11px] text-slate-500">还没有等待应用的澄清。</div>
      ) : (
        <div className="space-y-2">
          {pending.map((c) => (
            <div key={c.id} className="rounded-lg bg-white border border-amber-100 px-3 py-2">
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="text-[10px] font-bold text-slate-700">
                  {DIMENSION_META[c.dimension]?.label || c.dimension}
                </span>
                <span className="text-[10px] text-slate-400">{c.answeredAt.split('T')[0]}</span>
              </div>
              <div className="text-[11px] text-slate-700 leading-[1.6]">{c.answer}</div>
              <div className="text-[10px] text-slate-400 mt-1">— {c.answeredByDisplayName}</div>
            </div>
          ))}
          <div className="text-[10px] text-amber-700 mt-1">
            点上方"重新生成"让 AI 吸纳这些澄清, 更新故事网。
          </div>
        </div>
      )}
    </section>
  );
}

function AppliedClarificationsCard({ applied }: { applied: NarrativeClarification[] }) {
  if (applied.length === 0) return null;
  return (
    <section className="rounded-2xl border border-slate-100 bg-white px-4 py-3">
      <div className="flex items-center gap-2 mb-2">
        <Users size={13} className="text-slate-500" />
        <h3 className="text-[12px] font-bold text-slate-700">共同编织 (已应用历史)</h3>
        <span className="text-[10px] text-slate-500">{applied.length} 条</span>
      </div>
      <ul className="space-y-1.5">
        {applied.slice(0, 8).map((c) => (
          <li key={c.id} className="text-[11px] text-slate-600 leading-[1.6]">
            <span className="font-semibold text-slate-700">{c.answeredByDisplayName}</span>
            <span className="text-slate-400"> · {c.answeredAt.split('T')[0]}</span>
            <span className="text-slate-500"> · {DIMENSION_META[c.dimension]?.label}</span>
            <div className="text-slate-500 ml-2">{c.answer.slice(0, 100)}{c.answer.length > 100 ? '...' : ''}</div>
          </li>
        ))}
      </ul>
    </section>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// AI 引用源·字典层 (旧 5 区块折叠, 给用户钻取真实 db row)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function ReferenceLayerSection({ ctx }: { ctx: ClarificationContext }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <section className="rounded-2xl border border-slate-100 bg-slate-50/40 px-4 py-3">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between text-left"
      >
        <div className="flex items-center gap-2">
          <Database size={13} className="text-slate-400" />
          <h4 className="text-[12px] font-bold text-slate-600">AI 引用源 · 字典层</h4>
          <span className="text-[10px] text-slate-400">
            上面叙事的原始素材 ({ctx.eventLines.length} 主线 · {ctx.timeline.length} 事件 · {ctx.commitments.length} 承诺 · {ctx.peopleCandidates.length} 人物候选)
          </span>
        </div>
        <ChevronDown size={14} className={`text-slate-400 transition-transform ${expanded ? 'rotate-180' : ''}`} />
      </button>
      {expanded && (
        <div className="mt-3 space-y-3">
          <ProjectSkeletonBlock eventLines={ctx.eventLines} profile={ctx.profile} />
          <KeyPeopleBlock people={ctx.peopleCandidates} />
          <CommitmentChainBlock commitments={ctx.commitments} />
          <TimelineBlock items={ctx.timeline} />
          <BusinessMeaningBlock profile={ctx.profile} eventLines={ctx.eventLines} />
        </div>
      )}
    </section>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 客户选择器
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function ClientPicker({
  clientOptions,
  selectedClientId,
  onClientChange,
}: {
  clientOptions: Array<{ id: string; name: string }>;
  selectedClientId: string;
  onClientChange: (id: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[11px] font-bold text-slate-400">客户</span>
      <select
        value={selectedClientId}
        onChange={(e) => onClientChange(e.target.value)}
        className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-[13px] font-medium text-slate-700 focus:outline-none focus:border-blue-300"
      >
        <option value="">选择...</option>
        {clientOptions.map((c) => (
          <option key={c.id} value={c.id}>{c.name}</option>
        ))}
      </select>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/60 px-4 py-12 text-center text-[13px] text-slate-400">
      {text}
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 通用区块外壳
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

interface BlockShellProps {
  icon: typeof Briefcase;
  title: string;
  confidence: Confidence;
  hint?: string;
  children: React.ReactNode;
}

function BlockShell({ icon: Icon, title, confidence, hint, children }: BlockShellProps) {
  const meta = CONFIDENCE_META[confidence];
  const MetaIcon = meta.icon;
  return (
    <section className="rounded-[20px] border border-slate-100 bg-white px-5 py-4">
      <header className="flex items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <Icon size={15} className="text-slate-500" />
          <h3 className="text-[14px] font-bold text-slate-800">{title}</h3>
        </div>
        <div className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold ${meta.bg} ${meta.text}`}>
          <MetaIcon size={10} />
          {meta.label}
        </div>
      </header>
      {hint && <p className="text-[11px] text-slate-400 mb-3 leading-[1.6]">{hint}</p>}
      <div>{children}</div>
    </section>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 区块 1 · 项目骨架
// 数据源: event_lines 表 (kind/stage/status/business_category/owner_name)
// 占位字段: 起止时间窗 / 交付物 / 验收标准 → 等 Phase 1 加 committed_at / expected_completion_at / deliverable_spec_json
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function ProjectSkeletonBlock({
  eventLines,
  profile,
}: {
  eventLines: ClarificationEventLine[];
  profile: ClarificationProfile;
}) {
  const active = eventLines.filter((el) => !el.closedAt);
  const closed = eventLines.filter((el) => !!el.closedAt);
  const confidence: Confidence = active.length > 0 ? 'medium' : eventLines.length > 0 ? 'low' : 'low';

  return (
    <BlockShell
      icon={Briefcase}
      title="项目骨架"
      confidence={confidence}
      hint={`从 event_lines 表读取 ${eventLines.length} 条业务主线。`}
    >
      {eventLines.length === 0 ? (
        <PlaceholderRow text="这个客户还没建任何业务主线" />
      ) : (
        <div className="space-y-2">
          {active.map((el) => <EventLineRow key={el.id} el={el} />)}
          {closed.length > 0 && (
            <details className="mt-2">
              <summary className="text-[11px] font-bold text-slate-400 cursor-pointer hover:text-slate-600">
                已关闭 / 历史 ({closed.length})
              </summary>
              <div className="mt-2 space-y-2">
                {closed.map((el) => <EventLineRow key={el.id} el={el} grayed />)}
              </div>
            </details>
          )}
        </div>
      )}

      {/* 占位字段 - 等 Phase 1 升级 */}
      <div className="mt-4 pt-3 border-t border-dashed border-slate-200">
        <div className="text-[10px] font-bold text-slate-400 mb-2 uppercase tracking-wider">等 Phase 1 升级补充</div>
        <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-400">
          <PlaceholderField label="起止时间窗" hint="字段 committed_at / expected_completion_at" />
          <PlaceholderField label="交付物 + 验收标准" hint="字段 deliverable_spec_json" />
          <PlaceholderField label="项目类型 (5 颗粒度)" hint="字段 thread_level" />
          <PlaceholderField label="父子嵌套关系" hint="字段 parent_thread_id" />
        </div>
      </div>
    </BlockShell>
  );
}

function EventLineRow({ el, grayed = false }: { el: ClarificationEventLine; grayed?: boolean }) {
  const statusMeta =
    el.closedAt ? { bg: 'bg-slate-100', text: 'text-slate-500', label: '已关闭' }
      : el.status === 'active' ? { bg: 'bg-emerald-50', text: 'text-emerald-700', label: '进行中' }
        : { bg: 'bg-amber-50', text: 'text-amber-700', label: el.status || '未知' };
  return (
    <div className={`rounded-xl border border-slate-100 px-3 py-2 ${grayed ? 'opacity-60' : ''}`}>
      <div className="flex items-start justify-between gap-2 mb-1">
        <div className="text-[13px] font-semibold text-slate-800 line-clamp-2 flex-1">
          {el.isDirtyName ? <span className="text-rose-500">(脏数据 - name=id)</span> : el.name}
        </div>
        <span className={`shrink-0 inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-bold ${statusMeta.bg} ${statusMeta.text}`}>
          {statusMeta.label}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px] font-bold text-slate-400">
        {el.stage && <span>{el.stage}</span>}
        {el.ownerName && <span>· {el.ownerName}</span>}
        {el.businessCategory && <span>· {el.businessCategory}</span>}
        {el.evidenceCount > 0 && <span>· {el.evidenceCount} 证据</span>}
      </div>
    </div>
  );
}

function PlaceholderRow({ text }: { text: string }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/40 px-3 py-3 text-[12px] text-slate-400 text-center">
      {text}
    </div>
  );
}

function PlaceholderField({ label, hint }: { label: string; hint: string }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50/30 px-2 py-1.5">
      <div className="font-semibold text-slate-500">{label}</div>
      <div className="text-[9px] text-slate-300 mt-0.5">{hint}</div>
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 区块 2 · 关键人物
// 数据源: event_lines.owner_name + activities.actor_name + tasks.owner_name + action_items.owner_name (粗糙归并)
// 占位: 别名归一 / 当前状态 / 在项目中的角色 / 健康信号 → 等 Phase 1 花名册 external_persons
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function KeyPeopleBlock({ people }: { people: ClarificationPerson[] }) {
  const confidence: Confidence = people.length > 0 ? 'low' : 'low';
  return (
    <BlockShell
      icon={Users}
      title={`关键人物 (${people.length} 人候选)`}
      confidence={confidence}
      hint="从 task/event_line/activity 的 owner_name + actor_name 提取的人名候选。等 Phase 1 花名册建好后, 自动归一别名 + 显示角色 + 状态。"
    >
      {people.length === 0 ? (
        <PlaceholderRow text="数据库里没有提取到任何人名 (检查 owner_name / actor_name 字段是否有值)" />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {people.map((p) => <PersonCard key={p.name} person={p} />)}
        </div>
      )}

      <div className="mt-4 pt-3 border-t border-dashed border-slate-200">
        <div className="text-[10px] font-bold text-slate-400 mb-2 uppercase tracking-wider">等 Phase 1 花名册升级</div>
        <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-400">
          <PlaceholderField label="别名归一" hint="例: 强哥=王强=王老师" />
          <PlaceholderField label="在职/离职/休假" hint="字段 employment_status + status_changed_at" />
          <PlaceholderField label="在这个项目里的角色" hint="字段 roles_json (含 since 时间戳)" />
          <PlaceholderField label="健康/工作风格信号" hint="字段 health_signal_json + work_style_traits_json" />
        </div>
      </div>
    </BlockShell>
  );
}

function PersonCard({ person }: { person: ClarificationPerson }) {
  return (
    <div className="rounded-xl border border-slate-100 px-3 py-2">
      <div className="flex items-baseline justify-between gap-2 mb-1">
        <div className="text-[13px] font-semibold text-slate-800">{person.name}</div>
        <span className="text-[10px] font-bold text-slate-400 tabular-nums">{person.mentionCount}×</span>
      </div>
      <div className="flex flex-wrap gap-1 text-[10px]">
        {person.sources.map((s) => (
          <span key={s} className="inline-block rounded bg-slate-100 px-1.5 py-0.5 text-slate-500 font-medium">
            {SOURCE_LABEL[s] || s}
          </span>
        ))}
      </div>
    </div>
  );
}

const SOURCE_LABEL: Record<string, string> = {
  event_line_owner: '主线负责人',
  activity_actor: '事件参与者',
  task_owner: '任务负责人',
  action_item_owner: '承诺负责人',
};

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 区块 3 · 承诺链
// 数据源: action_items + meetings (当前数据极少, 全库 4 条 action_items)
// 占位: 承诺人/被承诺人/承诺日 → 等 Phase 1 承诺级 thread 升级
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function CommitmentChainBlock({ commitments }: { commitments: ClarificationCommitment[] }) {
  const confidence: Confidence = commitments.length === 0 ? 'low' : 'low';
  return (
    <BlockShell
      icon={Target}
      title={`承诺链 (${commitments.length} 条)`}
      confidence={confidence}
      hint="从 action_items 提取。当前全库只有 4 条, 等 Phase 1 承诺级业务主线建好 + 录音转写 action_item 自动抽取流程跑起来。"
    >
      {commitments.length === 0 ? (
        <PlaceholderRow text="还没有从会议里抽出来的承诺 (action_items 数据为空)" />
      ) : (
        <div className="space-y-1.5">
          {commitments.map((c) => <CommitmentRow key={c.id} commitment={c} />)}
        </div>
      )}

      <div className="mt-4 pt-3 border-t border-dashed border-slate-200">
        <div className="text-[10px] font-bold text-slate-400 mb-2 uppercase tracking-wider">等 Phase 1 承诺级 thread 升级</div>
        <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-400">
          <PlaceholderField label="谁向谁承诺" hint="action_items 当前没有'被承诺人'字段" />
          <PlaceholderField label="承诺日期 ≠ 截止日期" hint="字段 committed_at" />
          <PlaceholderField label="是否有人承接" hint="承诺-承接对应链" />
          <PlaceholderField label="承诺履约状态" hint="advance/neutral/block 业务语义" />
        </div>
      </div>
    </BlockShell>
  );
}

function CommitmentRow({ commitment }: { commitment: ClarificationCommitment }) {
  return (
    <div className="rounded-xl border border-slate-100 px-3 py-2">
      <div className="text-[12px] font-semibold text-slate-800 mb-1 line-clamp-2">{commitment.title}</div>
      <div className="flex items-center gap-2 text-[10px] font-bold text-slate-400">
        {commitment.ownerName && <span>{commitment.ownerName}</span>}
        {commitment.dueDate && <span>· 截止 {commitment.dueDate}</span>}
        {commitment.meetingTitle && <span>· {commitment.meetingTitle}</span>}
      </div>
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 区块 4 · 来龙去脉 (时间线) — 当前可用度最高
// 数据源: event_line_activities (合并所有该客户主线的 activities)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function TimelineBlock({ items }: { items: ClarificationTimelineItem[] }) {
  const confidence: Confidence = items.length >= 5 ? 'medium' : items.length > 0 ? 'low' : 'low';
  return (
    <BlockShell
      icon={Clock}
      title={`来龙去脉 (${items.length} 条事件)`}
      confidence={confidence}
      hint="从 event_line_activities 表读取所有主线的事件 (已过滤测试附件)。等 Phase 2 加业务语义标签 (推进/中性/阻塞) + 影响传播。"
    >
      {items.length === 0 ? (
        <PlaceholderRow text="还没有事件记录" />
      ) : (
        <div className="relative pl-5 max-h-[400px] overflow-y-auto">
          <div className="absolute left-1.5 top-2 bottom-2 w-px bg-slate-200" />
          <div className="space-y-3">
            {items.map((item) => <TimelineItem key={item.id} item={item} />)}
          </div>
        </div>
      )}
    </BlockShell>
  );
}

function TimelineItem({ item }: { item: ClarificationTimelineItem }) {
  const dateLabel = (item.happenedAt || '').slice(0, 10);
  return (
    <div className="relative">
      <div className={`absolute -left-[18px] top-1 h-2.5 w-2.5 rounded-full ${item.isKey ? 'bg-blue-500' : 'bg-slate-300'} ring-2 ring-white`} />
      <div className="text-[10px] font-bold text-slate-400 mb-0.5">
        {dateLabel}
        {item.sourceType && <span className="ml-1.5 text-slate-300">· {item.sourceType}</span>}
        {item.actorName && <span className="ml-1.5">· {item.actorName}</span>}
      </div>
      <div className="text-[12px] text-slate-700 line-clamp-2">{item.title}</div>
      {item.eventLineName && (
        <div className="text-[10px] text-slate-400 mt-0.5">所属主线: {item.eventLineName}</div>
      )}
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 区块 5 · 业务意义
// 数据源: clients + client_strategic_profiles (后者大多空, 等 Phase 2 LLM 反推填充)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function BusinessMeaningBlock({
  profile,
  eventLines,
}: {
  profile: ClarificationProfile;
  eventLines: ClarificationEventLine[];
}) {
  const filledFields = [profile.industry, profile.scale, profile.currentNeeds, profile.strategicValueToYiyu]
    .filter((v) => v.trim().length > 0).length;
  const confidence: Confidence = filledFields >= 3 ? 'medium' : filledFields > 0 ? 'low' : 'low';
  return (
    <BlockShell
      icon={Sparkles}
      title="业务意义"
      confidence={confidence}
      hint={`从 clients + client_strategic_profiles 表读取。当前已填 ${filledFields}/7 字段, 等 Phase 2 加 LLM 从 memory_facts 反推填充。`}
    >
      <div className="space-y-2">
        <FieldRow label="行业 / 领域" value={profile.industry || profile.domain} />
        <FieldRow label="服务对象 / 当前需求" value={profile.currentNeeds} />
        <FieldRow label="痛点" value={profile.painPoints} />
        <FieldRow label="对益语的战略价值" value={profile.strategicValueToYiyu} />
        <FieldRow label="决策链" value={profile.decisionChain} />
        <FieldRow label="合作关系" value={profile.cooperationType ? `${profile.cooperationType} · 健康度: ${profile.relationshipHealth}` : ''} />
        <FieldRow label="阶段" value={profile.stage} />
      </div>

      <div className="mt-4 pt-3 border-t border-dashed border-slate-200">
        <div className="text-[10px] font-bold text-slate-400 mb-2 uppercase tracking-wider">等 Phase 1/2 字段升级</div>
        <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-400">
          <PlaceholderField label="治理结构" hint="governance_mode + governance_structure_json" />
          <PlaceholderField label="业务线占比" hint="business_lines_json (含占比 + 手法)" />
          <PlaceholderField label="资助方 / 合作方关系" hint="funder_relations_json" />
          <PlaceholderField label="核心人员健康信号" hint="key_personnel_health_signals_json" />
        </div>
      </div>
    </BlockShell>
  );
}

function FieldRow({ label, value }: { label: string; value: string }) {
  if (!value.trim()) {
    return (
      <div className="flex items-baseline gap-3 py-1 border-b border-dashed border-slate-100 last:border-0">
        <span className="text-[11px] font-bold text-slate-400 w-24 shrink-0">{label}</span>
        <span className="text-[11px] text-slate-300 italic">(空)</span>
      </div>
    );
  }
  return (
    <div className="flex items-baseline gap-3 py-1 border-b border-dashed border-slate-100 last:border-0">
      <span className="text-[11px] font-bold text-slate-400 w-24 shrink-0">{label}</span>
      <span className="text-[12px] text-slate-700 leading-[1.6] flex-1">{value}</span>
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 右侧 · 澄清队列
// 数据源: event_line_memory_snapshots.clarification_needs_json (当前是字段缺失提示, 不是业务问题)
// 占位: 真正的针对性业务问题需要 Phase 3 加'澄清问题生成引擎'
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function ClarificationQueue({
  needs,
  eventLines,
  clientName,
}: {
  needs: ClarificationNeed[];
  eventLines: ClarificationEventLine[];
  clientName: string;
}) {
  // 把 missingFields 翻译成业务问题
  const questions = needs.flatMap((need) => {
    return need.missingFields.map((field) => ({
      id: `${need.eventLineId}_${field}`,
      eventLineId: need.eventLineId,
      eventLineName: need.eventLineName,
      field,
      label: FIELD_QUESTION_LABEL[field] || `请补充: ${field}`,
      readiness: need.predictionReadiness,
    }));
  });

  return (
    <section className="rounded-[20px] border border-blue-100 bg-blue-50/30 px-5 py-4 sticky top-4">
      <header className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <MessageCircle size={15} className="text-blue-600" />
          <h3 className="text-[14px] font-bold text-slate-800">AI 想问你</h3>
        </div>
        <span className="text-[11px] font-bold text-blue-700">{questions.length} 个问题</span>
      </header>

      <p className="text-[11px] text-slate-500 leading-[1.6] mb-3">
        以下是 AI 目前还没明白的地方。回答后, 故事网会立刻更新。
        <span className="block mt-1 text-slate-400">当前展示的是字段缺失类基础问题 (来自 event_line_memory_snapshots)。Phase 3 会接 AI 主动生成的针对性业务问题。</span>
      </p>

      {questions.length === 0 ? (
        <div className="rounded-xl border border-dashed border-blue-200 bg-white/60 px-3 py-6 text-center text-[11px] text-slate-400">
          {clientName} 的关系网当前没有明显缺口
        </div>
      ) : (
        <div className="space-y-3">
          {questions.slice(0, 8).map((q) => <QuestionCard key={q.id} question={q} />)}
        </div>
      )}

      <div className="mt-4 pt-3 border-t border-dashed border-blue-200">
        <div className="text-[10px] font-bold text-slate-400 mb-2 uppercase tracking-wider">等 Phase 3 升级</div>
        <ul className="text-[10px] text-slate-400 space-y-1 leading-[1.6]">
          <li>· 引文支撑 (列引用的 evidence/document)</li>
          <li>· 一键打开原文件 (📂 按钮)</li>
          <li>· 语音回答 (🎤 按钮)</li>
          <li>· 答完自动 patch 进关系网 + 显示更新</li>
          <li>· 部门同事共同编织 (多答者追溯)</li>
        </ul>
      </div>
    </section>
  );
}

const FIELD_QUESTION_LABEL: Record<string, string> = {
  current_stage: '这条主线现在到了哪个阶段?',
  current_blocker: '现在卡在什么地方?',
  recent_decision: '最近做出过什么决策?',
  next_step: '下一步要做什么?',
  current_work: '现在具体在做什么?',
};

function QuestionCard({ question }: {
  question: {
    id: string;
    eventLineId: string;
    eventLineName: string;
    field: string;
    label: string;
    readiness: number;
  };
}) {
  return (
    <div className="rounded-xl border border-blue-200/60 bg-white px-3 py-2.5">
      <div className="text-[12px] font-semibold text-slate-800 mb-1.5 leading-[1.5]">
        {question.label}
      </div>
      {question.eventLineName && (
        <div className="text-[10px] text-slate-400 mb-2">
          关于: {question.eventLineName}
        </div>
      )}
      <div className="flex gap-1.5">
        <button
          type="button"
          disabled
          className="flex-1 inline-flex items-center justify-center gap-1 rounded-lg border border-slate-200 bg-slate-50 py-1 text-[10px] font-bold text-slate-400 cursor-not-allowed"
          title="等 Phase 3 上线"
        >
          <Mic size={10} />
          语音
        </button>
        <button
          type="button"
          disabled
          className="flex-1 inline-flex items-center justify-center gap-1 rounded-lg border border-slate-200 bg-slate-50 py-1 text-[10px] font-bold text-slate-400 cursor-not-allowed"
          title="等 Phase 3 上线"
        >
          <Type size={10} />
          打字
        </button>
      </div>
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 底部 · 数据卫生 (折叠) - 重复文件 + 误归类 + 测试数据
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function DataHygieneSection({
  clientId,
  flash,
}: {
  clientId: string;
  flash?: (level: 'success' | 'error' | 'info', message: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [groups, setGroups] = useState<DuplicateDocumentGroup[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!clientId) {
      setGroups([]);
      return;
    }
    let mounted = true;
    setLoading(true);
    getClientDuplicateDocuments(clientId)
      .then((data) => { if (mounted) setGroups(Array.isArray(data) ? data : []); })
      .catch(() => { if (mounted) setGroups([]); })
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, [clientId]);

  const hasDup = groups.length > 0;

  return (
    <section className="rounded-[18px] border border-slate-100 bg-slate-50/40 px-4 py-3">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between text-left"
      >
        <div className="flex items-center gap-2">
          <Building2 size={13} className="text-slate-400" />
          <h4 className="text-[12px] font-bold text-slate-600">数据卫生</h4>
          {hasDup && (
            <span className="text-[10px] font-bold text-amber-600 rounded-full bg-amber-50 px-2 py-0.5">
              {groups.length} 组重复文件
            </span>
          )}
        </div>
        <ChevronDown size={14} className={`text-slate-400 transition-transform ${expanded ? 'rotate-180' : ''}`} />
      </button>

      {expanded && (
        <div className="mt-3 space-y-2">
          {loading && <div className="text-[11px] text-slate-400">扫描中...</div>}
          {!loading && !hasDup && (
            <div className="text-[11px] text-emerald-600">✓ 没发现重复文件</div>
          )}
          {hasDup && (
            <div className="text-[11px] text-slate-600 leading-[1.7]">
              共 {groups.length} 组可清理。
              <span className="text-slate-400"> (Phase 1 升级后这里会加: 误归类剔除 + 测试数据标记 + 模拟角色清理)</span>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
