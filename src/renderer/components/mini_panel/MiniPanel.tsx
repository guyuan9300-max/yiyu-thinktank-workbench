import { useMemo, useState } from 'react';
import {
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock,
  ListTodo,
  Maximize2,
  Plus,
  Settings,
} from 'lucide-react';

// ──────────────────────────────────────────────────────────────────────────
// 益语智库 · 迷你面板(参考滴答清单桌面挂件)— 对齐全软件 UI 设计语言
// 设计 token: airy-blue #5B7BFE / 品牌渐变 / shadow-airy 蓝调柔光 / glass /
//   eyebrow uppercase tracking / rounded-2xl / .window-drag / fade 动画。
// 两张卡:「今天」(日程+待办) /「日历」(月历+当天)。纯 UI,数据走 props。
// ──────────────────────────────────────────────────────────────────────────

export type MiniEvent = {
  id: string;
  time: string;
  title: string;
  clientName?: string;
};

export type MiniTask = {
  id: string;
  title: string;
  done: boolean;
  dueLabel?: string;
  clientName?: string;
  overdue?: boolean;
};

export type MiniDay = {
  date: string; // ISO "2026-05-28"
  events: MiniEvent[];
  tasks: MiniTask[];
};

export interface MiniPanelProps {
  today: MiniDay;
  markedDates?: string[];
  getDay?: (isoDate: string) => MiniDay | undefined;
  onToggleTask?: (taskId: string) => void;
  onOpenTask?: (taskId: string) => void;
  onOpenEvent?: (eventId: string) => void;
  onQuickAdd?: (text: string) => void;
  onRestore?: () => void;
  onOpenSettings?: () => void;
}

type MiniView = 'today' | 'calendar';

const ACCENT = '#5B7BFE';
const BRAND_GRADIENT = 'linear-gradient(135deg,#5B7BFE 0%,#7ea0ff 100%)';

function fmtDateHeader(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  const wd = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][d.getDay()];
  return `${d.getMonth() + 1}月${d.getDate()}日 ${wd}`;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

// 小节标题(eyebrow):品牌竖条 accent + 字母间距,呼应全软件 section 头风格
function SectionLabel({ icon: Icon, label, count }: { icon: typeof Clock; label: string; count?: number }) {
  return (
    <div className="mb-1.5 flex items-center gap-1.5 px-1.5">
      <span className="h-3 w-[3px] rounded-full" style={{ background: BRAND_GRADIENT }} />
      <Icon size={11} className="text-slate-400" />
      <span className="text-[11px] font-bold tracking-[0.12em] text-slate-400">{label}</span>
      {count !== undefined && count > 0 && (
        <span className="text-[11px] font-bold text-[#5B7BFE]">{count}</span>
      )}
    </div>
  );
}

// ── 顶栏:视图 tab(分段控件)+ 还原/设置 ───────────────────────────────────
function MiniHeader({
  view,
  onView,
  onRestore,
  onOpenSettings,
}: {
  view: MiniView;
  onView: (v: MiniView) => void;
  onRestore?: () => void;
  onOpenSettings?: () => void;
}) {
  const tab = (v: MiniView, label: string, Icon: typeof ListTodo) => {
    const active = view === v;
    return (
      <button
        type="button"
        onClick={() => onView(v)}
        className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-[12px] font-semibold transition-all ${
          active ? 'bg-white text-[#5B7BFE] shadow-sm' : 'text-slate-500 hover:text-slate-700'
        }`}
      >
        <Icon size={13} />
        {label}
      </button>
    );
  };
  return (
    <div className="window-drag flex items-center justify-between gap-2 px-2.5 pt-2.5 pb-1.5">
      <div className="window-no-drag inline-flex items-center gap-0.5 rounded-xl bg-slate-100/70 p-1">
        {tab('today', '今天', ListTodo)}
        {tab('calendar', '日历', CalendarDays)}
      </div>
      <div className="window-no-drag flex items-center gap-0.5 text-slate-400">
        <button
          type="button"
          onClick={onOpenSettings}
          title="设置(透明度 / 置顶 / 主题)"
          className="inline-flex h-7 w-7 items-center justify-center rounded-lg transition-colors hover:bg-slate-100 hover:text-slate-600"
        >
          <Settings size={14} />
        </button>
        <button
          type="button"
          onClick={onRestore}
          title="还原完整窗口"
          className="inline-flex h-7 w-7 items-center justify-center rounded-lg transition-colors hover:bg-slate-100 hover:text-slate-600"
        >
          <Maximize2 size={14} />
        </button>
      </div>
    </div>
  );
}

// ── 日程 + 待办 公共块 ──────────────────────────────────────────────────────
function DayAgenda({
  day,
  onToggleTask,
  onOpenTask,
  onOpenEvent,
}: {
  day: MiniDay;
  onToggleTask?: (id: string) => void;
  onOpenTask?: (id: string) => void;
  onOpenEvent?: (id: string) => void;
}) {
  const pending = day.tasks.filter((t) => !t.done);
  const done = day.tasks.filter((t) => t.done);
  return (
    <div className="space-y-3.5">
      {/* 日程 */}
      <section>
        <SectionLabel icon={Clock} label="日程" />
        {day.events.length === 0 ? (
          <p className="px-2.5 text-[12px] text-slate-300">今天没有安排</p>
        ) : (
          <ul className="space-y-0.5">
            {day.events.map((e) => (
              <li key={e.id}>
                <button
                  type="button"
                  onClick={() => onOpenEvent?.(e.id)}
                  className="flex w-full items-center gap-2.5 rounded-xl px-2 py-1.5 text-left transition-colors hover:bg-[#5B7BFE]/[0.06]"
                >
                  <span className="shrink-0 rounded-md bg-[#5B7BFE]/10 px-1.5 py-0.5 font-mono text-[11px] font-bold text-[#5B7BFE]">
                    {e.time}
                  </span>
                  <span className="truncate text-[13px] text-slate-800">{e.title}</span>
                  {e.clientName && <span className="ml-auto shrink-0 text-[10px] text-slate-400">{e.clientName}</span>}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* 待办 */}
      <section>
        <SectionLabel icon={ListTodo} label="待办" count={pending.length} />
        {day.tasks.length === 0 ? (
          <p className="px-2.5 text-[12px] text-slate-300">没有待办</p>
        ) : (
          <ul className="space-y-0.5">
            {[...pending, ...done].map((t) => (
              <li key={t.id} className="flex items-center gap-2.5 rounded-xl px-2 py-1.5 transition-colors hover:bg-slate-50">
                <button
                  type="button"
                  onClick={() => onToggleTask?.(t.id)}
                  aria-label={t.done ? '标为未完成' : '标为完成'}
                  className={`flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-md border transition-all ${
                    t.done ? 'border-transparent text-white' : 'border-slate-300 hover:border-[#5B7BFE]'
                  }`}
                  style={t.done ? { background: BRAND_GRADIENT } : undefined}
                >
                  {t.done && <Check size={12} strokeWidth={3} />}
                </button>
                <button
                  type="button"
                  onClick={() => onOpenTask?.(t.id)}
                  className={`flex min-w-0 flex-1 items-center gap-2 text-left ${t.done ? 'text-slate-400 line-through' : 'text-slate-800'}`}
                >
                  <span className="truncate text-[13px]">{t.title}</span>
                  {t.clientName && <span className="shrink-0 text-[10px] text-slate-400">·{t.clientName}</span>}
                  {t.dueLabel && (
                    <span
                      className={`ml-auto shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-bold ${
                        t.overdue ? 'bg-rose-50 text-rose-500' : 'bg-slate-100 text-slate-500'
                      }`}
                    >
                      {t.dueLabel}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

// ── 今天卡 ────────────────────────────────────────────────────────────────
function TodayCard({
  today,
  onToggleTask,
  onOpenTask,
  onOpenEvent,
  onQuickAdd,
}: Pick<MiniPanelProps, 'today' | 'onToggleTask' | 'onOpenTask' | 'onOpenEvent' | 'onQuickAdd'>) {
  const [draft, setDraft] = useState('');
  const total = today.tasks.length;
  const doneN = today.tasks.filter((t) => t.done).length;
  const pct = total ? Math.round((doneN / total) * 100) : 0;
  const submit = () => {
    const text = draft.trim();
    if (!text) return;
    onQuickAdd?.(text);
    setDraft('');
  };
  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* 日期 + 今日完成进度(品牌渐变细条) */}
      <div className="px-3.5 pb-2.5">
        <div className="flex items-baseline justify-between">
          <span className="text-[15px] font-bold tracking-tight text-slate-900">{fmtDateHeader(today.date)}</span>
          {total > 0 && <span className="text-[11px] font-semibold text-slate-400">今日 {doneN}/{total}</span>}
        </div>
        {total > 0 && (
          <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-slate-100">
            <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: BRAND_GRADIENT }} />
          </div>
        )}
      </div>
      <div className="workspace-thin-scroll min-h-0 flex-1 overflow-y-auto px-2 pb-2">
        <DayAgenda day={today} onToggleTask={onToggleTask} onOpenTask={onOpenTask} onOpenEvent={onOpenEvent} />
      </div>
      {/* 快速添加(药丸输入) */}
      <div className="window-no-drag px-2.5 pb-2.5 pt-1.5">
        <div className="flex items-center gap-2 rounded-xl bg-slate-50 px-3 py-2 transition-colors focus-within:bg-white focus-within:ring-1 focus-within:ring-[#5B7BFE]/30">
          <Plus size={14} className="shrink-0 text-[#5B7BFE]" />
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
            placeholder="快速添加任务…"
            className="min-w-0 flex-1 bg-transparent text-[13px] text-slate-800 placeholder:text-slate-300 outline-none"
          />
        </div>
      </div>
    </div>
  );
}

// ── 日历卡 ────────────────────────────────────────────────────────────────
function CalendarCard({
  markedDates = [],
  getDay,
  today,
  onToggleTask,
  onOpenTask,
  onOpenEvent,
}: Pick<MiniPanelProps, 'markedDates' | 'getDay' | 'today' | 'onToggleTask' | 'onOpenTask' | 'onOpenEvent'>) {
  const tIso = todayIso();
  const [cursor, setCursor] = useState(() => {
    const d = new Date(`${today.date}T00:00:00`);
    return { y: d.getFullYear(), m: d.getMonth() };
  });
  const [selected, setSelected] = useState(today.date);

  const marked = useMemo(() => new Set(markedDates), [markedDates]);

  const cells = useMemo(() => {
    const first = new Date(cursor.y, cursor.m, 1);
    const startOffset = (first.getDay() + 6) % 7;
    const daysInMonth = new Date(cursor.y, cursor.m + 1, 0).getDate();
    const out: (string | null)[] = [];
    for (let i = 0; i < startOffset; i += 1) out.push(null);
    for (let d = 1; d <= daysInMonth; d += 1) {
      out.push(`${cursor.y}-${String(cursor.m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`);
    }
    while (out.length % 7 !== 0) out.push(null);
    return out;
  }, [cursor]);

  const selectedDay: MiniDay = (selected === today.date ? today : getDay?.(selected)) ?? {
    date: selected,
    events: [],
    tasks: [],
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* 月份切换 */}
      <div className="window-no-drag flex items-center justify-between px-3.5 py-1">
        <button
          type="button"
          onClick={() => setCursor((c) => (c.m === 0 ? { y: c.y - 1, m: 11 } : { y: c.y, m: c.m - 1 }))}
          className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100"
        >
          <ChevronLeft size={16} />
        </button>
        <span className="text-[14px] font-bold tracking-tight text-slate-900">{cursor.y}年{cursor.m + 1}月</span>
        <button
          type="button"
          onClick={() => setCursor((c) => (c.m === 11 ? { y: c.y + 1, m: 0 } : { y: c.y, m: c.m + 1 }))}
          className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100"
        >
          <ChevronRight size={16} />
        </button>
      </div>
      {/* 星期表头 */}
      <div className="grid grid-cols-7 px-2.5 text-center text-[10px] font-bold tracking-wider text-slate-300">
        {['一', '二', '三', '四', '五', '六', '日'].map((w) => (
          <div key={w} className="py-1">{w}</div>
        ))}
      </div>
      {/* 日期网格 */}
      <div className="window-no-drag grid grid-cols-7 gap-y-1 px-2.5">
        {cells.map((iso, i) => {
          if (!iso) return <div key={`e${i}`} />;
          const day = Number(iso.slice(8));
          const isToday = iso === tIso;
          const isSel = iso === selected;
          const hasItems = marked.has(iso);
          return (
            <button
              key={iso}
              type="button"
              onClick={() => setSelected(iso)}
              className="relative mx-auto flex h-8 w-8 items-center justify-center rounded-full text-[12px] transition-all hover:bg-slate-100"
              style={isSel ? { background: BRAND_GRADIENT, color: '#fff', boxShadow: '0 4px 12px rgba(91,123,254,0.35)' } : undefined}
            >
              <span className={!isSel && isToday ? 'font-bold text-[#5B7BFE]' : !isSel ? 'text-slate-700' : ''}>{day}</span>
              {hasItems && !isSel && (
                <span className="absolute bottom-1 h-1 w-1 rounded-full" style={{ background: ACCENT }} />
              )}
            </button>
          );
        })}
      </div>
      {/* 选中日 议程 */}
      <div className="workspace-thin-scroll mt-2 min-h-0 flex-1 overflow-y-auto border-t border-slate-100 px-2 pb-2 pt-2.5">
        <div className="px-2 pb-1.5 text-[13px] font-bold tracking-tight text-slate-800">{fmtDateHeader(selected)}</div>
        <DayAgenda day={selectedDay} onToggleTask={onToggleTask} onOpenTask={onOpenTask} onOpenEvent={onOpenEvent} />
      </div>
    </div>
  );
}

// ── 浮窗壳(磨砂卡片 · 品牌阴影) ─────────────────────────────────────────────
export function MiniPanel(props: MiniPanelProps) {
  const [view, setView] = useState<MiniView>('today');
  return (
    <div className="animate-fade-in flex h-full w-full flex-col overflow-hidden rounded-[24px] border border-white/70 bg-white/85 shadow-[0_18px_56px_rgba(91,123,254,0.22)] backdrop-blur-2xl">
      {/* 顶部品牌渐变细条,呼应全软件的强调条 */}
      <div className="h-[3px] w-full shrink-0" style={{ background: BRAND_GRADIENT }} />
      <MiniHeader view={view} onView={setView} onRestore={props.onRestore} onOpenSettings={props.onOpenSettings} />
      <div className="min-h-0 flex-1">
        {view === 'today' ? (
          <TodayCard
            today={props.today}
            onToggleTask={props.onToggleTask}
            onOpenTask={props.onOpenTask}
            onOpenEvent={props.onOpenEvent}
            onQuickAdd={props.onQuickAdd}
          />
        ) : (
          <CalendarCard
            markedDates={props.markedDates}
            getDay={props.getDay}
            today={props.today}
            onToggleTask={props.onToggleTask}
            onOpenTask={props.onOpenTask}
            onOpenEvent={props.onOpenEvent}
          />
        )}
      </div>
    </div>
  );
}

// ── 样例数据 + Demo ─────────────────────────────────────────────────────────
const SAMPLE_TODAY: MiniDay = {
  date: todayIso(),
  events: [
    { id: 'e1', time: '09:30', title: '日慈 战略对齐会', clientName: '日慈' },
    { id: 'e2', time: '14:00', title: 'CFFC 合同评审', clientName: 'CFFC' },
  ],
  tasks: [
    { id: 't1', title: '输出第一版价值观建议稿', done: false, dueLabel: '今天', clientName: '日慈' },
    { id: 't2', title: '提交理事会汇报简版材料', done: false, dueLabel: '6/10', clientName: '日慈' },
    { id: 't3', title: '提供更轻量的试点方案及风险控制说明', done: false, dueLabel: '逾期', overdue: true, clientName: '日慈' },
    { id: 't4', title: '完成存量品牌素材评估', done: true, clientName: '日慈' },
  ],
};

export function MiniPanelDemo() {
  const [data, setData] = useState(SAMPLE_TODAY);
  return (
    <div className="flex h-screen items-center justify-center bg-slate-200 p-6">
      <div style={{ width: 340, height: 460 }}>
        <MiniPanel
          today={data}
          markedDates={[data.date]}
          onToggleTask={(id) =>
            setData((d) => ({ ...d, tasks: d.tasks.map((t) => (t.id === id ? { ...t, done: !t.done } : t)) }))
          }
          onQuickAdd={(text) =>
            setData((d) => ({ ...d, tasks: [...d.tasks, { id: `t${Date.now()}`, title: text, done: false, dueLabel: '今天' }] }))
          }
          onRestore={() => undefined}
        />
      </div>
    </div>
  );
}

export default MiniPanel;
