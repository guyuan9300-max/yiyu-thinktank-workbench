import React, { useMemo } from 'react';

import type { HealthResponse } from '../../../shared/types';

/**
 * 数据中心连接 + AI 模型 全局右上角灯。
 *
 * 显示逻辑：
 *   🟢 绿 — backend health 200 且 AI 真实配置（非 mock、key 已设、ready）
 *   🟡 黄 — backend 200 但 AI 未配置 / 缺 key / 不 ready
 *   🔴 红 — backend health 失败 / 数据中心不可达
 *
 * 文案简化：去掉"· 已连接"后缀，模型名走短名映射（豆包 2.0 / 通义 / GPT-5 / Kimi / Claude 等）。
 *
 * 点击 → 调 onClickConfigure 跳转到设置。
 */
export type GlobalAiStatusBadgeProps = {
  health: HealthResponse | null;
  backendOnline: boolean;
  onClickConfigure: () => void;
};

export function GlobalAiStatusBadge({ health, backendOnline, onClickConfigure }: GlobalAiStatusBadgeProps) {
  const status = useMemo(() => {
    if (!backendOnline) {
      return {
        tone: 'offline' as const,
        label: '数据中心离线',
        dot: 'bg-rose-500',
        chipClassName: 'border-rose-200 bg-rose-50/90 text-rose-700',
        title: '内置服务连接失败，请检查后端进程',
      };
    }
    if (!health?.ai.provider) {
      return {
        tone: 'pending' as const,
        label: '加载中',
        dot: 'bg-gray-400',
        chipClassName: 'border-gray-200 bg-white/90 text-gray-500',
        title: '正在读取当前模型',
      };
    }
    const shortName = shortAiModelLabel(health.ai.provider, health.ai.model, health.ai.providerLabel);
    const isReady = Boolean(
      health.ai.provider
      && health.ai.provider !== 'mock'
      && health.ai.ready,
    );
    if (isReady) {
      return {
        tone: 'online' as const,
        label: shortName,
        dot: 'bg-emerald-500',
        chipClassName: 'border-emerald-200 bg-emerald-50/90 text-emerald-700',
        title: `${health.ai.providerLabel || health.ai.provider}${health.ai.model ? ` · ${health.ai.model}` : ''}`,
      };
    }
    if (health.ai.provider === 'mock') {
      return {
        tone: 'warn' as const,
        label: '未配置模型',
        dot: 'bg-amber-500',
        chipClassName: 'border-amber-200 bg-amber-50/90 text-amber-700',
        title: '请到系统设置配置 AI 提供商',
      };
    }
    return {
      tone: 'warn' as const,
      label: `${shortName} · 未配置`,
      dot: 'bg-amber-500',
      chipClassName: 'border-amber-200 bg-amber-50/90 text-amber-700',
      title: health.ai.detail || '当前模型未就绪',
    };
  }, [backendOnline, health]);

  return (
    <button
      type="button"
      onClick={onClickConfigure}
      title={status.title}
      className={`inline-flex items-center gap-1.5 rounded-full border py-1 pl-2 pr-3 text-[11px] font-bold tracking-[0.04em] shadow-sm backdrop-blur-sm transition-colors hover:brightness-95 ${status.chipClassName}`}
    >
      <span className={`inline-block h-2 w-2 rounded-full ${status.dot}`} />
      {status.label}
    </button>
  );
}

/**
 * 把 provider + model + label 映射到简短显示名。
 * 没识别到时退到 providerLabel 或 model。
 */
export function shortAiModelLabel(
  provider?: string | null,
  model?: string | null,
  providerLabel?: string | null,
): string {
  const p = (provider || '').toLowerCase().trim();
  const m = (model || '').toLowerCase().trim();

  // 豆包 / 火山方舟 - 任何 doubao-* 都归到"豆包 2.0"（项目内 doubao-seed-2-0-pro-* 系列）
  if (p.includes('doubao') || p.includes('volc') || p.includes('ark') || m.includes('doubao')) {
    if (m.includes('1-5') || m.includes('1.5')) return '豆包 1.5';
    return '豆包 2.0';
  }
  // 通义 / qwen
  if (p.includes('qwen') || p.includes('tongyi') || m.includes('qwen')) {
    if (m.includes('vl')) return '通义 VL';
    if (m.includes('max')) return '通义 Max';
    if (m.includes('plus')) return '通义 Plus';
    return '通义';
  }
  // OpenAI 系列 — 抽出 GPT-X
  if (p.includes('openai') || m.startsWith('gpt') || m.startsWith('o1') || m.startsWith('o3') || m.startsWith('o4')) {
    if (m.startsWith('gpt-5') || m.includes('gpt5')) return 'GPT-5';
    if (m.startsWith('gpt-4o')) return 'GPT-4o';
    if (m.startsWith('gpt-4')) return 'GPT-4';
    if (m.startsWith('gpt-3')) return 'GPT-3.5';
    if (m.startsWith('o3')) return 'o3';
    if (m.startsWith('o1')) return 'o1';
    if (m.startsWith('o4')) return 'o4';
    return 'GPT';
  }
  // Anthropic Claude
  if (p.includes('anthropic') || p.includes('claude') || m.startsWith('claude')) {
    if (m.includes('opus')) return 'Claude Opus';
    if (m.includes('sonnet')) return 'Claude Sonnet';
    if (m.includes('haiku')) return 'Claude Haiku';
    return 'Claude';
  }
  // Kimi / Moonshot
  if (p.includes('kimi') || p.includes('moonshot') || m.includes('kimi') || m.includes('moonshot')) {
    return 'Kimi';
  }
  // DeepSeek
  if (p.includes('deepseek') || m.includes('deepseek')) {
    return 'DeepSeek';
  }
  // 智谱 ChatGLM
  if (p.includes('zhipu') || p.includes('glm') || m.startsWith('glm')) return '智谱 GLM';
  // 百川
  if (p.includes('baichuan') || m.includes('baichuan')) return '百川';
  // Gemini
  if (p.includes('gemini') || m.startsWith('gemini')) return 'Gemini';
  // mock
  if (p === 'mock') return '模拟';
  // 兜底：providerLabel 太长截断
  const fallback = (providerLabel || provider || model || 'AI').trim();
  if (fallback.length > 14) {
    return fallback.slice(0, 12) + '…';
  }
  return fallback || 'AI';
}
