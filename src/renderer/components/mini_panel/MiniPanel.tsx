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
// 益语智库 · 迷你面板(参考滴答清单桌面挂件)
// 两张卡:「今天」(日程+待办) / 「日历」(月历+当天)。无边框磨砂浮窗,可切换。
// 本文件是纯 UI + 清晰 props 接口;真实数据接入 + 缩小/还原窗口模式(主进程)为后续阶段。
// ──────────────────────────────────────────────────────────────────────────

export type MiniEvent = {
  id: string;
  time: string;        // "09:30"
  title: string;
  clientName?: string;
};

export type MiniTask = {
  id: string;
  title: string;
  done: boolean;
  dueLabel?: string;   // "今天" / "6/10" / "逾期"
  clientName?: string;
  overdue?: boolean;
};

export type MiniDay = {
  date: string;        // ISO "2026-05-28"
  events: MiniEvent[];
  tasks: MiniTask[];
};

export interface MiniPanelProps {
  /** 今天的日程 + 待办 */
  today: MiniDay;
  /** 日历视图:有日程/任务的日期(ISO) → 用于打点 */
  markedDates?: string[];
  /** 选中某天时拉那天的日程+待办(日历视图用);未提供则只展示 today */
  getDay?: (isoDate: string) => MiniDay | undefined;
  onToggleTask?: (taskId: string) => void;
  onOpenTask?: (taskId: string) => void;
  onOpenEvent?: (eventId: string) => void;
  onQuickAdd?: (text: string) => void;
  /** 还原成完整窗口 */
  onRestore?: () => void;
  onOpenSettings?: () => void;
}

type MiniView = 'today' | 'calendar';

const ACCENT = '#5B7BFE';

function fmtDateHeader(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  const wd = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][d.getDay()];
  return `${d.getMonth() + 1}月${d.getDate()}日 ${wd}`;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

// ── 顶栏:视图 tab + 还原 + 设置 ──────────────────────────────────────────
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
        className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-[12px] font-semibold transition-colors ${
          active ? 'bg-white text-[#5B7BFE] shadow-sm' : 'text-slate-500 hover:text-slate-700'
        }`}
      >
        <Icon size={13} />
        {label}
      </button>
    );
  };
  return (
    <div
      className="flex items-center justify-between gap-2 px-2.5 py-2"
      style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}  // 整条顶栏可拖动浮窗
    >
      <div
        className="inline-flex items-center gap-0.5 rounded-xl bg-slate-100/80 p-0.5"
        style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
      >
        {tab('today', '今天', ListTodo)}
        {tab('calendar', '日历', CalendarDays)}
      </div>
      <div
        className="flex items-center gap-0.5 text-slate-400"
        style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
      >
        <button
          type="button"
          onClick={onOpenSettings}
          title="设置(透明度 / 置顶 / 主题)"
          className="inline-flex h-6 w-6 items-center justify-center rounded-md hover:bg-slate-100 hover:text-slate-600"
        >
          <Settings size={13} />
        </button>
        <button
          type="button"
          onClick={onRestore}
          title="还原完整窗口"
          className="inline-flex h-6 w-6 items-center justify-center rounded-md hover:bg-slate-100 hover:text-slate-600"
        >
          <Maximize2 size={13} />
        </button>
      </div>
    </div>
  );
}

// ── 日程 + 待办 公共块(今天卡 / 日历选中日 共用) ─────────────────────────
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
  const doneCount = day.tasks.length - pending.length;
  return (
    <div className="space-y-3">
      {/* 日程 */}
      <section>
        <div className="mb-1 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-slate-400">
          <Clock size={11} /> 日程
        </div>
        {day.events.length === 0 ? (
          <p className="px-1 text-[12px] text-slate-300">今天没有安排</p>
        ) : (
          <ul className="space-y-1">
            {day.events.map((e) => (
              <li key={e.id}>
                <button
                  type="button"
                  onClick={() => onOpenEvent?.(e.id)}
                  className="flex w-full items-baseline gap-2 rounded-lg px-1.5 py-1 text-left hover:bg-slate-50"
                >
                  <span className="shrink-0 font-mono text-[12px] font-bold text-[#5B7BFE]">{e.time}</span>
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
        <div className="mb-1 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-slate-400">
          <ListTodo size={11} /> 待办
          {pending.length > 0 && <span className="text-[#5B7BFE]">({pending.length})</span>}
        </div>
        {day.tasks.length === 0 ? (
          <p className="px-1 text-[12px] text-slate-300">没有待办</p>
        ) : (
          <ul className="space-y-0.5">
            {[...pending, ...day.tasks.filter((t) => t.done)].map((t) => (
              <li key={t.id} className="flex items-center gap-2 rounded-lg px-1.5 py-1 hover:bg-slate-50">
                <button
                  type="button"
                  onClick={() => onToggleTask?.(t.id)}
                  aria-label={t.done ? '标为未完成' : '标为完成'}
                  className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-[5px] border transition-colors ${
                    t.done ? 'border-[#5B7BFE] bg-[#5B7BFE] text-white' : 'border-slate-300 hover:border-[#5B7BFE]'
                  }`}
                >
                  {t.done && <Check size={11} strokeWidth={3} />}
                </button>
                <button
                  type="button"
                  onClick={() => onOpenTask?.(t.id)}
                  className={`flex min-w-0 flex-1 items-center gap-2 text-left ${t.done ? 'text-slate-400 line-through' : 'text-slate-800'}`}
                >
                  <span className="truncate text-[13px]">{t.title}</span>
                  {t.clientName && <span className="shrink-0 text-[10px] text-slate-400">·{t.clientName}</span>}
                  {t.dueLabel && (
                    <span className={`ml-auto shrink-0 text-[10px] font-semibold ${t.overdue ? 'text-rose-500' : 'text-slate-400'}`}>
                      {t.dueLabel}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
        {doneCount > 0 && <p className="mt-1 px-1.5 text-[10px] text-slate-300">已完成 {doneCount}</p>}
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
  const submit = () => {
    const text = draft.trim();
    if (!text) return;
    onQuickAdd?.(text);
    setDraft('');
  };
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="px-3 pb-1 text-[13px] font-bold text-slate-900">{fmtDateHeader(today.date)}</div>
      <div className="min-h-0 flex-1 overflow-y-auto px-1.5 pb-2">
        <DayAgenda day={today} onToggleTask={onToggleTask} onOpenTask={onOpenTask} onOpenEvent={onOpenEvent} />
      </div>
      {/* 快速添加 */}
      <div className="flex items-center gap-1.5 border-t border-slate-100 px-2.5 py-2">
        <Plus size={14} className="shrink-0 text-slate-400" />
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
          placeholder="快速添加任务…"
          className="min-w-0 flex-1 bg-transparent text-[13px] text-slate-800 placeholder:text-slate-300 outline-none"
        />
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
    return { y: d.getFullYear(), m: d.getMonth() }; // m: 0-11
  });
  const [selected, setSelected] = useState(today.date);

  const marked = useMemo(() => new Set(markedDates), [markedDates]);

  // 计算月历网格(周一起始,6 行 x 7 列)
  const cells = useMemo(() => {
    const first = new Date(cursor.y, cursor.m, 1);
    const startOffset = (first.getDay() + 6) % 7; // 周一=0
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
      <div className="flex items-center justify-between px-3 py-1">
        <button type="button" onClick={() => setCursor((c) => (c.m === 0 ? { y: c.y - 1, m: 11 } : { y: c.y, m: c.m - 1 }))}
          className="inline-flex h-6 w-6 items-center justify-center rounded-md text-slate-400 hover:bg-slate-100">
          <ChevronLeft size={15} />
        </button>
        <span className="text-[13px] font-bold text-slate-900">{cursor.y}年{cursor.m + 1}月</span>
        <button type="button" onClick={() => setCursor((c) => (c.m === 11 ? { y: c.y + 1, m: 0 } : { y: c.y, m: c.m + 1 }))}
          className="inline-flex h-6 w-6 items-center justify-center rounded-md text-slate-400 hover:bg-slate-100">
          <ChevronRight size={15} />
        </button>
      </div>
      {/* 星期表头 */}
      <div className="grid grid-cols-7 px-2 text-center text-[10px] font-semibold text-slate-400">
        {['一', '二', '三', '四', '五', '六', '日'].map((w) => <div key={w} className="py-0.5">{w}</div>)}
      </div>
      {/* 日期网格 */}
      <div className="grid grid-cols-7 gap-y-0.5 px-2">
        {cells.map((iso, i) => {
          if (!iso) return <div key={`e${i}`} />;
          const day = Number(iso.slice(8));
          const isToday = iso === tIso;
          const isSel = iso === selected;
          const hasItems = marked.has(iso);
          return (
            <button key={iso} type="button" onClick={() => setSelected(iso)}
              className="relative mx-auto flex h-7 w-7 items-center justify-center rounded-full text-[12px] transition-colors"
              style={isSel ? { background: ACCENT, color: '#fff' } : undefined}>
              <span className={!isSel && isToday ? 'font-bold text-[#5B7BFE]' : !isSel ? 'text-slate-700' : ''}>{day}</span>
              {hasItems && !isSel && <span className="absolute bottom-0.5 h-1 w-1 rounded-full" style={{ background: ACCENT }} />}
            </button>
          );
        })}
      </div>
      {/* 选中日 议程 */}
      <div className="mt-1 min-h-0 flex-1 overflow-y-auto border-t border-slate-100 px-1.5 pt-2 pb-2">
        <div className="px-1.5 pb-1 text-[12px] font-bold text-slate-700">{fmtDateHeader(selected)}</div>
        <DayAgenda day={selectedDay} onToggleTask={onToggleTask} onOpenTask={onOpenTask} onOpenEvent={onOpenEvent} />
      </div>
    </div>
  );
}

// ── 浮窗壳(磨砂卡片) ──────────────────────────────────────────────────────
export function MiniPanel(props: MiniPanelProps) {
  const [view, setView] = useState<MiniView>('today');
  return (
    <div
      className="flex h-full w-full flex-col overflow-hidden rounded-2xl border border-white/60 bg-white/85 shadow-[0_12px_48px_rgba(15,23,42,0.22)] backdrop-blur-xl"
      style={{ minWidth: 320, minHeight: 420 }}
    >
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

// ── 样例数据 + Demo(可直接挂到一个路由查看效果) ───────────────────────────
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
