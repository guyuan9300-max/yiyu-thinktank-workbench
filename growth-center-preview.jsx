import { useState, useCallback } from "react";

/* ── Design tokens ────────────────────────────────────────────────── */
const brand = "#5B7BFE";

/* ── Mock data ────────────────────────────────────────────────────── */
const INSIGHTS = [
  { id: "1", quote: "让客户先交完整方案再提问题，比直接帮改方案更有效——陪伴的核心是不代偿。", author: "顾源源", ai: false, src: "日慈战略陪伴", week: "W14", likes: 3, liked: false },
  { id: "2", quote: "数字化理解快的客户，效率瓶颈往往不在技术而在项目设计。", author: "大周", ai: true, src: "数字化复盘", week: "W14", likes: 5, liked: true },
  { id: "3", quote: "月捐人流失率最高的阶段不是首月，而是第三个月——这是承诺感消退的临界点。", author: "庆华", ai: true, src: "月捐分析", week: "W13", likes: 7, liked: false },
  { id: "4", quote: "组织内部培训如果只讲方法不讲为什么，三个月后执行率会掉到 20% 以下。", author: "顾源源", ai: false, src: "内部管理", week: "W13", likes: 2, liked: false },
  { id: "5", quote: "合作方的节奏感比能力更重要，节奏对不上的合作最终都会变成消耗。", author: "佳乐", ai: false, src: "合作方管理", week: "W12", likes: 4, liked: false },
  { id: "6", quote: "公益项目设计中最常见的错误是把活动当成了成果，活动是手段不是目的。", author: "大周", ai: true, src: "项目设计复盘", week: "W12", likes: 6, liked: true },
];

const PENDING = [
  { id: "p1", quote: "客户的抗拒往往不是对方案的否定，而是对变化的恐惧——先处理情绪再处理问题。", src: "日慈复盘 · W14" },
  { id: "p2", quote: "周报的价值不在记录做了什么，而在沉淀出哪些判断值得复用。", src: "内部管理 · W14" },
];

const TEMPLATES = [
  { id: "t1", name: "战略陪伴全流程", steps: ["客户背景调研", "首次诊断会议", "诊断报告输出", "季度复盘", "战略方案迭代", "结项评估"], calls: 4, xp: 48 },
  { id: "t2", name: "月捐人深度运营", steps: ["捐赠人画像分析", "沟通策略制定", "个性化内容生成", "反馈追踪"], calls: 2, xp: 24 },
  { id: "t3", name: "项目结项评估", steps: ["数据收集", "指标计算", "报告生成", "复盘会议"], calls: 6, xp: 36 },
];

const BADGES = [
  { id: "b1", name: "战略陪伴达人", emoji: "\u{1F525}", type: "upgrade", status: "unlocked", stars: 3, max: 5, desc: "完成 3 个客户的战略陪伴全流程交付。", next: "完成 5 个客户", at: "2026-03-22", xp: 50 },
  { id: "b2", name: "经验传承者", emoji: "\u{1F4A1}", type: "upgrade", status: "progress", stars: 1, max: 3, pct: 60, desc: "推送经验墙金句被 3 人收藏。", next: "被 10 人收藏" },
  { id: "b3", name: "模板建筑师", emoji: "\u{1F3D7}\uFE0F", type: "upgrade", status: "unlocked", stars: 2, max: 5, desc: "创建的模板被其他人调用 10 次。", next: "被调用 25 次", at: "2026-03-15", xp: 40 },
  { id: "b4", name: "首次客户诊断", emoji: "\u{1F3AF}", type: "achievement", status: "unlocked", desc: "完成第一次客户诊断报告。", at: "2026-02-10", xp: 20 },
  { id: "b5", name: "首个模板被复用", emoji: "\u267B\uFE0F", type: "achievement", status: "unlocked", desc: "你创建的工作模板第一次被其他同事使用。", at: "2026-03-01", xp: 30 },
  { id: "b6", name: "复盘先锋", emoji: "\u{1F4DD}", type: "achievement", status: "progress", pct: 75, desc: "连续 4 周完成周复盘。" },
  { id: "b7", name: "数据猎手", emoji: "\u{1F4CA}", type: "upgrade", status: "locked" },
  { id: "b8", name: "全能选手", emoji: "\u{1F31F}", type: "achievement", status: "locked" },
  { id: "b9", name: "知识矿工", emoji: "\u26CF\uFE0F", type: "upgrade", status: "locked" },
  { id: "b10", name: "团队催化剂", emoji: "\u26A1", type: "achievement", status: "locked" },
];

const RANKS = [
  { rank: 1, name: "大周", ai: true, xp: 2847 },
  { rank: 2, name: "顾源源", ai: false, xp: 1523 },
  { rank: 3, name: "庆华", ai: true, xp: 1201 },
  { rank: 4, name: "花花", ai: true, xp: 876 },
  { rank: 5, name: "罗茜茜", ai: true, xp: 654 },
  { rank: 6, name: "佳乐", ai: false, xp: 340 },
];

/* ── Helpers ───────────────────────────────────────────────────────── */
const Stars = ({ count, max }) => (
  <span className="inline-flex gap-px">{Array.from({ length: max }).map((_, i) => (
    <svg key={i} width="9" height="9" viewBox="0 0 24 24" fill={i < count ? "#F59E0B" : "none"} stroke={i < count ? "#F59E0B" : "#D1D5DB"} strokeWidth="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" /></svg>
  ))}</span>
);

const Heart = ({ filled }) => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill={filled ? brand : "none"} stroke={filled ? brand : "currentColor"} strokeWidth="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" /></svg>
);

const ChevDown = () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9" /></svg>;
const ChevUp = () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="18 15 12 9 6 15" /></svg>;
const Trophy = () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" strokeWidth="2"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6" /><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18" /><path d="M4 22h16" /><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20 7 22" /><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20 17 22" /><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z" /></svg>;
const Check = () => <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="3"><polyline points="20 6 9 17 4 12" /></svg>;

/* ── Sub-components ────────────────────────────────────────────────── */

function InsightCard({ c, onLike }) {
  return (
    <div className="bg-white border border-gray-100 rounded-[10px] p-4 hover:shadow-[0_1px_3px_rgba(0,0,0,0.04)] transition-all duration-200 mb-3">
      <p style={{ fontSize: 13, fontWeight: 400, color: "#1f2937", lineHeight: 1.8 }}>"{c.quote}"</p>
      <div className="flex items-center justify-between mt-3">
        <div className="flex items-center gap-1.5">
          <span style={{ fontSize: 11, color: "#9CA3AF" }}>{c.ai ? "\u{1F916}" : "\u{1F464}"} {c.author}</span>
          <span className="rounded-[6px] bg-gray-50 px-1.5 py-0.5" style={{ fontSize: 10, color: "#9CA3AF" }}>{c.src} \u00B7 {c.week}</span>
        </div>
        <button onClick={() => onLike(c.id)} className="flex items-center gap-1 hover:opacity-70 transition-opacity" style={{ fontSize: 11, color: "#D1D5DB", border: "none", background: "none", cursor: "pointer" }}>
          <Heart filled={c.liked} /><span>{c.likes}</span>
        </button>
      </div>
    </div>
  );
}

function PendingCard({ item, onPush, onSkip }) {
  return (
    <div className="bg-white border border-gray-100 rounded-[10px] p-4">
      <p style={{ fontSize: 13, color: "#1f2937", lineHeight: 1.8 }}>"{item.quote}"</p>
      <p style={{ fontSize: 11, color: "#9CA3AF", marginTop: 6 }}>\u6765\u6E90\uFF1A{item.src}</p>
      <div className="flex items-center gap-2 mt-3">
        <button onClick={() => onPush(item.id)} className="rounded-[10px] text-white px-3.5 py-1.5 hover:opacity-90 transition-opacity" style={{ fontSize: 12, fontWeight: 500, background: brand, border: "none", cursor: "pointer" }}>\u63A8\u4E0A\u7ECF\u9A8C\u5899</button>
        <button onClick={() => onSkip(item.id)} className="rounded-[10px] border border-gray-200 px-3.5 py-1.5 hover:bg-gray-50 transition-colors" style={{ fontSize: 12, fontWeight: 500, color: "#6B7280", background: "white", cursor: "pointer" }}>\u8DF3\u8FC7</button>
      </div>
    </div>
  );
}

function TemplateCard({ t }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="bg-white border border-gray-100 rounded-[10px] overflow-hidden">
      <button onClick={() => setOpen(!open)} className="w-full px-4 py-3.5 flex items-center gap-3 hover:bg-gray-50/50 transition-colors" style={{ border: "none", background: "transparent", cursor: "pointer", textAlign: "left" }}>
        <span style={{ fontSize: 15 }}>{"\u{1F4CB}"}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <span style={{ fontSize: 13, fontWeight: 600, color: "#1f2937" }} className="truncate">{t.name}</span>
            <span style={{ fontSize: 12, fontWeight: 500, color: brand }} className="shrink-0 ml-3">\u8C03\u7528 {t.calls} \u6B21</span>
          </div>
          <div className="flex items-center gap-3 mt-1.5">
            <span style={{ fontSize: 11, color: "#9CA3AF" }}>{t.steps.length} \u4E2A\u6B65\u9AA4 \u00B7 +{t.xp} XP</span>
            <div className="flex-1 h-[3px] bg-gray-100 rounded-full overflow-hidden">
              <div className="h-full rounded-full transition-all duration-500" style={{ width: `${Math.min(100, (t.calls / 10) * 100)}%`, background: `${brand}66` }} />
            </div>
          </div>
        </div>
        <span style={{ color: "#D1D5DB" }}>{open ? <ChevUp /> : <ChevDown />}</span>
      </button>
      {open && (
        <div className="px-4 pb-3.5">
          <div className="rounded-[10px] bg-gray-50 p-3">
            {t.steps.map((s, i) => (
              <div key={i} className="flex items-center gap-2 py-1">
                <span style={{ fontSize: 11, fontWeight: 500, color: "#D1D5DB", width: 16, textAlign: "right" }}>{i + 1}.</span>
                <span style={{ fontSize: 12, color: "#6B7280" }}>{s}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function BadgeItem({ b, onClick }) {
  const u = b.status === "unlocked";
  const p = b.status === "progress";
  return (
    <button
      onClick={() => onClick(b)}
      className={`flex flex-col items-center justify-center gap-1 p-2 aspect-square rounded-[10px] transition-all duration-200 ${u ? "bg-white border border-blue-100 hover:border-blue-300" : p ? "bg-blue-50/50 border border-gray-200 hover:border-blue-200" : "bg-gray-50 border border-dashed border-gray-200 hover:bg-gray-100"}`}
      style={{ cursor: "pointer" }}
    >
      <span style={{ fontSize: 20 }} className={b.status === "locked" ? "opacity-30 grayscale" : ""}>{b.status === "locked" ? "\u{1F512}" : b.emoji}</span>
      <span style={{ fontSize: 10, fontWeight: 500, lineHeight: 1.2, textAlign: "center", color: u ? "#374151" : p ? "#6B7280" : "#D1D5DB" }}>{b.status === "locked" ? "???" : b.name}</span>
      {u && b.type === "upgrade" && <Stars count={b.stars} max={b.max} />}
      {u && b.type === "achievement" && <Check />}
      {p && b.pct != null && <span style={{ fontSize: 9, fontWeight: 500, color: brand }}>{b.pct}%</span>}
    </button>
  );
}

function BadgeModal({ b, onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.15)" }} onClick={onClose}>
      <div className="rounded-[16px] bg-white shadow-[0_4px_12px_rgba(0,0,0,0.06)] p-6 w-80 max-w-[90vw]" onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-3 mb-4">
          <span style={{ fontSize: 28 }}>{b.emoji}</span>
          <div>
            <p style={{ fontSize: 15, fontWeight: 600, color: "#1f2937" }}>{b.name}</p>
            {b.type === "upgrade" && b.stars != null && <Stars count={b.stars} max={b.max} />}
          </div>
        </div>
        <p style={{ fontSize: 13, color: "#374151", lineHeight: 1.7 }}>{b.desc}</p>
        {b.next && <div className="rounded-[6px] bg-gray-50 px-3 py-2 mt-3"><p style={{ fontSize: 11, color: "#9CA3AF" }}>{b.type === "upgrade" ? "\u4E0B\u4E00\u7EA7" : "\u8FBE\u6210\u6761\u4EF6"}\uFF1A{b.next}</p></div>}
        {b.at && <p style={{ fontSize: 11, color: "#9CA3AF", marginTop: 10 }}>\u83B7\u5F97\u65F6\u95F4\uFF1A{b.at}\u3000+{b.xp} XP</p>}
        <button onClick={onClose} className="w-full rounded-[10px] border border-gray-200 py-2 mt-4 hover:bg-gray-50 transition-colors" style={{ fontSize: 12, fontWeight: 500, color: "#6B7280", background: "white", cursor: "pointer" }}>\u5173\u95ED</button>
      </div>
    </div>
  );
}

function RankRow({ e, maxXp }) {
  const w = maxXp > 0 ? (e.xp / maxXp) * 100 : 0;
  const mc = e.rank === 1 ? "#F59E0B" : e.rank === 2 ? "#9CA3AF" : e.rank === 3 ? "#D97706" : "#9CA3AF";
  const bc = e.rank === 1 ? "#F59E0B" : e.rank === 2 ? brand : e.rank === 3 ? "#D97706" : "#D1D5DB";
  return (
    <div className={`flex items-center gap-3 px-3.5 py-2.5 rounded-[10px] ${e.rank <= 3 ? "bg-gray-50/70" : ""}`}>
      <span style={{ fontSize: 13, fontWeight: 600, width: 20, textAlign: "center", color: mc }}>{e.rank}</span>
      <span style={{ fontSize: 13 }}>{e.ai ? "\u{1F916}" : "\u{1F464}"}</span>
      <span className="truncate" style={{ fontSize: 13, fontWeight: 500, color: "#374151", width: 64 }}>{e.name}</span>
      <span className="shrink-0 text-right" style={{ fontSize: 12, fontWeight: 500, color: "#6B7280", width: 64 }}>{e.xp.toLocaleString()}</span>
      <div className="flex-1 h-[3px] bg-gray-100 rounded-full overflow-hidden ml-1">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${w}%`, background: bc }} />
      </div>
    </div>
  );
}

/* ── Tab panels ────────────────────────────────────────────────────── */

function ExperienceTab() {
  const [cards, setCards] = useState(INSIGHTS);
  const [pending, setPending] = useState(PENDING);
  const like = useCallback(id => setCards(p => p.map(c => c.id === id ? { ...c, liked: !c.liked, likes: c.liked ? c.likes - 1 : c.likes + 1 } : c)), []);
  const col1 = cards.filter((_, i) => i % 2 === 0);
  const col2 = cards.filter((_, i) => i % 2 === 1);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div>
        <p style={{ fontSize: 15, fontWeight: 600, color: "#1f2937", marginBottom: 12 }}>\u7EC4\u7EC7\u7ECF\u9A8C\u5899</p>
        <div className="grid grid-cols-2 gap-3">
          <div>{col1.map(c => <InsightCard key={c.id} c={c} onLike={like} />)}</div>
          <div>{col2.map(c => <InsightCard key={c.id} c={c} onLike={like} />)}</div>
        </div>
      </div>
      {pending.length > 0 && (
        <div className="rounded-[10px] border border-blue-100 p-4" style={{ background: "#f7f9ff" }}>
          <p style={{ fontSize: 13, fontWeight: 500, color: brand, marginBottom: 12 }}>{"\u{1F4A1}"} AI \u4E3A\u4F60\u63D0\u70BC\u4E86 {pending.length} \u6761\u7ECF\u9A8C</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {pending.map(p => <PendingCard key={p.id} item={p} onPush={id => setPending(a => a.filter(x => x.id !== id))} onSkip={id => setPending(a => a.filter(x => x.id !== id))} />)}
          </div>
        </div>
      )}
    </div>
  );
}

function ContributionTab() {
  const tot = TEMPLATES.length;
  const calls = TEMPLATES.reduce((s, t) => s + t.calls, 0);
  const xp = TEMPLATES.reduce((s, t) => s + t.xp, 0);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div className="bg-white border border-gray-100 rounded-[10px] px-5 py-4 flex items-center" style={{ gap: 0 }}>
        {[{ l: "\u6211\u521B\u5EFA\u7684\u6A21\u677F", v: tot }, { l: "\u88AB\u8C03\u7528\u6B21\u6570", v: calls }, { l: "\u7D2F\u8BA1\u8D21\u732E XP", v: `+${xp}` }, { l: "\u672C\u6708", v: "+52" }].map((s, i) => (
          <div key={s.l} className="flex-1 text-center" style={{ borderLeft: i > 0 ? "1px solid #F3F4F6" : "none", paddingLeft: i > 0 ? 12 : 0 }}>
            <p style={{ fontSize: 11, color: "#9CA3AF" }}>{s.l}</p>
            <p style={{ fontSize: 20, fontWeight: 600, color: "#1f2937", marginTop: 2 }}>{s.v}</p>
          </div>
        ))}
      </div>
      <div>
        <p style={{ fontSize: 15, fontWeight: 600, color: "#1f2937", marginBottom: 12 }}>\u5DE5\u4F5C\u6A21\u677F</p>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {TEMPLATES.map(t => <TemplateCard key={t.id} t={t} />)}
        </div>
      </div>
    </div>
  );
}

function BadgesTab() {
  const [sel, setSel] = useState(null);
  const [mode, setMode] = useState("total");
  const unlocked = BADGES.filter(b => b.status === "unlocked").length;
  const maxXp = RANKS[0]?.xp || 1;
  const breakdown = [{ l: "\u6A21\u677F\u8D21\u732E", v: 56 }, { l: "\u7ECF\u9A8C\u5899", v: 30 }, { l: "\u6D41\u7A0B\u8C03\u7528", v: 36 }, { l: "\u6267\u884C\u8D28\u91CF", v: 30 }];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* XP card */}
      <div className="bg-white border border-gray-100 rounded-[10px] p-5">
        <div className="flex items-center gap-3 mb-4">
          <span style={{ fontSize: 24 }}>{"\u2694\uFE0F"}</span>
          <div>
            <p style={{ fontSize: 15, fontWeight: 600, color: "#1f2937" }}>\u9EC4\u91D1 III</p>
            <p style={{ fontSize: 22, fontWeight: 600, color: "#111827", lineHeight: 1.2 }}>1,523 <span style={{ fontSize: 13, fontWeight: 400, color: "#9CA3AF" }}>XP</span></p>
          </div>
          <div className="ml-auto text-right">
            <p style={{ fontSize: 11, fontWeight: 500, color: "#10B981" }}>+152 \u672C\u5468</p>
          </div>
        </div>
        <div className="mb-1 flex items-center justify-between">
          <p style={{ fontSize: 11, color: "#9CA3AF" }}>\u8DDD\u94C2\u91D1 I \u8FD8\u9700 277 XP</p>
          <p style={{ fontSize: 11, color: "#9CA3AF" }}>85%</p>
        </div>
        <div className="h-1 bg-gray-100 rounded-full overflow-hidden">
          <div className="h-full rounded-full" style={{ width: "85%", background: brand, transition: "width 0.7s" }} />
        </div>
        <div className="grid grid-cols-4 gap-2 mt-4">
          {breakdown.map(b => (
            <div key={b.l} className="rounded-[10px] px-2.5 py-2 text-center" style={{ background: "#f7f9ff" }}>
              <p style={{ fontSize: 15, fontWeight: 600, color: "#1f2937" }}>{b.v}</p>
              <p style={{ fontSize: 10, color: "#9CA3AF", marginTop: 2 }}>{b.l}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Badges */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <p style={{ fontSize: 15, fontWeight: 600, color: "#1f2937" }}>\u6211\u7684\u5FBD\u7AE0</p>
          <p style={{ fontSize: 11, color: "#9CA3AF" }}>\u5DF2\u70B9\u4EAE {unlocked}/{BADGES.length}</p>
        </div>
        <div className="grid grid-cols-5 gap-2">
          {BADGES.map(b => <BadgeItem key={b.id} b={b} onClick={setSel} />)}
        </div>
      </div>

      {/* Leaderboard */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2"><Trophy /><p style={{ fontSize: 15, fontWeight: 600, color: "#1f2937" }}>\u7EC4\u7EC7\u6392\u884C\u699C</p></div>
          <div className="rounded-[6px] bg-gray-100 p-0.5 flex">
            {["total", "weekly"].map(m => (
              <button key={m} onClick={() => setMode(m)} className={`px-2.5 py-1 rounded-[6px] transition-colors ${mode === m ? "bg-white text-gray-700 shadow-sm" : "text-gray-400 hover:text-gray-600"}`} style={{ fontSize: 11, fontWeight: 500, border: "none", cursor: "pointer", background: mode === m ? "white" : "transparent" }}>{m === "total" ? "\u603B\u699C" : "\u672C\u5468"}</button>
            ))}
          </div>
        </div>
        <div className="bg-white border border-gray-100 rounded-[10px] p-2" style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {RANKS.map(e => <RankRow key={e.rank} e={e} maxXp={maxXp} />)}
        </div>
        <div className="rounded-[10px] border border-amber-100 px-4 py-3 mt-3" style={{ background: "rgba(245,158,11,0.06)" }}>
          <p style={{ fontSize: 12, fontWeight: 500, color: "#B45309" }}>\u672C\u5468 MVP\uFF1A\u{1F464} \u987E\u6E90\u6E90\uFF08+152 XP\uFF09</p>
          <p style={{ fontSize: 11, color: "rgba(180,83,9,0.6)", marginTop: 2 }}>\u521B\u5EFA 2 \u4E2A\u5DE5\u4F5C\u6A21\u677F\uFF0C\u63A8\u9001 3 \u6761\u7ECF\u9A8C\u5899\u91D1\u53E5</p>
        </div>
      </div>

      {sel && <BadgeModal b={sel} onClose={() => setSel(null)} />}
    </div>
  );
}

/* ── Main component ────────────────────────────────────────────────── */

const TABS = [
  { key: "experience", label: "\u7ECF\u9A8C\u5899" },
  { key: "contribution", label: "\u7EC4\u7EC7\u8D21\u732E" },
  { key: "badges", label: "\u5FBD\u7AE0\u4E0E\u6392\u884C" },
];

export default function GrowthCenterView() {
  const [tab, setTab] = useState("experience");
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", background: "#F9FAFB", fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", overflow: "hidden" }}>
      {/* Header */}
      <div style={{ background: "white", borderBottom: "1px solid #F3F4F6", padding: "20px 24px 0", flexShrink: 0 }}>
        <div className="flex items-start justify-between mb-4">
          <div>
            <h1 style={{ fontSize: 18, fontWeight: 600, color: "#111827", margin: 0 }}>\u6210\u957F\u4E2D\u5FC3</h1>
            <p style={{ fontSize: 11, color: "#9CA3AF", marginTop: 2 }}>\u628A\u5DE5\u4F5C\u7ECF\u9A8C\u53D8\u6210\u7EC4\u7EC7\u8D44\u4EA7</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="rounded-[6px] border border-blue-100 px-2.5 py-1 flex items-center gap-1.5" style={{ background: "#f7f9ff" }}>
              <span style={{ fontSize: 13 }}>{"\u2694\uFE0F"}</span>
              <span style={{ fontSize: 12, fontWeight: 500, color: "#374151" }}>\u9EC4\u91D1 III</span>
            </div>
            <div className="text-right">
              <p style={{ fontSize: 13, fontWeight: 600, color: "#1f2937" }}>1,523 <span style={{ fontSize: 11, fontWeight: 400, color: "#9CA3AF" }}>XP</span></p>
              <p style={{ fontSize: 11, fontWeight: 500, color: "#10B981" }}>+152</p>
            </div>
          </div>
        </div>
        <div className="flex gap-6">
          {TABS.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)} style={{ fontSize: 13, fontWeight: 500, paddingBottom: 10, borderBottom: `2.5px solid ${tab === t.key ? brand : "transparent"}`, color: tab === t.key ? brand : "#9CA3AF", background: "none", border: "none", borderBottomWidth: 2.5, borderBottomStyle: "solid", borderBottomColor: tab === t.key ? brand : "transparent", cursor: "pointer", transition: "color 0.15s" }}>{t.label}</button>
          ))}
        </div>
      </div>
      {/* Content */}
      <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>
        <div style={{ maxWidth: 820, margin: "0 auto" }}>
          {tab === "experience" && <ExperienceTab />}
          {tab === "contribution" && <ContributionTab />}
          {tab === "badges" && <BadgesTab />}
        </div>
      </div>
    </div>
  );
}
