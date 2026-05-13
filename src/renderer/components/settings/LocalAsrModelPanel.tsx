import { useCallback, useEffect, useRef, useState } from 'react';
import { Download, CheckCircle2, AlertCircle, Loader2, Trash2, PlayCircle } from 'lucide-react';

import type { LocalAsrModelStatus } from '../../../shared/types';
import {
  getLocalAsrModelStatus,
  startLocalAsrModelDownload,
  cancelLocalAsrModelDownload,
} from '../../lib/api';

interface LocalAsrModelPanelProps {
  canEdit: boolean;
}

function formatBytes(bytes: number): string {
  if (bytes <= 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function formatSpeed(bytesPerSec: number): string {
  return `${formatBytes(Math.max(0, Math.round(bytesPerSec)))}/s`;
}

export function LocalAsrModelPanel({ canEdit }: LocalAsrModelPanelProps) {
  const [status, setStatus] = useState<LocalAsrModelStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState<string>('');
  const [actionError, setActionError] = useState<string>('');
  const pollTimerRef = useRef<number | null>(null);
  const lastBytesRef = useRef<number>(0);
  const lastBytesTimeRef = useRef<number>(0);
  const [instantSpeed, setInstantSpeed] = useState<number>(0);

  const refresh = useCallback(async () => {
    try {
      const next = await getLocalAsrModelStatus();
      setStatus(next);
      // 估算瞬时下载速度
      if (next.downloadInProgress) {
        const now = Date.now();
        const elapsedMs = now - lastBytesTimeRef.current;
        if (elapsedMs > 0 && lastBytesRef.current > 0) {
          const delta = next.downloadBytesDownloaded - lastBytesRef.current;
          if (delta > 0) {
            setInstantSpeed((delta * 1000) / elapsedMs);
          }
        }
        lastBytesRef.current = next.downloadBytesDownloaded;
        lastBytesTimeRef.current = now;
      } else {
        setInstantSpeed(0);
      }
    } catch (error) {
      console.warn('[local-asr] status fetch failed', error);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // 下载进行中时每秒轮询
  useEffect(() => {
    const shouldPoll = status?.downloadInProgress;
    if (!shouldPoll) {
      if (pollTimerRef.current !== null) {
        window.clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      return;
    }
    pollTimerRef.current = window.setInterval(() => {
      void refresh();
    }, 1000);
    return () => {
      if (pollTimerRef.current !== null) {
        window.clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [status?.downloadInProgress, refresh]);

  const handleStartDownload = async () => {
    setLoading(true);
    setActionError('');
    setActionMessage('');
    try {
      lastBytesRef.current = 0;
      lastBytesTimeRef.current = Date.now();
      const result = await startLocalAsrModelDownload(true);
      setActionMessage(result.message || '已开始下载');
      void refresh();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '启动下载失败');
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async () => {
    setLoading(true);
    try {
      const result = await cancelLocalAsrModelDownload();
      setActionMessage(result.cancelled ? '已请求取消，即将停止下载' : '当前无下载任务可取消');
      void refresh();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '取消失败');
    } finally {
      setLoading(false);
    }
  };

  if (!status) {
    return (
      <div className="rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[12px] text-gray-500">
        正在读取本地 ASR 模型状态…
      </div>
    );
  }

  const downloadPercent = status.downloadBytesTotal > 0
    ? Math.min(100, (status.downloadBytesDownloaded / status.downloadBytesTotal) * 100)
    : 0;

  return (
    <div className="space-y-3 rounded-2xl border border-blue-100 bg-blue-50/60 px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[12px] text-gray-600">
            SenseVoice-Small（达摩院 · 中文场景准确率最强 · 完全离线 · ~240MB）
          </p>
        </div>
        {status.installed ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-100 px-2.5 py-1 text-[11px] font-bold text-emerald-700">
            <CheckCircle2 size={12} /> 已就绪 · {formatBytes(status.sizeBytes)}
          </span>
        ) : status.downloadInProgress ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 border border-blue-100 px-2.5 py-1 text-[11px] font-bold text-blue-700">
            <Loader2 size={12} className="animate-spin" /> 下载中
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-100 px-2.5 py-1 text-[11px] font-bold text-amber-700">
            <AlertCircle size={12} /> 模型未下载（约 240MB）
          </span>
        )}
      </div>

      {status.downloadInProgress && (
        <div className="space-y-1.5">
          <div className="h-2 rounded-full bg-blue-100 overflow-hidden">
            <div
              className="h-full bg-[#5B7BFE] transition-all"
              style={{ width: `${downloadPercent}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-[11px] text-gray-600">
            <span>
              {formatBytes(status.downloadBytesDownloaded)} / {formatBytes(status.downloadBytesTotal)}
              （{downloadPercent.toFixed(1)}%）
            </span>
            <span>
              {instantSpeed > 0 ? formatSpeed(instantSpeed) : '—'}
              {status.downloadCurrentFile ? ` · ${status.downloadCurrentFile}` : ''}
            </span>
          </div>
        </div>
      )}

      {status.downloadError && !status.downloadInProgress && (
        <div className="flex items-start gap-2 rounded-xl border border-rose-100 bg-rose-50 px-3 py-2 text-[11px] text-rose-700">
          <AlertCircle size={12} className="mt-0.5 shrink-0" />
          <span>{status.downloadError}</span>
        </div>
      )}

      {actionMessage && !status.downloadError && (
        <p className="text-[11px] text-gray-500">{actionMessage}</p>
      )}
      {actionError && <p className="text-[11px] text-rose-600">{actionError}</p>}

      <div className="flex items-center gap-2 pt-1">
        {!status.installed && !status.downloadInProgress && (
          <button
            type="button"
            onClick={() => void handleStartDownload()}
            disabled={!canEdit || loading}
            className="inline-flex items-center gap-1.5 rounded-2xl bg-[#5B7BFE] px-4 py-2 text-[12px] font-bold text-white shadow-[0_4px_12px_rgba(91,123,254,0.18)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download size={13} /> 立即下载模型（约 240MB）
          </button>
        )}
        {status.downloadInProgress && (
          <button
            type="button"
            onClick={() => void handleCancel()}
            disabled={!canEdit || loading}
            className="inline-flex items-center gap-1.5 rounded-2xl border border-gray-200 bg-white px-4 py-2 text-[12px] font-bold text-gray-700 hover:border-rose-200 hover:text-rose-600 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Trash2 size={13} /> 取消下载
          </button>
        )}
        {status.installed && (
          <>
            <span className="inline-flex items-center gap-1 text-[11px] text-emerald-700">
              <PlayCircle size={12} /> 模型已就绪，客户工作台可以上传录音转文字了
            </span>
          </>
        )}
      </div>
    </div>
  );
}
