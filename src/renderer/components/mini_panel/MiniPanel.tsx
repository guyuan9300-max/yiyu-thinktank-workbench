import { useMemo, useState } from 'react';
import { Check, ChevronLeft, ChevronRight, Maximize2, Plus, Settings } from 'lucide-react';

// ──────────────────────────────────────────────────────────────────────────
// 益语智库 · 迷你面板 — 北欧极简风
// 原则:大量留白、近乎单色(slate 中性)、克制单一品牌色 #5B7BFE 点缀、
//   无渐变 / 无装饰条 / 无重投影、发丝分隔线、靠字号字重分层级。
// 两张卡:「今天」(日程+待办) /「日历」(月历+当天)。纯 UI,数据走 props。
// ──────────────────────────────────────────────────────────────────────────

export type MiniEvent = { id: string; time: string; title: string; clientName?: string };
export type MiniTask = {
  id: string;
  title: string;
  done: boolean;
  dueLabel?: string;
  clientName?: string;
  overdue?: boolean;
};
export type MiniDay = { date: string; events: MiniEvent[]; tasks: MiniTask[] };

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

function fmtDateHeader(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  const wd = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][d.getDay()];
  return `${d.getMonth() + 1}月${d.getDate()}日 · ${wd}`;
}
function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

// 极简小节标题:仅一行轻量文字,无色块无 accent 条
function SectionLabel({ label, count }: { label: string; count?: number }) {
  return (
    <div className="mb-2 flex items-center gap-2 px-1">
      <span className="text-[11px] font-medium tracking-[0.08em] text-slate-400">{label}</span>
      {count !== undefined && count > 0 && <span className="text-[11px] text-slate-300">{count}</span>}
    </div>
  );
}

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
  const tab = (v: MiniView, label: string) => {
    const active = view === v;
    return (
      <button
        type="button"
        onClick={() => onView(v)}
        className={`relative px-1 pb-0.5 text-[13px] transition-colors ${
          active ? 'font-semibold text-slate-900' : 'font-normal text-slate-400 hover:text-slate-600'
        }`}
      >
        {label}
        {active && <span className="absolute -bottom-[3px] left-0 right-0 mx-auto h-[2px] w-3 rounded-full" style={{ background: ACCENT }} />}
      </button>
    );
  };
  return (
    <div className="window-drag flex items-center justify-between px-4 pt-3.5 pb-2.5">
      <div className="window-no-drag flex items-center gap-4">
        {tab('today', '今天')}
        {tab('calendar', '日历')}
      </div>
      <div className="window-no-drag flex items-center gap-0.5 text-slate-300">
        <button type="button" onClick={onOpenSettings} title="设置" className="inline-flex h-7 w-7 items-center justify-center rounded-lg transition-colors hover:bg-slate-100 hover:text-slate-500">
          <Settings size={14} />
        </button>
        <button type="button" onClick={onRestore} title="还原完整窗口" className="inline-flex h-7 w-7 items-center justify-center rounded-lg transition-colors hover:bg-slate-100 hover:text-slate-500">
          <Maximize2 size={14} />
        </button>
      </div>
    </div>
  );
}

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
    <div className="space-y-5">
      {/* 日程 */}
      <section>
        <SectionLabel label="日程" />
        {day.events.length === 0 ? (
          <p className="px-1 text-[12px] text-slate-300">今天没有安排</p>
        ) : (
          <ul>
            {day.events.map((e) => (
              <li key={e.id}>
                <button type="button" onClick={() => onOpenEvent?.(e.id)} className="flex w-full items-baseline gap-3 rounded-lg px-1 py-1.5 text-left transition-colors hover:bg-slate-50">
                  <span className="w-10 shrink-0 font-mono text-[12px] tabular-nums text-slate-400">{e.time}</span>
                  <span className="truncate text-[13px] text-slate-700">{e.title}</span>
                  {e.clientName && <span className="ml-auto shrink-0 text-[11px] text-slate-300">{e.clientName}</span>}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* 待办 */}
      <section>
        <SectionLabel label="待办" count={pending.length} />
        {day.tasks.length === 0 ? (
          <p className="px-1 text-[12px] text-slate-300">没有待办</p>
        ) : (
          <ul>
            {[...pending, ...done].map((t) => (
              <li key={t.id} className="group flex items-center gap-3 rounded-lg px-1 py-1.5 transition-colors hover:bg-slate-50">
                <button
                  type="button"
                  onClick={() => onToggleTask?.(t.id)}
                  aria-label={t.done ? '标为未完成' : '标为完成'}
                  className={`flex h-[17px] w-[17px] shrink-0 items-center justify-center rounded-[6px] border transition-colors ${
                    t.done ? 'border-[#5B7BFE] bg-[#5B7BFE] text-white' : 'border-slate-300 group-hover:border-slate-400'
                  }`}
                >
                  {t.done && <Check size={11} strokeWidth={3} />}
                </button>
                <button type="button" onClick={() => onOpenTask?.(t.id)} className={`flex min-w-0 flex-1 items-center gap-2 text-left ${t.done ? 'text-slate-300 line-through' : 'text-slate-700'}`}>
                  <span className="truncate text-[13px]">{t.title}</span>
                  {t.clientName && <span className="shrink-0 text-[11px] text-slate-300">{t.clientName}</span>}
                  {t.dueLabel && (
                    <span className={`ml-auto shrink-0 text-[11px] ${t.overdue ? 'text-rose-400' : 'text-slate-300'}`}>{t.dueLabel}</span>
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
  const submit = () => {
    const text = draft.trim();
    if (!text) return;
    onQuickAdd?.(text);
    setDraft('');
  };
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-baseline justify-between px-4 pb-3">
        <span className="text-[17px] font-semibold tracking-tight text-slate-900">{fmtDateHeader(today.date)}</span>
        {total > 0 && <span className="text-[12px] text-slate-300">{doneN}/{total}</span>}
      </div>
      <div className="workspace-thin-scroll min-h-0 flex-1 overflow-y-auto px-3 pb-2">
        <DayAgenda day={today} onToggleTask={onToggleTask} onOpenTask={onOpenTask} onOpenEvent={onOpenEvent} />
      </div>
      {/* 快速添加:发丝上分隔 + 极简输入 */}
      <div className="window-no-drag flex items-center gap-2.5 border-t border-slate-100 px-4 py-3">
        <Plus size={15} className="shrink-0 text-slate-300" />
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
          placeholder="添加任务"
          className="min-w-0 flex-1 bg-transparent text-[13px] text-slate-700 placeholder:text-slate-300 outline-none"
        />
      </div>
    </div>
  );
}

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
    for (let d = 1; d <= daysInMonth; d += 1) out.push(`${cursor.y}-${String(cursor.m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`);
    while (out.length % 7 !== 0) out.push(null);
    return out;
  }, [cursor]);

  const selectedDay: MiniDay = (selected === today.date ? today : getDay?.(selected)) ?? { date: selected, events: [], tasks: [] };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="window-no-drag flex items-center justify-between px-4 py-1">
        <button type="button" onClick={() => setCursor((c) => (c.m === 0 ? { y: c.y - 1, m: 11 } : { y: c.y, m: c.m - 1 }))} className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-slate-300 transition-colors hover:bg-slate-100 hover:text-slate-500">
          <ChevronLeft size={16} />
        </button>
        <span className="text-[14px] font-semibold tracking-tight text-slate-800">{cursor.y}年{cursor.m + 1}月</span>
        <button type="button" onClick={() => setCursor((c) => (c.m === 11 ? { y: c.y + 1, m: 0 } : { y: c.y, m: c.m + 1 }))} className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-slate-300 transition-colors hover:bg-slate-100 hover:text-slate-500">
          <ChevronRight size={16} />
        </button>
      </div>
      <div className="grid grid-cols-7 px-3 text-center text-[10px] font-medium text-slate-300">
        {['一', '二', '三', '四', '五', '六', '日'].map((w) => <div key={w} className="py-1.5">{w}</div>)}
      </div>
      <div className="window-no-drag grid grid-cols-7 gap-y-1 px-3">
        {cells.map((iso, i) => {
          if (!iso) return <div key={`e${i}`} />;
          const day = Number(iso.slice(8));
          const isToday = iso === tIso;
          const isSel = iso === selected;
          const hasItems = marked.has(iso);
          return (
            <button key={iso} type="button" onClick={() => setSelected(iso)} className="relative mx-auto flex h-8 w-8 items-center justify-center rounded-full text-[12px] transition-colors hover:bg-slate-100">
              <span
                className={isSel ? 'flex h-7 w-7 items-center justify-center rounded-full text-white' : isToday ? 'font-semibold text-[#5B7BFE]' : 'text-slate-600'}
                style={isSel ? { background: ACCENT } : undefined}
              >
                {day}
              </span>
              {hasItems && !isSel && <span className="absolute bottom-1 h-[3px] w-[3px] rounded-full bg-slate-300" />}
            </button>
          );
        })}
      </div>
      <div className="workspace-thin-scroll mt-3 min-h-0 flex-1 overflow-y-auto border-t border-slate-100 px-3 pb-2 pt-3">
        <div className="px-1 pb-2 text-[13px] font-semibold tracking-tight text-slate-700">{fmtDateHeader(selected)}</div>
        <DayAgenda day={selectedDay} onToggleTask={onToggleTask} onOpenTask={onOpenTask} onOpenEvent={onOpenEvent} />
      </div>
    </div>
  );
}

export function MiniPanel(props: MiniPanelProps) {
  const [view, setView] = useState<MiniView>('today');
  return (
    <div className="animate-fade-in flex h-full w-full flex-col overflow-hidden rounded-[20px] border border-slate-200/70 bg-white/95 shadow-[0_10px_40px_rgba(15,23,42,0.10)] backdrop-blur-xl">
      <MiniHeader view={view} onView={setView} onRestore={props.onRestore} onOpenSettings={props.onOpenSettings} />
      <div className="min-h-0 flex-1">
        {view === 'today' ? (
          <TodayCard today={props.today} onToggleTask={props.onToggleTask} onOpenTask={props.onOpenTask} onOpenEvent={props.onOpenEvent} onQuickAdd={props.onQuickAdd} />
        ) : (
          <CalendarCard markedDates={props.markedDates} getDay={props.getDay} today={props.today} onToggleTask={props.onToggleTask} onOpenTask={props.onOpenTask} onOpenEvent={props.onOpenEvent} />
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
    <div className="flex h-screen items-center justify-center bg-slate-100 p-6">
      <div style={{ width: 340, height: 460 }}>
        <MiniPanel
          today={data}
          markedDates={[data.date]}
          onToggleTask={(id) => setData((d) => ({ ...d, tasks: d.tasks.map((t) => (t.id === id ? { ...t, done: !t.done } : t)) }))}
          onQuickAdd={(text) => setData((d) => ({ ...d, tasks: [...d.tasks, { id: `t${Date.now()}`, title: text, done: false, dueLabel: '今天' }] }))}
          onRestore={() => undefined}
        />
      </div>
    </div>
  );
}

export default MiniPanel;
