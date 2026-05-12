import { useCallback, useEffect, useRef, useState } from 'react';
import { Download, CheckCircle2, AlertCircle, Loader2, ExternalLink, X } from 'lucide-react';

import type {
  OllamaHealthResponse,
  OllamaPullStatusResponse,
  OllamaRecommendedModel,
} from '../../../shared/types';
import {
  getOllamaHealth,
  getOllamaRecommendedModels,
  startOllamaPull,
  getOllamaPullStatus,
  cancelOllamaPull,
} from '../../lib/api';

interface OllamaQuickPullPanelProps {
  capability: string;
  canEdit: boolean;
  /** 下载完成后回调，给上层（profile 表单）自动写入 baseUrl + model */
  onModelReady: (modelName: string) => void;
}

function formatBytes(bytes: number): string {
  if (bytes <= 0) return '0 B';
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(0)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

export function OllamaQuickPullPanel({ capability, canEdit, onModelReady }: OllamaQuickPullPanelProps) {
  const [health, setHealth] = useState<OllamaHealthResponse | null>(null);
  const [recommended, setRecommended] = useState<OllamaRecommendedModel[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [pullStatus, setPullStatus] = useState<OllamaPullStatusResponse | null>(null);
  const [actionError, setActionError] = useState<string>('');
  const [actionMessage, setActionMessage] = useState<string>('');
  const completedRef = useRef<string>('');
  const pollTimerRef = useRef<number | null>(null);

  const refreshHealth = useCallback(async () => {
    try {
      const h = await getOllamaHealth();
      setHealth(h);
    } catch (error) {
      console.warn('[ollama] health failed', error);
    }
  }, []);

  const refreshRecommended = useCallback(async () => {
    try {
      const r = await getOllamaRecommendedModels(capability);
      setRecommended(r.models);
      // 默认选中带 default=true 的
      const def = r.models.find((m) => m.default);
      if (def) setSelectedModel((prev) => prev || def.name);
    } catch (error) {
      console.warn('[ollama] recommended failed', error);
    }
  }, [capability]);

  const refreshPullStatus = useCallback(async () => {
    try {
      const s = await getOllamaPullStatus();
      setPullStatus(s);
      // 下载完成 → 触发回调（一次）
      if (s.completed && s.modelName && completedRef.current !== s.modelName) {
        completedRef.current = s.modelName;
        onModelReady(s.modelName);
        setActionMessage(`✅ ${s.modelName} 已下载完成并自动填入下方配置`);
        await refreshHealth();
      }
    } catch (error) {
      console.warn('[ollama] pull status failed', error);
    }
  }, [onModelReady, refreshHealth]);

  useEffect(() => {
    void refreshHealth();
    void refreshRecommended();
    void refreshPullStatus();
  }, [refreshHealth, refreshRecommended, refreshPullStatus]);

  useEffect(() => {
    const inProgress = pullStatus?.inProgress;
    if (!inProgress) {
      if (pollTimerRef.current !== null) {
        window.clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      return;
    }
    pollTimerRef.current = window.setInterval(() => {
      void refreshPullStatus();
    }, 1000);
    return () => {
      if (pollTimerRef.current !== null) {
        window.clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [pullStatus?.inProgress, refreshPullStatus]);

  const installedNames = new Set((health?.installedModels || []).map((m) => m.name));

  const handlePull = async () => {
    if (!selectedModel) return;
    setActionError('');
    setActionMessage('');
    completedRef.current = '';
    try {
      const r = await startOllamaPull(selectedModel);
      if (!r.started) {
        setActionError(r.message || '启动拉取失败');
      } else {
        setActionMessage(r.message || `已开始拉取 ${selectedModel}`);
        void refreshPullStatus();
      }
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '请求失败');
    }
  };

  const handleCancel = async () => {
    try {
      await cancelOllamaPull();
      setActionMessage('已请求取消，下载即将停止');
      await refreshPullStatus();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '取消失败');
    }
  };

  const handleUseInstalled = (name: string) => {
    onModelReady(name);
    setActionMessage(`✅ 已选择已安装的 ${name}，并自动填入下方配置`);
  };

  if (!health) {
    return (
      <div className="rounded-2xl border border-gray-200 bg-gray-50 px-3 py-2 text-[11px] text-gray-500">
        正在读取 Ollama 状态…
      </div>
    );
  }

  if (!health.running) {
    return (
      <div className="space-y-2 rounded-2xl border border-amber-100 bg-amber-50 px-3 py-2.5 text-[11px] text-amber-800">
        <div className="flex items-start gap-2">
          <AlertCircle size={13} className="mt-0.5 shrink-0" />
          <div>
            <p className="font-bold">Ollama 未运行（{health.error || '无法连接 127.0.0.1:11434'}）</p>
            <p className="opacity-80 mt-0.5">本地大语言模型需要先安装 Ollama（一次性，免费开源，Mac 一键安装）。</p>
          </div>
        </div>
        <div className="flex gap-2">
          <a
            href="https://ollama.com/download"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 rounded-xl bg-amber-700 text-white px-3 py-1.5 text-[11px] font-bold hover:bg-amber-800"
          >
            <ExternalLink size={11} /> 去 ollama.com 下载安装
          </a>
          <button
            type="button"
            onClick={() => void refreshHealth()}
            className="inline-flex items-center gap-1 rounded-xl border border-amber-200 bg-white px-3 py-1.5 text-[11px] font-bold text-amber-700 hover:border-amber-300"
          >
            重新检测
          </button>
        </div>
      </div>
    );
  }

  const pullPercent = pullStatus && pullStatus.bytesTotal > 0
    ? Math.min(100, (pullStatus.bytesDownloaded / pullStatus.bytesTotal) * 100)
    : 0;

  return (
    <div className="space-y-2 rounded-2xl border border-blue-100 bg-blue-50/60 px-3 py-2.5 text-[11px]">
      <div className="flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1 font-bold text-blue-800">
          <CheckCircle2 size={11} className="text-emerald-600" />
          Ollama 运行中
          {health.version ? <span className="opacity-60 font-normal">v{health.version}</span> : null}
          <span className="opacity-60 font-normal">· {health.installedModels.length} 个已装模型</span>
        </span>
      </div>

      {/* 推荐模型 dropdown */}
      <div className="flex items-stretch gap-1.5">
        <select
          value={selectedModel}
          onChange={(e) => setSelectedModel(e.target.value)}
          disabled={!canEdit || pullStatus?.inProgress}
          className="flex-1 rounded-xl border border-gray-200 bg-white px-2.5 py-1.5 text-[11px] font-bold text-gray-900 outline-none focus:border-[#5B7BFE] disabled:opacity-50"
        >
          <option value="">— 选择推荐模型 —</option>
          {recommended.map((m) => {
            const isInstalled = installedNames.has(m.name);
            return (
              <option key={m.name} value={m.name}>
                {m.name} ({m.sizeGb.toFixed(1)}GB){isInstalled ? ' · 已安装 ✓' : ''} — {m.description}
              </option>
            );
          })}
        </select>
        {!pullStatus?.inProgress && (
          selectedModel && installedNames.has(selectedModel) ? (
            <button
              type="button"
              onClick={() => handleUseInstalled(selectedModel)}
              disabled={!canEdit}
              className="inline-flex items-center gap-1 rounded-xl bg-emerald-600 text-white px-3 py-1.5 text-[11px] font-bold hover:bg-emerald-700 disabled:opacity-50"
            >
              <CheckCircle2 size={11} /> 使用此模型
            </button>
          ) : (
            <button
              type="button"
              onClick={() => void handlePull()}
              disabled={!canEdit || !selectedModel}
              className="inline-flex items-center gap-1 rounded-xl bg-[#5B7BFE] text-white px-3 py-1.5 text-[11px] font-bold disabled:opacity-50"
            >
              <Download size={11} /> 下载模型
            </button>
          )
        )}
        {pullStatus?.inProgress && (
          <button
            type="button"
            onClick={() => void handleCancel()}
            className="inline-flex items-center gap-1 rounded-xl border border-rose-200 bg-white px-3 py-1.5 text-[11px] font-bold text-rose-600 hover:border-rose-300"
          >
            <X size={11} /> 取消
          </button>
        )}
      </div>

      {/* 进度条 */}
      {pullStatus?.inProgress && (
        <div className="space-y-1">
          <div className="h-1.5 rounded-full bg-blue-100 overflow-hidden">
            <div className="h-full bg-[#5B7BFE] transition-all" style={{ width: `${pullPercent}%` }} />
          </div>
          <div className="flex items-center justify-between text-[10px] text-blue-700">
            <span className="inline-flex items-center gap-1">
              <Loader2 size={9} className="animate-spin" />
              {pullStatus.modelName} · {pullStatus.status}
            </span>
            <span>
              {formatBytes(pullStatus.bytesDownloaded)} / {formatBytes(pullStatus.bytesTotal)}（{pullPercent.toFixed(1)}%）
            </span>
          </div>
        </div>
      )}

      {pullStatus?.error && !pullStatus.inProgress && (
        <p className="text-[10px] text-rose-600">{pullStatus.error}</p>
      )}
      {actionMessage && <p className="text-[10px] text-emerald-700">{actionMessage}</p>}
      {actionError && <p className="text-[10px] text-rose-600">{actionError}</p>}
    </div>
  );
}
