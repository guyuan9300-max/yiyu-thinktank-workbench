import { useCallback, useEffect, useRef, useState } from 'react';
import { Cloud, HardDrive, Loader2, Play, Square } from 'lucide-react';

import {
  backfillLocalAi,
  getLocalAiCoverage,
  getLocalAiQueue,
  getLocalAiSettings,
  runLocalAiNow,
  updateLocalAiSettings,
  type LocalAiClientCoverage,
  type LocalAiOptimizationSettings,
} from '../../lib/api';

interface DeepReadSettingsCardProps {
  /** 当前工作台客户。null = 没选客户（按钮按全库范围）。 */
  clientId: string | null;
  /** 是否有权改敏感设置（云端只读账号为 false）。 */
  canEdit: boolean;
  onFlash?: (tone: 'info' | 'success' | 'error', message: string) => void;
}

// 自动解析打开时写入的一套"温柔"默认：夜间窗口 + 插电 + 需空闲，确保不影响白天使用。
const AUTO_ON_PATCH: Partial<LocalAiOptimizationSettings> = {
  enabled: true,
  paused: false,
  dailyWindows: [{ start: '22:00', end: '08:00' }],
  requireACPower: true,
  minIdleSeconds: 60,
};

export function DeepReadSettingsCard({ clientId, canEdit, onFlash }: DeepReadSettingsCardProps) {
  const [settings, setSettings] = useState<LocalAiOptimizationSettings | null>(null);
  const [coverage, setCoverage] = useState<LocalAiClientCoverage | null>(null);
  const [queued, setQueued] = useState(0);
  const [running, setRunning] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const mounted = useRef(true);

  const flash = useCallback(
    (tone: 'info' | 'success' | 'error', message: string) => onFlash?.(tone, message),
    [onFlash],
  );

  const refresh = useCallback(async () => {
    try {
      const [s, cov, queue] = await Promise.all([
        getLocalAiSettings(),
        getLocalAiCoverage(clientId || undefined),
        getLocalAiQueue({ taskType: 'document_card_generation', limit: 1 }),
      ]);
      if (!mounted.current) return;
      setSettings(s);
      setCoverage(cov.perClient.find((p) => p.clientId === clientId) ?? cov.perClient[0] ?? null);
      setQueued(Number(queue.totalByStatus?.queued ?? 0));
      setRunning(Number(queue.totalByStatus?.running ?? 0));
    } catch {
      /* 静默：面板是辅助信息，拉取失败不打断 */
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    return () => {
      mounted.current = false;
    };
  }, [refresh]);

  // 解析进行中时轮询，让进度条/状态自己往上爬。
  const active = Boolean(settings?.manualActive) || running > 0 || queued > 0;
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => void refresh(), 4000);
    return () => clearInterval(timer);
  }, [active, refresh]);

  const apply = useCallback(
    async (fn: () => Promise<unknown>, okMsg?: string) => {
      if (!canEdit || busy) return;
      setBusy(true);
      try {
        await fn();
        await refresh();
        if (okMsg) flash('success', okMsg);
      } catch (error: unknown) {
        flash('error', error instanceof Error ? error.message : '操作失败');
      } finally {
        if (mounted.current) setBusy(false);
      }
    },
    [canEdit, busy, refresh, flash],
  );

  const autoOn = settings?.enabled === true;
  const manualOn = settings?.manualActive === true;
  const parseLocal = settings?.parseModelMode === 'local';
  const pct = coverage && coverage.documents > 0 ? Math.round((coverage.deepRead / coverage.documents) * 100) : 0;

  const toggleAuto = () =>
    apply(
      () => updateLocalAiSettings(autoOn ? { enabled: false } : AUTO_ON_PATCH),
      autoOn ? '已关闭自动解析' : '已开启自动解析（空闲/夜间自动进行）',
    );

  const setMode = (mode: 'online' | 'local') => {
    if (settings?.parseModelMode === mode) return;
    void apply(() => updateLocalAiSettings({ parseModelMode: mode }));
  };

  const toggleManual = () => {
    if (manualOn) {
      void apply(() => updateLocalAiSettings({ manualActive: false }), '已停止解析');
      return;
    }
    void apply(async () => {
      await backfillLocalAi(clientId || undefined); // 把存量入队（幂等）
      await updateLocalAiSettings({ manualActive: true, paused: false }); // 开手动直跑
      await runLocalAiNow(true); // 立刻踢一条，不等下一轮轮询
    }, '已开始解析');
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 px-1 py-3 text-[12px] text-gray-400">
        <Loader2 size={13} className="animate-spin" /> 正在读取解析状态…
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-[12px] leading-5 text-gray-500">
        深度解析会占用内存和算力，建议<b className="text-gray-700">空闲/夜间自动进行</b>。也可立刻手动解析（会占用资源）。
      </p>

      {/* 解析进度 */}
      <div className="rounded-2xl border border-gray-100 bg-gray-50/70 px-4 py-3">
        <div className="mb-1.5 flex items-center justify-between text-[12px]">
          <span className="font-semibold text-gray-700">{clientId ? '当前客户解析率' : '全部客户解析率'}</span>
          <span className="font-bold text-[#5B7BFE]">{coverage ? `${coverage.deepRead}/${coverage.documents}` : '—'} · {pct}%</span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-200">
          <div className="h-full rounded-full bg-[#5B7BFE] transition-all" style={{ width: `${pct}%` }} />
        </div>
        <p className="mt-1.5 text-[11px] text-gray-400">
          {manualOn || running > 0 ? (
            <span className="inline-flex items-center gap-1 text-[#5B7BFE]">
              <Loader2 size={11} className="animate-spin" /> 解析中…{queued > 0 ? ` 待跑 ${queued}` : ''}
            </span>
          ) : autoOn ? '已开启自动解析（空闲/夜间）' : '未解析的文件不会进入公司大脑的深度理解'}
        </p>
      </div>

      {/* 自动解析开关 */}
      <label className="flex items-center justify-between">
        <span className="text-[13px] font-medium text-gray-800">自动解析<span className="ml-1 text-[11px] text-gray-400">空闲/夜间/插电时</span></span>
        <button
          type="button"
          role="switch"
          aria-checked={autoOn}
          disabled={!canEdit || busy}
          onClick={toggleAuto}
          className={`relative h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-40 ${autoOn ? 'bg-[#5B7BFE]' : 'bg-gray-300'}`}
        >
          <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${autoOn ? 'left-[22px]' : 'left-0.5'}`} />
        </button>
      </label>

      {/* 解析用模型 */}
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-medium text-gray-800">解析用模型</span>
        <div className="inline-flex rounded-xl border border-gray-200 bg-gray-50 p-0.5 text-[12px] font-semibold">
          <button
            type="button"
            disabled={!canEdit || busy}
            onClick={() => setMode('online')}
            className={`inline-flex items-center gap-1 rounded-lg px-3 py-1.5 transition-colors disabled:opacity-40 ${!parseLocal ? 'bg-white text-[#5B7BFE] shadow-sm' : 'text-gray-500'}`}
            title="跟主模型走（快，按量计费）"
          >
            <Cloud size={13} /> 线上
          </button>
          <button
            type="button"
            disabled={!canEdit || busy}
            onClick={() => setMode('local')}
            className={`inline-flex items-center gap-1 rounded-lg px-3 py-1.5 transition-colors disabled:opacity-40 ${parseLocal ? 'bg-white text-[#5B7BFE] shadow-sm' : 'text-gray-500'}`}
            title="本地 qwen3-vl:32b（免费，占本机算力）"
          >
            <HardDrive size={13} /> 本地
          </button>
        </div>
      </div>

      {/* 现在开始解析 / 停止 */}
      <button
        type="button"
        disabled={!canEdit || busy}
        onClick={toggleManual}
        className={`flex w-full items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-[13px] font-bold text-white transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${manualOn ? 'bg-rose-500 hover:bg-rose-600' : 'bg-[#5B7BFE] hover:bg-[#4a6af0]'}`}
      >
        {busy ? <Loader2 size={15} className="animate-spin" /> : manualOn ? <Square size={15} /> : <Play size={15} />}
        {manualOn ? '停止' : '现在开始解析'}
      </button>

      {!canEdit && <p className="text-[11px] text-amber-700">当前账号只能查看，不能修改解析设置。</p>}
    </div>
  );
}

export default DeepReadSettingsCard;
