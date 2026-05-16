import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, MessageCircle, Radio, Users, ChevronDown, ChevronUp } from 'lucide-react';
import { getDepartmentSignals } from '../../lib/api';
import type {
  DepartmentSignalActionAlert,
  DepartmentSignalsResponse,
  DepartmentSnapshot,
} from '../../../shared/types';

interface Props {
  weekLabel?: string | null;
  perspective: 'organization' | 'department' | 'mine';
  departmentId?: string | null;
}

const SEVERITY_STYLE: Record<string, { bg: string; border: string; text: string; dot: string }> = {
  high: { bg: 'bg-rose-50', border: 'border-rose-200', text: 'text-rose-700', dot: 'bg-rose-500' },
  medium: { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-700', dot: 'bg-amber-500' },
  low: { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-700', dot: 'bg-blue-500' },
};

const STATUS_STYLE: Record<string, { label: string; color: string; emoji: string }> = {
  abnormal: { label: '异常', color: 'text-rose-600', emoji: '🔴' },
  tight: { label: '紧', color: 'text-amber-600', emoji: '🟠' },
  stable: { label: '稳', color: 'text-emerald-600', emoji: '🟢' },
};

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function CompletionRing({ ratio, size = 56 }: { ratio: number; size?: number }) {
  const radius = size / 2 - 4;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - Math.max(0, Math.min(ratio, 1)));
  return (
    <svg width={size} height={size} className="-rotate-90">
      <circle cx={size / 2} cy={size / 2} r={radius} stroke="#E5E7EB" strokeWidth="6" fill="none" />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        stroke={ratio >= 0.7 ? '#10B981' : ratio >= 0.3 ? '#F59E0B' : '#9CA3AF'}
        strokeWidth="6"
        fill="none"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
      />
    </svg>
  );
}

function TemperatureBar({ level }: { level: number }) {
  const segments = 5;
  const filled = Math.max(0, Math.min(level, segments));
  return (
    <div className="flex items-center gap-[2px]">
      {Array.from({ length: segments }).map((_, i) => (
        <div
          key={i}
          className={`h-2 w-3 rounded-sm ${
            i < filled
              ? filled >= 4
                ? 'bg-rose-400'
                : filled >= 2
                  ? 'bg-amber-400'
                  : 'bg-emerald-400'
              : 'bg-gray-200'
          }`}
        />
      ))}
    </div>
  );
}

function BurndownMini({ ideal, actual }: { ideal: number[]; actual: number[] }) {
  if (!ideal.length) return null;
  const width = 140;
  const height = 28;
  const maxValue = Math.max(...ideal, ...actual, 1);
  const points = (values: number[]) =>
    values
      .map((v, i) => `${(i / Math.max(ideal.length - 1, 1)) * width},${height - (v / maxValue) * height}`)
      .join(' ');
  return (
    <svg width={width} height={height} className="block">
      <polyline
        points={points(ideal)}
        fill="none"
        stroke="#D1D5DB"
        strokeDasharray="3,3"
        strokeWidth="1.5"
      />
      {actual.length > 0 && (
        <polyline points={points(actual)} fill="none" stroke="#5B7BFE" strokeWidth="2" />
      )}
    </svg>
  );
}

function AlertCard({ alert }: { alert: DepartmentSignalActionAlert }) {
  const style = SEVERITY_STYLE[alert.severity] || SEVERITY_STYLE.medium;
  return (
    <div className={`rounded-2xl border ${style.border} ${style.bg} p-4`}>
      <div className="flex items-start gap-3">
        <div className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${style.dot}`} />
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className={`text-[13px] font-bold ${style.text}`}>{alert.title}</span>
            {alert.daysLeft != null && (
              <span className="rounded-full bg-white/70 px-2 py-0.5 text-[10px] font-bold text-gray-600">
                剩 {alert.daysLeft} 天
              </span>
            )}
          </div>
          <p className="text-[12px] leading-5 text-gray-700">
            <span className="font-bold text-gray-900">建议：</span>
            {alert.advice}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-gray-500">
            {alert.involvedDepartmentName && (
              <span className="rounded bg-white/80 px-2 py-0.5">{alert.involvedDepartmentName}</span>
            )}
            {alert.involvedUserNames && alert.involvedUserNames.length > 0 && (
              <span className="rounded bg-white/80 px-2 py-0.5">
                涉及：{alert.involvedUserNames.join('、')}
              </span>
            )}
            {alert.metricLabel && alert.metricValueText && (
              <span className="rounded bg-white/80 px-2 py-0.5">
                {alert.metricLabel} · {alert.metricValueText}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function DepartmentCard({ snapshot }: { snapshot: DepartmentSnapshot }) {
  const status = STATUS_STYLE[snapshot.status] || STATUS_STYLE.stable;
  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <h3 className="text-[15px] font-bold text-gray-900">{snapshot.departmentName}</h3>
          <p className="mt-0.5 text-[11px] text-gray-500">
            负责人 · {snapshot.leaderName || '未指定'}
          </p>
        </div>
        <div className={`text-[11px] font-bold ${status.color}`}>
          {status.emoji} {status.label}
        </div>
      </div>

      <div className="flex items-center gap-3 mb-3">
        <CompletionRing ratio={snapshot.completionRate} size={56} />
        <div className="flex-1 min-w-0">
          <p className="text-[11px] text-gray-500">完成率</p>
          <p className="text-[18px] font-bold text-gray-900">{formatPercent(snapshot.completionRate)}</p>
          <p className="mt-0.5 text-[11px] text-gray-500">
            {snapshot.planDoneCount} / {snapshot.planTotalCount} 项
          </p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 mb-3 text-[11px]">
        <div className="rounded bg-gray-50 px-2 py-1.5 text-center">
          <div className="text-gray-400">认领</div>
          <div className="font-bold text-gray-700">
            {snapshot.planAssignedCount}/{snapshot.planTotalCount}
          </div>
        </div>
        <div className="rounded bg-gray-50 px-2 py-1.5 text-center">
          <div className="text-gray-400">承接</div>
          <div className="font-bold text-gray-700">
            {snapshot.planLinkedCount}/{snapshot.planTotalCount}
          </div>
        </div>
        <div className="rounded bg-gray-50 px-2 py-1.5 text-center">
          <div className="text-gray-400">完成</div>
          <div className="font-bold text-gray-700">
            {snapshot.planDoneCount}/{snapshot.planTotalCount}
          </div>
        </div>
      </div>

      {snapshot.headlines.length > 0 && (
        <ul className="mb-3 space-y-1">
          {snapshot.headlines.map((line, idx) => (
            <li key={idx} className="text-[12px] leading-5 text-gray-600">
              · {line}
            </li>
          ))}
        </ul>
      )}

      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold text-gray-400">温度</span>
          <TemperatureBar level={snapshot.temperatureLevel} />
        </div>
        <BurndownMini ideal={snapshot.burndownIdeal} actual={snapshot.burndownActual} />
      </div>
    </div>
  );
}

export function DepartmentSignalsView({ weekLabel, perspective, departmentId }: Props) {
  const [data, setData] = useState<DepartmentSignalsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAllDepts, setShowAllDepts] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const resp = await getDepartmentSignals({
          weekLabel,
          perspective,
          departmentId,
        });
        if (!cancelled) setData(resp);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [weekLabel, perspective, departmentId]);

  const visibleSnapshots = useMemo(() => {
    if (!data) return [];
    if (showAllDepts) return data.departmentSnapshots;
    return data.departmentSnapshots.slice(0, 6);
  }, [data, showAllDepts]);

  if (loading && !data) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-2xl bg-white p-12 text-center text-gray-400 shadow-sm">
        <Radio size={24} />
        <p className="text-[13px]">加载部门信号中…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-rose-100 bg-rose-50 p-6">
        <p className="text-[13px] font-bold text-rose-700">部门信号加载失败</p>
        <p className="mt-1 text-[12px] text-rose-600">{error}</p>
      </div>
    );
  }

  if (!data) return null;

  const hasContent =
    data.actionAlerts.length > 0 ||
    data.oneOnOneSuggestions.length > 0 ||
    data.departmentSnapshots.length > 0;

  if (!hasContent) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-2xl bg-white p-12 text-center text-gray-400 shadow-sm">
        <Radio size={24} />
        <p className="font-bold text-gray-600 text-[15px]">本周协作驾驶舱无数据</p>
        <p className="text-[13px] text-gray-400 max-w-md">
          系统检查了部门计划、协作流转、任务承接，本周暂未发现需要主动介入的信号。
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {data.actionAlerts.length > 0 && (
        <section>
          <div className="mb-3 flex items-center gap-2">
            <AlertTriangle size={16} className="text-amber-500" />
            <h3 className="text-[14px] font-bold text-gray-900">
              本周建议出面的 {data.actionAlerts.length} 件事
            </h3>
          </div>
          <div className="space-y-2">
            {data.actionAlerts.map((alert) => (
              <AlertCard key={alert.id} alert={alert} />
            ))}
          </div>
        </section>
      )}

      {data.oneOnOneSuggestions.length > 0 && (
        <section>
          <div className="mb-3 flex items-center gap-2">
            <MessageCircle size={16} className="text-violet-500" />
            <h3 className="text-[14px] font-bold text-gray-900">
              本周建议 1:1 的 {data.oneOnOneSuggestions.length} 位伙伴
            </h3>
          </div>
          <div className="space-y-2">
            {data.oneOnOneSuggestions.map((suggestion) => (
              <div
                key={suggestion.userId}
                className="rounded-2xl border border-violet-100 bg-violet-50/40 p-4"
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[13px] font-bold text-gray-900">{suggestion.userName}</span>
                  {suggestion.departmentName && (
                    <span className="rounded bg-white/80 px-2 py-0.5 text-[10px] font-bold text-violet-700">
                      {suggestion.departmentName}
                    </span>
                  )}
                </div>
                <p className="text-[12px] text-gray-700 mb-2">{suggestion.reason}</p>
                <div className="flex flex-wrap gap-1.5">
                  {suggestion.questionPrompts.map((q, idx) => (
                    <span
                      key={idx}
                      className="rounded bg-white px-2 py-1 text-[11px] text-violet-700 border border-violet-100"
                    >
                      建议问：{q}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {data.departmentSnapshots.length > 0 && (
        <section>
          <div className="mb-3 flex items-center gap-2">
            <Users size={16} className="text-blue-500" />
            <h3 className="text-[14px] font-bold text-gray-900">部门体感</h3>
            <span className="text-[11px] text-gray-400">
              · {data.departmentSnapshots.length} 个部门
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {visibleSnapshots.map((snap) => (
              <DepartmentCard key={snap.departmentId} snapshot={snap} />
            ))}
          </div>
          {data.departmentSnapshots.length > 6 && (
            <button
              type="button"
              onClick={() => setShowAllDepts((v) => !v)}
              className="mt-3 inline-flex items-center gap-1 text-[12px] font-bold text-[#5B7BFE]"
            >
              {showAllDepts ? (
                <>
                  收起 <ChevronUp size={14} />
                </>
              ) : (
                <>
                  展开全部 <ChevronDown size={14} />
                </>
              )}
            </button>
          )}
        </section>
      )}
    </div>
  );
}
