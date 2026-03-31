import React from 'react';
import { Activity, AlertCircle, RefreshCw, Radar, ShieldAlert, Sparkles } from 'lucide-react';

import type { BettaFishSignal, DiagnosisEngineHealth, DiagnosisEngineMode } from '../../../shared/types';

type DiagnosisEnginePanelProps = {
  supported: boolean;
  selectedModeLabel: string;
  health: DiagnosisEngineHealth | null;
  engineMode: DiagnosisEngineMode;
  signal: BettaFishSignal | null;
  isRefreshingHealth: boolean;
  isRunning: boolean;
  error: string;
  onRefreshHealth: () => void;
  onRun: () => void;
  onEngineModeChange: (value: DiagnosisEngineMode) => void;
};

function getHealthBadge(health: DiagnosisEngineHealth | null) {
  if (!health) return { label: '未探测', className: 'bg-black/[0.05] text-black/45' };
  if (health.status === 'healthy') return { label: '已就绪', className: 'bg-emerald-50 text-emerald-600' };
  if (health.status === 'not_configured') return { label: '未配置', className: 'bg-black/[0.05] text-black/45' };
  if (health.status === 'not_installed') return { label: '未安装', className: 'bg-amber-50 text-amber-600' };
  if (health.status === 'disabled') return { label: '已关闭', className: 'bg-black/[0.05] text-black/45' };
  return { label: '不可达', className: 'bg-amber-50 text-amber-600' };
}

function getModeLabel(mode: DiagnosisEngineMode) {
  if (mode === 'fast') return '快速';
  if (mode === 'deep') return '深度';
  return '标准';
}

export function DiagnosisEnginePanel({
  supported,
  selectedModeLabel,
  health,
  engineMode,
  signal,
  isRefreshingHealth,
  isRunning,
  error,
  onRefreshHealth,
  onRun,
  onEngineModeChange,
}: DiagnosisEnginePanelProps) {
  const healthBadge = getHealthBadge(health);

  return (
    <div className="mt-6 rounded-[20px] border border-black/[0.05] bg-white p-5 shadow-[0_12px_28px_-20px_rgba(15,23,42,0.22)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-black/40">
            <Radar className="h-3.5 w-3.5" />
            外部信号诊断
          </div>
          <h3 className="mt-2 text-[18px] font-semibold tracking-tight text-black/90">BettaFish 外部感知层</h3>
          <p className="mt-2 max-w-[640px] text-[13px] leading-6 text-black/50">
            用独立 sidecar 补一层公域视角，重点看情绪感受、可信度、风险点和误读点，不改动当前诊断主链路。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${healthBadge.className}`}>{healthBadge.label}</span>
          <button
            type="button"
            onClick={onRefreshHealth}
            disabled={isRefreshingHealth}
            className="inline-flex h-[32px] items-center gap-1.5 rounded-[10px] border border-black/[0.06] px-3 text-[12px] font-medium text-black/60 hover:bg-black/[0.03] disabled:opacity-60"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isRefreshingHealth ? 'animate-spin' : ''}`} />
            刷新
          </button>
          <button
            type="button"
            onClick={onRun}
            disabled={!supported || health?.status !== 'healthy' || isRunning}
            className="inline-flex h-[34px] items-center gap-1.5 rounded-[10px] bg-[#0A53CC] px-4 text-[12px] font-semibold text-white shadow-[0_12px_24px_-14px_rgba(10,83,204,0.55)] disabled:opacity-60"
          >
            {isRunning ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Activity className="h-3.5 w-3.5" />}
            运行外部诊断
          </button>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {(['fast', 'standard', 'deep'] as DiagnosisEngineMode[]).map((mode) => {
          const isActive = mode === engineMode;
          return (
            <button
              key={mode}
              type="button"
              onClick={() => onEngineModeChange(mode)}
              className={`rounded-[9px] px-3 py-1.5 text-[11px] font-semibold transition-colors ${
                isActive ? 'bg-[#EAF2FF] text-[#0A53CC]' : 'bg-black/[0.04] text-black/50 hover:text-black/80'
              }`}
            >
              {getModeLabel(mode)}
            </button>
          );
        })}
        <span className="rounded-[9px] bg-black/[0.04] px-3 py-1.5 text-[11px] font-medium text-black/45">
          当前模式：{selectedModeLabel}
        </span>
        {health?.baseUrl && (
          <span className="rounded-[9px] bg-black/[0.04] px-3 py-1.5 text-[11px] font-medium text-black/45">
            {health.baseUrl}
          </span>
        )}
      </div>

      {supported && health?.status === 'healthy' && (
        <div className="mt-4 rounded-[14px] border border-black/[0.05] bg-[#F8F9FB] px-4 py-3 text-[12px] leading-6 text-black/45">
          {health.detail === 'llm_configured'
            ? '当前 bridge 已接到 BettaFish 隔离环境里的模型配置，外部信号会优先走 LLM 诊断。'
            : '当前 bridge 已启动，但还没读到 BettaFish 的模型配置，所以先用稳态启发式规则返回外部风险信号。'}
        </div>
      )}

      {!supported && (
        <div className="mt-4 rounded-[14px] border border-dashed border-black/[0.08] bg-[#F8F9FB] px-4 py-4 text-[13px] leading-6 text-black/45">
          当前工作区还没有接入 BettaFish。Phase 1 只先覆盖筹款文案和舆情公关，项目设计暂不进入外部信号链路。
        </div>
      )}

      {supported && (health?.status === 'disabled' || health?.status === 'not_configured') && (
        <div className="mt-4 rounded-[14px] border border-black/[0.05] bg-[#F8F9FB] px-4 py-4 text-[13px] leading-6 text-black/45">
          <div className="flex items-start gap-2">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-black/35" />
            <div>
              <p className="font-medium text-black/65">
                {health?.status === 'not_configured' ? 'BettaFish 当前还没接入本地环境。' : 'BettaFish 当前按配置关闭。'}
              </p>
              <p className="mt-1">
                {health?.status === 'not_configured'
                  ? '当前还没检测到可直接启动的本地仓库或独立 bridge 运行环境，所以工作台不会尝试拉起外部引擎。'
                  : '这是故意的稳定性保护。只有在本地 sidecar / bridge 就绪且未被显式关闭时，工作台才会真正调用外部引擎。'}
              </p>
              <p className="mt-1 text-[12px] text-black/38">默认会优先使用项目内的 `bettafish_bridge.py`。如需手工覆盖，仍可配置 `YIYU_BETTAFISH_ENABLED`、`YIYU_BETTAFISH_AUTOSTART` 与 `YIYU_BETTAFISH_START_COMMAND`。</p>
            </div>
          </div>
        </div>
      )}

      {supported && health?.status === 'not_installed' && (
        <div className="mt-4 rounded-[14px] border border-[#FFB36B]/20 bg-[#FFF7ED] px-4 py-4 text-[13px] leading-6 text-[#8A5A1F]">
          <div className="flex items-start gap-2">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-medium">BettaFish 已启用，但本地源码还没装好。</p>
              <p className="mt-1">{health.detail}</p>
              <p className="mt-1 text-[12px] text-[#8A5A1F]/80">可先运行安装脚本，把上游仓库拉到本项目的 `external/BettaFish`，再配置启动命令。</p>
            </div>
          </div>
        </div>
      )}

      {supported && health && !['disabled', 'not_configured', 'not_installed', 'healthy'].includes(health.status) && (
        <div className="mt-4 rounded-[14px] border border-[#FFB36B]/20 bg-[#FFF7ED] px-4 py-4 text-[13px] leading-6 text-[#8A5A1F]">
          <div className="flex items-start gap-2">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-medium">外部引擎当前不可达。</p>
              <p className="mt-1">{health.detail}</p>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="mt-4 rounded-[14px] border border-[#FF5A4F]/15 bg-[#FFF4F2] px-4 py-4 text-[13px] leading-6 text-[#C63F35]">
          <div className="flex items-start gap-2">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-medium">本次外部诊断失败。</p>
              <p className="mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      {supported && signal ? (
        <div className="mt-5 grid gap-4 xl:grid-cols-[1.1fr_1fr]">
          <div className="rounded-[16px] border border-black/[0.05] bg-[#F8F9FB] p-4">
            <div className="flex flex-wrap gap-2">
              <span className="rounded-[8px] bg-[#EAF2FF] px-2.5 py-1 text-[11px] font-semibold text-[#0A53CC]">情绪：{signal.emotion}</span>
              <span className="rounded-[8px] bg-black/[0.04] px-2.5 py-1 text-[11px] font-semibold text-black/55">可信度：{signal.credibility}</span>
              <span className="rounded-[8px] bg-black/[0.04] px-2.5 py-1 text-[11px] font-semibold text-black/55">模式：{getModeLabel(signal.mode)}</span>
            </div>
            <p className="mt-3 text-[12px] leading-6 text-black/45">
              最近一次运行：{new Date(signal.generatedAt).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })}
            </p>
            <div className="mt-4 rounded-[12px] bg-white px-4 py-3 text-[13px] leading-6 text-black/55">
              这层信号只补充“外部世界会怎么感受”，不会替代你当前的组织上下文判断和学习沉淀。
            </div>
          </div>

          <div className="grid gap-4">
            <div className="rounded-[16px] border border-[#FF5A4F]/10 bg-[#FFF7F6] p-4">
              <div className="flex items-center gap-2 text-[12px] font-semibold text-[#C63F35]">
                <ShieldAlert className="h-4 w-4" />
                风险点
              </div>
              <div className="mt-3 space-y-2">
                {(signal.riskPoints.length ? signal.riskPoints : ['本次没有返回明确风险点。']).map((item) => (
                  <div key={item} className="rounded-[10px] bg-white/90 px-3 py-2 text-[13px] leading-6 text-[#7A3832]">
                    {item}
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-[16px] border border-[#5B7BFE]/12 bg-[#F5F8FF] p-4">
              <div className="flex items-center gap-2 text-[12px] font-semibold text-[#0A53CC]">
                <Sparkles className="h-4 w-4" />
                误读点
              </div>
              <div className="mt-3 space-y-2">
                {(signal.misunderstandingPoints.length ? signal.misunderstandingPoints : ['本次没有返回明确误读点。']).map((item) => (
                  <div key={item} className="rounded-[10px] bg-white/90 px-3 py-2 text-[13px] leading-6 text-[#23499D]">
                    {item}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : supported && !error ? (
        <div className="mt-5 rounded-[16px] border border-dashed border-black/[0.08] bg-[#F8F9FB] px-5 py-6 text-[13px] leading-6 text-black/45">
          这里会显示 BettaFish 返回的外部信号。当前重点只看四类结果：情绪感受、可信度、风险点、误读点。
        </div>
      ) : null}
    </div>
  );
}
