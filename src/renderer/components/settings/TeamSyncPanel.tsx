/**
 * V2.3 Step 5 · 团队同步状态面板
 *
 * 设计准则 (跟"任务归属" / "事实澄清" 统一):
 *  - 大号细字标题 + 12px 灰副 label
 *  - 中性灰骨架 + 蓝紫 #5B7BFE 强调
 *  - ghost outline 按钮 (border + 浅底 + hover 加深)
 *  - 实时拉 stats, 用户手动触发"立即同步"
 */
import { useCallback, useEffect, useState } from 'react';
import {
  Cloud,
  CloudOff,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  RefreshCw,
  Zap,
} from 'lucide-react';
import {
  getTeamSyncStats,
  enqueueTeamSyncAll,
  runTeamSyncOnce,
  type TeamSyncStats,
} from '../../lib/api';

interface TeamSyncPanelProps {
  flash?: (kind: 'success' | 'error' | 'info', message: string) => void;
}

export function TeamSyncPanel({ flash }: TeamSyncPanelProps) {
  const [stats, setStats] = useState<TeamSyncStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [enqueueing, setEnqueueing] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [lastSyncResult, setLastSyncResult] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const s = await getTeamSyncStats();
      setStats(s);
    } catch (err) {
      flash?.('error', `团队同步状态加载失败: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoading(false);
    }
  }, [flash]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleEnqueueAll = async () => {
    setEnqueueing(true);
    try {
      const r = await enqueueTeamSyncAll();
      flash?.('success', `已标记 ${r.inserted} 条新待同步项 (扫描 ${r.total_scanned})`);
      await refresh();
    } catch (err) {
      flash?.('error', `加入同步队列失败: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setEnqueueing(false);
    }
  };

  const handleSyncNow = async () => {
    setSyncing(true);
    setLastSyncResult(null);
    try {
      // 跑多批直到没 pending (或最多 20 批避免无限)
      let totalAccepted = 0;
      let totalDuplicates = 0;
      let totalRejected = 0;
      let totalCount = 0;
      for (let i = 0; i < 20; i += 1) {
        const r = await runTeamSyncOnce(100);
        if (r.status === 'no_pending') break;
        if (r.status !== 'ok') {
          flash?.('error', `同步失败: ${r.error || r.status}`);
          break;
        }
        totalAccepted += r.accepted || 0;
        totalDuplicates += r.duplicates || 0;
        totalRejected += r.rejected || 0;
        totalCount += r.count || 0;
        if ((r.count || 0) < 100) break;
      }
      setLastSyncResult(
        `本次推送 ${totalCount} 条 · 新增 ${totalAccepted} · 云端已存在 ${totalDuplicates} · 拒绝 ${totalRejected}`,
      );
      flash?.('success', `同步完成: 推送 ${totalCount} 条`);
      await refresh();
    } catch (err) {
      flash?.('error', `同步异常: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setSyncing(false);
    }
  };

  const pending = stats?.pending ?? 0;
  const synced = stats?.synced ?? 0;
  const failed = stats?.failed ?? 0;
  const total = stats?.total ?? 0;
  const syncRate = total > 0 ? Math.round((synced / total) * 100) : 0;

  return (
    <section className="rounded-xl border border-gray-100 bg-white px-6 py-5">
      {/* Header */}
      <header className="mb-5 flex items-end justify-between gap-6">
        <div>
          <h3 className="text-[18px] font-light tracking-tight text-gray-900 flex items-center gap-2">
            <Cloud size={18} className="text-[#5B7BFE]" strokeWidth={1.5} />
            团队同步
          </h3>
          <p className="mt-1 text-[12px] text-gray-400 leading-relaxed">
            把本地解析的文档同步到云端, 让团队其他成员可以复用同份解析结果
          </p>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={loading}
          className="inline-flex items-center gap-1 text-[11px] text-gray-400 hover:text-gray-700 transition-colors disabled:opacity-50"
        >
          <RefreshCw size={11} className={loading ? 'animate-spin' : ''} strokeWidth={2} />
          刷新
        </button>
      </header>

      {/* Stats Grid */}
      <div className="grid grid-cols-4 gap-3 mb-5">
        <div className="rounded-lg border border-gray-100 bg-gray-50/40 px-4 py-3">
          <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">总计</div>
          <div className="mt-1 text-[22px] font-light tabular-nums text-gray-900">{total}</div>
        </div>
        <div className="rounded-lg border border-emerald-100 bg-emerald-50/40 px-4 py-3">
          <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-emerald-700 flex items-center gap-1">
            <CheckCircle2 size={10} strokeWidth={2} />
            已同步
          </div>
          <div className="mt-1 text-[22px] font-light tabular-nums text-emerald-700">{synced}</div>
          {total > 0 && (
            <div className="text-[10px] text-gray-400 mt-0.5">{syncRate}%</div>
          )}
        </div>
        <div className={`rounded-lg border px-4 py-3 ${
          pending > 0 ? 'border-amber-100 bg-amber-50/40' : 'border-gray-100 bg-gray-50/40'
        }`}>
          <div className={`text-[10px] font-bold uppercase tracking-[0.18em] flex items-center gap-1 ${
            pending > 0 ? 'text-amber-700' : 'text-gray-400'
          }`}>
            <CloudOff size={10} strokeWidth={2} />
            待同步
          </div>
          <div className={`mt-1 text-[22px] font-light tabular-nums ${
            pending > 0 ? 'text-amber-700' : 'text-gray-400'
          }`}>{pending}</div>
        </div>
        <div className={`rounded-lg border px-4 py-3 ${
          failed > 0 ? 'border-rose-100 bg-rose-50/40' : 'border-gray-100 bg-gray-50/40'
        }`}>
          <div className={`text-[10px] font-bold uppercase tracking-[0.18em] flex items-center gap-1 ${
            failed > 0 ? 'text-rose-700' : 'text-gray-400'
          }`}>
            <AlertTriangle size={10} strokeWidth={2} />
            失败
          </div>
          <div className={`mt-1 text-[22px] font-light tabular-nums ${
            failed > 0 ? 'text-rose-700' : 'text-gray-400'
          }`}>{failed}</div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 flex-wrap">
        <button
          type="button"
          onClick={() => void handleSyncNow()}
          disabled={syncing || pending === 0}
          title={pending === 0 ? '没有待同步项, 先点"加入同步队列"或导入新文件' : '立即推送所有 pending 到云端'}
          className="inline-flex items-center gap-1.5 rounded-md border border-[#5B7BFE]/30 bg-[#5B7BFE]/5 px-3 py-1.5 text-[12px] font-medium text-[#5B7BFE] transition-colors hover:bg-[#5B7BFE]/10 hover:border-[#5B7BFE]/50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {syncing ? (
            <Loader2 size={13} className="animate-spin" strokeWidth={2} />
          ) : (
            <Zap size={13} strokeWidth={2} />
          )}
          立即同步
          {pending > 0 && (
            <span className="rounded-full bg-white px-1.5 py-px text-[10px] font-semibold tabular-nums">
              {pending}
            </span>
          )}
        </button>

        <button
          type="button"
          onClick={() => void handleEnqueueAll()}
          disabled={enqueueing}
          title="扫描所有 source_registry, 把没标记过的加入待同步队列 (一般不用点, 自动扫描)"
          className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-3 py-1.5 text-[12px] font-medium text-gray-600 transition-colors hover:border-gray-300 hover:bg-gray-50 disabled:opacity-50"
        >
          {enqueueing ? (
            <Loader2 size={13} className="animate-spin" strokeWidth={2} />
          ) : (
            <RefreshCw size={13} strokeWidth={2} />
          )}
          扫描新文件入队
        </button>

        {lastSyncResult && (
          <p className="ml-3 text-[11px] text-gray-400">{lastSyncResult}</p>
        )}
      </div>

      {/* Footer hint */}
      <div className="mt-4 pt-4 border-t border-gray-100">
        <p className="text-[11px] text-gray-400 leading-relaxed">
          <span className="font-medium text-gray-500">工作原理 · </span>
          本机导入或解析的文档自动登记到 source_registry, 你点"立即同步"会按 (org_id, content_hash) 推到云端 team_documents 表.
          云端按 hash 去重, 同事在他机器导同一份文件时云端已存在不会重复解析.
        </p>
      </div>
    </section>
  );
}
