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

import React, { useCallback, useEffect, useState } from 'react';
import {
  Users, Target, Clock, AlertCircle, CheckCircle, HelpCircle,
  Mic, Type, ExternalLink, ChevronDown, FileSearch, Briefcase,
  Sparkles, MessageCircle, Building2, RefreshCw, Database, GitBranch,
  Compass, Network, History, Handshake, AlertTriangle, ArrowRight,
  UploadCloud, ClipboardCheck, X,
} from 'lucide-react';
import {
  getClientClarificationContext,
  getClientDuplicateDocuments,
  resolveDuplicateDocuments,
  getClientNarrative,
  listClientNarrativeClarifications,
  submitClientNarrativeClarification,
  regenerateClientNarrative,
  getNarrativeStaleStatus,
  clearNarrativeStale,
  getMeetingActionItems,
  getNextSteps,
  getNextStepBackground,
  dismissUnifiedTodo,
  logSuggestionAction,
  getSuggestionLog,
  removeSuggestionLogEntry,
  getStrategicDocs,
  uploadStrategicDoc,
  deleteStrategicDoc,
  type MeetingActionItem,
  type NextStepItem,
  type SuggestionLogEntry,
  type SuggestionAction,
  type StrategicDocsResponse,
  type StrategicDocType,
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
  /** UnifiedTodoSection 里点 → 时触发, 由 App 接住打开原任务编辑器并预填. */
  onPromoteTodo?: (todo: import('../../lib/api').UnifiedTodo) => void;
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
  onPromoteTodo,
}: StrategicClarificationViewProps) {
  const [narrative, setNarrative] = useState<ClientNarrative | null>(null);
  const [clarifications, setClarifications] = useState<NarrativeClarification[]>([]);
  const [ctx, setCtx] = useState<ClarificationContext | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [regenerating, setRegenerating] = useState(false);
  const [refreshTodoKey, setRefreshTodoKey] = useState(0);

  // S4.2 fix: 切客户竞态 — 之前 mounted flag 只在 .then() 里检查, 但 loadAll 内部的 setState
  // 已经发生(setNarrative/setClarifications/setCtx 都在 try 里直接调用), flag 形同虚设.
  // 改成: 把 mounted check 推到每个 setState 之前. 切客户 → cleanup mounted=false →
  // 旧请求即使返回, 也不会再 setState 覆盖新客户的数据.
  const loadAll = useCallback(async (clientId: string, isMounted: () => boolean) => {
    if (!isMounted()) return;
    setLoading(true);
    setError(null);
    try {
      const [n, c, x] = await Promise.all([
        getClientNarrative(clientId),
        listClientNarrativeClarifications(clientId),
        getClientClarificationContext(clientId).catch(() => null),
      ]);
      if (!isMounted()) return;  // 旧请求返回时新客户已切, 丢弃
      setNarrative(n);
      setClarifications(c.clarifications);
      setCtx(x);
    } catch (err) {
      if (!isMounted()) return;
      setError(err instanceof Error ? err.message : '加载失败');
      setNarrative(null);
      setClarifications([]);
      setCtx(null);
    } finally {
      if (isMounted()) setLoading(false);
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
    const isMounted = () => mounted;
    void loadAll(selectedClientId, isMounted);
    return () => { mounted = false; };
  }, [selectedClientId, loadAll]);

  // ingest 后 narrative 自动重生:
  //   1. load narrative 完成后, 调 stale-status
  //   2. 若 isStale (有新文档进, 但 narrative 是旧的) → 后台触发 regenerate, 不阻塞 UI
  //   3. regen 成功后清掉 stale 标记 + 替换前端 narrative
  // 不在 loadAll 里做, 因为 loadAll 由切客户/手动 reload 触发, 这里要等 narrative 加载好.
  useEffect(() => {
    if (!selectedClientId || !narrative || regenerating) return;
    let cancelled = false;
    (async () => {
      try {
        const stale = await getNarrativeStaleStatus(selectedClientId);
        if (cancelled || !stale.isStale) return;
        flash?.('info', `检测到新材料 (${stale.lastDocTitle || '新文档'}), 正在后台更新洞察…`);
        const fresh = await regenerateClientNarrative(selectedClientId, {
          trigger: 'auto_after_ingest',
          force: true,
        });
        if (cancelled) return;
        setNarrative(fresh);
        try {
          const c = await listClientNarrativeClarifications(selectedClientId);
          if (!cancelled) setClarifications(c.clarifications);
        } catch { /* 澄清拉失败不影响 narrative 更新 */ }
        await clearNarrativeStale(selectedClientId).catch(() => {});
        if (!cancelled) flash?.('success', `已自动结合新材料生成 v${fresh.rev}`);
      } catch (err) {
        // 静默失败 — 自动逻辑不应打扰用户; 手动"重新生成"按钮仍然可用
        // eslint-disable-next-line no-console
        console.warn('[narrative auto-regen] skip', err);
      }
    })();
    return () => { cancelled = true; };
  }, [selectedClientId, narrative?.id, regenerating, flash]);

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
          onPromoteTodo={onPromoteTodo}
          flash={flash}
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
  // v1.0 6 层 (云端 narrative 真维度)
  // strategic_dna 不在这里 — 它是独立 UI (StrategicDnaCard), 数据从 /strategic-docs endpoint 拿
  essence:        { label: '组织介绍',           icon: Compass,       hint: '客户机构是谁 / 赛道 / 行业定位 / 影响力' },
  business_intro: { label: '业务介绍',           icon: Briefcase,     hint: '客户机构内含项目逐个详介' },
  cooperation:    { label: '合作关系',           icon: Handshake,     hint: '益语跟客户的服务关系 / 合作周期 / 核心交付' },
  people:         { label: '关键人物',           icon: Network,       hint: '益语方 + 客户方 + 每个项目对应角色' },
  timeline:       { label: '时间线',             icon: History,       hint: '合作里程碑 (起点→转折→现状)' },
  next_steps:     { label: '本阶段战略思路',     icon: ArrowRight,    hint: '战略层 / 关系层 / 风险对冲 — 给方向, 不列条目(看右侧"下一步要做什么")' },
  // 兼容旧 rev (废弃但仍可能从云端拿到)
  history:        { label: '来龙去脉 (旧)',     icon: History,       hint: '已废弃, 见时间线' },
  commitments:    { label: '承诺网 (旧)',       icon: Handshake,     hint: '已废弃, 见承诺与下一步' },
  risks:          { label: '卡点与风险 (旧)',   icon: AlertTriangle, hint: '已废弃, 隐含在下一步里' },
  next:           { label: '下一步 (旧)',       icon: ArrowRight,    hint: '已废弃, 见承诺与下一步' },
};

const DIMENSION_ORDER: NarrativeDimensionKey[] = [
  // 6 层 narrative 维度 (云端 storage 真维度)
  // 注: StrategicDnaCard (战略定位与发展路径, 用户上传的 .md) 是独立组件, 在循环外渲染,
  // 视觉上插在 essence 之后 / business_intro 之前
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

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 战略定位与发展路径 (用户上传的 .md, 不让 LLM 编造)
// 视觉上插在 essence 卡之后, 跟其他维度卡同构, 但数据源是独立 endpoint
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function StrategicDnaCard({
  clientId,
  flash,
}: {
  clientId: string;
  flash?: (level: 'success' | 'error' | 'info', message: string) => void;
}) {
  const [data, setData] = useState<StrategicDocsResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const reload = useCallback(() => {
    if (!clientId) return;
    setLoading(true);
    getStrategicDocs(clientId)
      .then((d) => setData(d))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [clientId]);

  useEffect(() => {
    reload();
  }, [reload]);

  const handleFilePick = (docType: StrategicDocType) => async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';  // 允许重选同一文件
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.md') && !file.name.toLowerCase().endsWith('.markdown')) {
      flash?.('error', '只接受 .md / .markdown 格式');
      return;
    }
    if (file.size > 200 * 1024) {
      flash?.('error', '文档过大 (>200KB), 请精简后再上传');
      return;
    }
    try {
      const mdContent = await file.text();
      await uploadStrategicDoc(clientId, { docType, fileName: file.name, mdContent });
      flash?.('success', `已上传 ${docType === 'strategy' ? '战略文档' : '方法论文档'}`);
      reload();
    } catch (err) {
      flash?.('error', err instanceof Error ? err.message : '上传失败');
    }
  };

  const handleDelete = async (docType: StrategicDocType) => {
    if (!window.confirm(`确认删除${docType === 'strategy' ? '战略文档' : '方法论文档'}? 删除后, 品牌监控/提案等模块将看不到此客户的战略基线.`)) return;
    try {
      await deleteStrategicDoc(clientId, docType);
      flash?.('info', '已删除');
      reload();
    } catch (err) {
      flash?.('error', err instanceof Error ? err.message : '删除失败');
    }
  };

  if (loading && !data) {
    return (
      <div className="rounded-2xl border border-slate-100 bg-white p-5">
        <div className="text-[11px] text-slate-400">加载战略文档...</div>
      </div>
    );
  }

  const hasAny = data?.hasStrategy || data?.hasMethodology;
  const hasAll = data?.hasStrategy && data?.hasMethodology;

  return (
    <div className="rounded-2xl border border-violet-100 bg-gradient-to-br from-violet-50/40 to-white p-5">
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <Target size={16} className="text-violet-600" />
          <h3 className="text-[15px] font-bold text-violet-900">战略定位与发展路径</h3>
        </div>
        <span className="text-[10px] text-violet-700 bg-violet-100 rounded-full px-2 py-0.5 font-bold">
          {hasAll ? '已配置' : hasAny ? '部分配置' : '未配置'}
        </span>
      </div>

      {!hasAny && (
        <div className="space-y-3">
          <div className="text-[12px] leading-relaxed text-slate-700 bg-violet-50/60 rounded-xl px-4 py-3 border border-violet-100">
            <p className="font-semibold text-violet-900 mb-1">AI 说:</p>
            <p>
              我在客户资料里没找到足够多的战略方向内容和明确的业务方法论文档. 这两份是品牌监控、情报匹配、提案生成等模块判断客户事情的关键基线. 建议把客户内部讨论过的战略文档和方法论保存为 <code className="bg-white px-1.5 py-0.5 rounded text-[11px]">.md</code> 上传 — 上传后这些模块的准确度会显著提升, 也避免 AI 编造战略误导决策.
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
        <StrategicDocSlot
          docType="strategy"
          title="战略文档"
          hint="客户在赛道里走什么路线"
          entry={data?.strategy ?? null}
          onPick={handleFilePick('strategy')}
          onDelete={() => handleDelete('strategy')}
        />
        <StrategicDocSlot
          docType="methodology"
          title="方法论文档"
          hint="客户的发展路径和工作方法"
          entry={data?.methodology ?? null}
          onPick={handleFilePick('methodology')}
          onDelete={() => handleDelete('methodology')}
        />
      </div>
    </div>
  );
}

function StrategicDocSlot({
  docType,
  title,
  hint,
  entry,
  onPick,
  onDelete,
}: {
  docType: StrategicDocType;
  title: string;
  hint: string;
  entry: { fileName: string; mdContent: string; uploadedAt: string; uploadedBy: string } | null;
  onPick: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onDelete: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const inputId = `strategic-upload-${docType}`;

  if (!entry) {
    return (
      <label htmlFor={inputId} className="block cursor-pointer rounded-xl border-2 border-dashed border-violet-200 hover:border-violet-400 bg-white px-4 py-4 text-center transition-colors">
        <UploadCloud size={18} className="mx-auto text-violet-500 mb-2" />
        <div className="text-[12px] font-bold text-slate-800">{title}</div>
        <div className="text-[10px] text-slate-500 mt-0.5">{hint}</div>
        <div className="text-[10px] text-violet-600 font-bold mt-2">点击上传 .md 文件</div>
        <input id={inputId} type="file" accept=".md,.markdown,text/markdown" className="hidden" onChange={onPick} />
      </label>
    );
  }
  const previewLines = entry.mdContent.split('\n').slice(0, 5).join('\n');
  const hasMore = entry.mdContent.split('\n').length > 5;
  return (
    <div className="rounded-xl border border-violet-200 bg-white px-4 py-3">
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="min-w-0 flex-1">
          <div className="text-[12px] font-bold text-slate-800">{title}</div>
          <div className="text-[10px] text-slate-500 truncate mt-0.5">📄 {entry.fileName}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            上传于 {entry.uploadedAt.slice(0, 16).replace('T', ' ')}
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <label htmlFor={`${inputId}-replace`} className="cursor-pointer text-[10px] text-violet-600 hover:text-violet-800 font-bold">
            重传
            <input id={`${inputId}-replace`} type="file" accept=".md,.markdown,text/markdown" className="hidden" onChange={onPick} />
          </label>
          <button
            type="button"
            onClick={onDelete}
            className="text-[10px] text-rose-500 hover:text-rose-700 font-bold"
          >
            删除
          </button>
        </div>
      </div>
      <div className="mt-2 text-[11px] text-slate-700 leading-relaxed bg-slate-50 rounded-lg px-3 py-2 max-h-[180px] overflow-y-auto whitespace-pre-wrap font-mono">
        {expanded ? entry.mdContent : previewLines}
        {!expanded && hasMore && '...'}
      </div>
      {hasMore && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="mt-1.5 text-[10px] text-violet-600 hover:text-violet-800 font-bold"
        >
          {expanded ? '▲ 收起' : '▼ 展开全文'}
        </button>
      )}
    </div>
  );
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
  onPromoteTodo,
  flash,
}: {
  narrative: ClientNarrative;
  clarifications: NarrativeClarification[];
  onClarify: (dim: NarrativeDimensionKey, answer: string, question?: string) => void;
  onRegenerate: () => void;
  regenerating: boolean;
  clientName: string;
  refreshTodoKey: number;
  onPromoteTodo?: (todo: import('../../lib/api').UnifiedTodo) => void;
  flash?: (level: 'success' | 'error' | 'info', message: string) => void;
}) {
  const dimsByKey = new Map<NarrativeDimensionKey, NarrativeDimensionRecord>(
    narrative.dimensions.map((d) => [d.dimension, d]),
  );
  const pending = clarifications.filter((c) => c.status === 'pending');
  const applied = clarifications.filter((c) => c.status === 'applied');
  // 本地刷新 key — 用户在主区块点 → / ✓ / ✗ 或在日志卡点"找回" 后, 主区块跟日志卡都重拉
  const [localRefreshKey, setLocalRefreshKey] = useState(0);
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

        {/* 6 段叙事 + StrategicDnaCard 插在 essence 之后 / business_intro 之前
            (战略定位与发展路径 — 用户上传的 .md, 独立数据源, 不让 LLM 编造) */}
        {DIMENSION_ORDER.map((key) => {
          const dim = dimsByKey.get(key);
          if (!dim) return null;
          const dimClars = applied.filter((c) => c.dimension === key);
          const card = (
            <NarrativeDimensionCard
              key={key}
              dim={dim}
              appliedClarifications={dimClars}
              onClarify={(answer, question) => onClarify(key, answer, question)}
            />
          );
          // essence 渲染完后, 紧跟着插入战略定位与发展路径卡
          if (key === 'essence') {
            return (
              <React.Fragment key="essence-with-dna">
                {card}
                <StrategicDnaCard clientId={narrative.clientId} flash={flash} />
              </React.Fragment>
            );
          }
          return card;
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
        <MeetingActionItemsCard
          clientId={narrative.clientId}
          onPromote={onPromoteTodo}
          refreshKey={refreshTodoKey}
          onLogChange={() => setLocalRefreshKey((k) => k + 1)}
        />
        <SuggestionLogCard
          clientId={narrative.clientId}
          refreshKey={localRefreshKey}
          onChange={() => setLocalRefreshKey((k) => k + 1)}
        />
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
              : <span className="whitespace-pre-wrap">{
                  // 兜底: 部分 narrative LLM 偶尔输出 <br>/<br/>, 转成真换行
                  dim.narrative.replace(/<br\s*\/?>/gi, '\n')
                }</span>)
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

      {/* 历史澄清贡献已迁移到右侧"共同编织"统一日志面板 (AppliedClarificationsCard),
          避免每个维度卡片都重复一份, 修改多了左侧就臃肿. */}

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

const KIND_META: Record<NextStepItem['kind'], { label: string; bg: string; text: string }> = {
  meeting:         { label: '会议',   bg: 'bg-violet-100',  text: 'text-violet-700' },
  commitment:      { label: '承诺',   bg: 'bg-blue-100',    text: 'text-blue-700' },
  task:            { label: '任务',   bg: 'bg-amber-100',   text: 'text-amber-700' },
  meeting_action:  { label: '会议待办', bg: 'bg-emerald-100', text: 'text-emerald-700' },
};

function MeetingActionItemsCard({
  clientId,
  onPromote,
  refreshKey,
  onLogChange,
}: {
  clientId: string;
  onPromote?: (todo: import('../../lib/api').UnifiedTodo) => void;
  refreshKey?: number;
  onLogChange?: () => void;
}) {
  const [items, setItems] = useState<NextStepItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let alive = true;
    if (!clientId) return;
    setLoading(true);
    getNextSteps(clientId)
      .then((d) => { if (alive) setItems(d.items || []); })
      .catch(() => { if (alive) setItems([]); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [clientId, refreshKey]);

  const writeLog = async (it: NextStepItem, action: SuggestionAction) => {
    try {
      await logSuggestionAction(clientId, {
        fingerprint: it.fingerprint,
        action,
        actor: it.actor,
        suggestionText: it.text,
        sourceDocTitle: '',
        sourceDocId: '',
      });
      // 老 dismiss endpoint 兼容: commitment/task/action 类同时落 status=cancelled/done
      // (这样 commitments 表里的旧建议不会通过 unified-todos 老路径再次回潮)
      if (it.rawId && (it.kind === 'commitment' || it.kind === 'task' || it.kind === 'meeting_action')) {
        try {
          const legacyAction = action === 'completed' ? 'complete' : 'cancel';
          await dismissUnifiedTodo(clientId, it.rawId, legacyAction);
        } catch { /* legacy endpoint 失败不阻塞 */ }
      }
    } catch { /* suggestion_log 写失败也不阻塞 UI */ }
    setItems((prev) => prev.filter((x) => x.fingerprint !== it.fingerprint));
    onLogChange?.();
  };

  const handlePromote = async (it: NextStepItem) => {
    if (!onPromote) return;
    const firstActor = (it.actor || '').split(',')[0]?.trim() || '';
    // 拿 LLM 背景说明 (列表加载时已后台预生成, 一般是 cache 命中, 体感瞬时)
    // cache miss 时也最多 2-3s, 不阻塞 fallback (拿不到就空背景)
    let description = '';
    let sourceLabel = '';
    try {
      const bg = await getNextStepBackground(clientId, {
        fingerprint: it.fingerprint,
        kind: it.kind,
        actor: it.actor,
        text: it.text,
      });
      description = bg.background || '';
      sourceLabel = bg.sourceLabel || '';
    } catch { /* 失败也继续, 描述为空 */ }
    if (description && sourceLabel) {
      description = `${description}\n\n— 来源: 《${sourceLabel}》`;
    }
    const fakeTodo: import('../../lib/api').UnifiedTodo = {
      id: it.rawId || `meeting:${it.fingerprint}`,
      source: it.kind === 'meeting' ? 'meeting_action' : (it.kind as 'task' | 'commitment' | 'meeting_action'),
      title: it.text,
      owner: firstActor,
      due_date: it.dueDate || '',
      status: 'pending',
      direction: '下一步',
      related_to: '',
      raw_id: it.rawId,
      severity: it.severity,
      description,
    };
    onPromote(fakeTodo);
    await writeLog(it, 'promoted');
  };

  if (loading) {
    return (
      <section className="rounded-2xl border border-slate-100 bg-slate-50/40 px-4 py-3">
        <div className="text-[11px] text-slate-400">加载下一步...</div>
      </section>
    );
  }
  if (items.length === 0) {
    return (
      <section className="rounded-2xl border border-violet-100 bg-violet-50/40 px-4 py-3">
        <div className="flex items-center gap-2 mb-1">
          <ClipboardCheck size={13} className="text-violet-600" />
          <h3 className="text-[12px] font-bold text-violet-800">下一步要做什么</h3>
        </div>
        <div className="text-[11px] text-slate-500">
          暂无新的建议 — 上传新会议纪要或点下方"推荐历史"找回。
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-violet-100 bg-violet-50/40 px-4 py-3">
      <div className="flex items-center gap-2 mb-2">
        <ClipboardCheck size={13} className="text-violet-600" />
        <h3 className="text-[12px] font-bold text-violet-800">下一步要做什么</h3>
        <span className="text-[10px] text-violet-700 bg-violet-100 rounded-full px-2 py-0.5 font-bold">
          {items.length}
        </span>
      </div>
      <div className="space-y-1.5 max-h-[460px] overflow-y-auto pr-0.5">
        {items.map((it) => (
          <ActionRow
            key={it.fingerprint}
            item={it}
            onPromote={onPromote ? () => handlePromote(it) : undefined}
            onComplete={() => writeLog(it, 'completed')}
            onDismiss={() => writeLog(it, 'dismissed')}
          />
        ))}
      </div>
    </section>
  );
}

function ActionRow({
  item,
  onPromote,
  onComplete,
  onDismiss,
}: {
  item: NextStepItem;
  onPromote?: () => void;
  onComplete?: () => void;
  onDismiss?: () => void;
}) {
  const meta = KIND_META[item.kind] ?? KIND_META.meeting;
  return (
    <div className="rounded-xl border border-slate-100 bg-white px-3 py-2.5 hover:border-violet-200 transition-colors">
      {/* 第一行: 左 kind chip + 右 三按钮 */}
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <span className={`text-[10px] font-bold ${meta.text} ${meta.bg} rounded px-1.5 py-0.5`}>
          {meta.label}
        </span>
        <div className="flex items-center gap-1">
          {onPromote && (
            <button
              type="button"
              onClick={onPromote}
              title="制定任务"
              className="inline-flex items-center justify-center w-6 h-6 rounded-full text-violet-600 hover:bg-violet-100 hover:text-violet-800"
            >
              <ArrowRight size={13} />
            </button>
          )}
          {onComplete && (
            <button
              type="button"
              onClick={onComplete}
              title="已完成"
              className="inline-flex items-center justify-center w-6 h-6 rounded-full text-emerald-600 hover:bg-emerald-100"
            >
              <CheckCircle size={12} />
            </button>
          )}
          {onDismiss && (
            <button
              type="button"
              onClick={onDismiss}
              title="删除"
              className="inline-flex items-center justify-center w-6 h-6 rounded-full text-slate-400 hover:bg-rose-100 hover:text-rose-600"
            >
              <X size={13} />
            </button>
          )}
        </div>
      </div>

      {/* 第二行: 内容 */}
      <p className="text-[13px] text-slate-800 leading-snug mb-2">{item.text}</p>

      {/* 第三行: @人 · 截止日期 (强调) */}
      <div className="flex items-center gap-2 text-[11px]">
        <span className="font-bold text-slate-700">
          @{item.actor || '未指定'}
        </span>
        {item.dueDate && (
          <>
            <span className="text-slate-300">·</span>
            <span className="font-bold text-rose-600">
              截止 {item.dueDate}
            </span>
          </>
        )}
      </div>
    </div>
  );
}

function SuggestionLogCard({
  clientId,
  refreshKey,
  onChange,
}: {
  clientId: string;
  refreshKey: number;
  onChange: () => void;
}) {
  const [log, setLog] = useState<{ promoted: SuggestionLogEntry[]; completed: SuggestionLogEntry[]; dismissed: SuggestionLogEntry[] }>(
    { promoted: [], completed: [], dismissed: [] },
  );
  const [tab, setTab] = useState<SuggestionAction>('dismissed');
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!clientId) return;
    let alive = true;
    getSuggestionLog(clientId).then((d) => {
      if (!alive) return;
      setLog({ promoted: d.promoted || [], completed: d.completed || [], dismissed: d.dismissed || [] });
    }).catch(() => {});
    return () => { alive = false; };
  }, [clientId, refreshKey]);

  const total = log.promoted.length + log.completed.length + log.dismissed.length;
  if (total === 0) return null;

  const restore = async (entry: SuggestionLogEntry) => {
    try {
      await removeSuggestionLogEntry(clientId, entry.fingerprint);
      setLog((prev) => ({
        promoted: prev.promoted.filter((e) => e.fingerprint !== entry.fingerprint),
        completed: prev.completed.filter((e) => e.fingerprint !== entry.fingerprint),
        dismissed: prev.dismissed.filter((e) => e.fingerprint !== entry.fingerprint),
      }));
      onChange();
    } catch {}
  };

  const current = log[tab];

  return (
    <section className="rounded-2xl border border-slate-200 bg-white">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full px-4 py-2.5 flex items-center gap-2 text-left hover:bg-slate-50 rounded-2xl"
      >
        <History size={13} className="text-slate-500" />
        <h3 className="text-[12px] font-bold text-slate-700">推荐历史</h3>
        <span className="text-[10px] text-slate-500 ml-1">
          已分配 {log.promoted.length} · 已完成 {log.completed.length} · 已删除 {log.dismissed.length}
        </span>
        <ChevronDown size={13} className={`ml-auto text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="px-4 pb-3 border-t border-slate-100">
          <div className="flex items-center gap-1 my-2">
            {(['dismissed', 'promoted', 'completed'] as const).map((k) => {
              const label = k === 'dismissed' ? '已删除' : k === 'promoted' ? '已分配' : '已完成';
              const isActive = tab === k;
              return (
                <button
                  key={k}
                  type="button"
                  onClick={() => setTab(k)}
                  className={`text-[11px] px-2.5 py-1 rounded-full font-bold ${
                    isActive ? 'bg-slate-800 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {label} {log[k].length}
                </button>
              );
            })}
          </div>
          {current.length === 0 ? (
            <div className="text-[11px] text-slate-400 py-2">这一类还没有记录</div>
          ) : (
            <div className="space-y-1 max-h-[260px] overflow-y-auto">
              {current.map((e) => (
                <div key={e.fingerprint} className="rounded-lg border border-slate-100 px-2.5 py-1.5 group">
                  <div className="flex items-start gap-1.5">
                    <span className="text-[9px] font-bold text-slate-600 bg-slate-100 rounded px-1 py-0.5 shrink-0">
                      @{e.actor || '?'}
                    </span>
                    <p className="text-[11px] text-slate-700 leading-snug flex-1 min-w-0">{e.suggestionText}</p>
                    <button
                      type="button"
                      onClick={() => restore(e)}
                      title="找回 — 让这条重新出现在'下一步要做什么'"
                      className="shrink-0 text-[10px] text-blue-600 hover:text-blue-800 opacity-0 group-hover:opacity-100"
                    >
                      找回
                    </button>
                  </div>
                  <div className="text-[9px] text-slate-400 mt-0.5 truncate">
                    {e.sourceDocTitle} · {(e.createdAt || '').slice(0, 16)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
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
  // 5 行高度的可滚动日志, 看谁填了什么, 像活动 log 一样. 全部内容可滚出来,
  // 不再硬截断到前 8 条 (避免遮蔽久远贡献).
  return (
    <section className="rounded-2xl border border-slate-100 bg-white px-4 py-3">
      <div className="flex items-center gap-2 mb-2">
        <Users size={13} className="text-slate-500" />
        <h3 className="text-[12px] font-bold text-slate-700">共同编织</h3>
        <span className="text-[10px] text-slate-500 ml-auto">{applied.length} 条</span>
      </div>
      {applied.length === 0 ? (
        <div className="text-[11px] text-slate-400 py-2">还没有人补充澄清</div>
      ) : (
        <ul className="space-y-1.5 max-h-[200px] overflow-y-auto pr-1">
          {applied.map((c) => (
            <li key={c.id} className="text-[11px] text-slate-600 leading-[1.55] border-b border-slate-50 last:border-b-0 pb-1.5 last:pb-0">
              <div className="flex items-center gap-1.5">
                <span className="font-semibold text-slate-700">{c.answeredByDisplayName}</span>
                <span className="text-slate-400">·</span>
                <span className="text-slate-400 text-[10px]">{c.answeredAt.split('T')[0]}</span>
                <span className="text-slate-400">·</span>
                <span className="text-slate-500 text-[10px]">{DIMENSION_META[c.dimension]?.label}</span>
              </div>
              <div className="text-slate-500 mt-0.5">{c.answer.slice(0, 120)}{c.answer.length > 120 ? '...' : ''}</div>
            </li>
          ))}
        </ul>
      )}
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
      hint="承诺表 (LLM 从对话/资料抽取) + 会议待办 action_items 合并。pending=未履约 / fulfilled=已交付 / cancelled=作废。"
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
