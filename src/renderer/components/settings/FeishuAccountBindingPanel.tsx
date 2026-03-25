import React, { useEffect, useState } from 'react';
import { Copy, ExternalLink, Link2, QrCode, RefreshCw, ShieldAlert, ShieldCheck, Unplug, X } from 'lucide-react';

import type { FeishuUserBinding } from '../../../shared/types';

type BusyAction = 'idle' | 'starting' | 'refreshing' | 'clearing';

export type FeishuBindingFlowState = {
  authorizeUrl: string;
  callbackUrl: string;
  expiresAt: string;
  qrReady: boolean;
  qrBlockedReason?: string | null;
  qrCodeDataUrl?: string | null;
  statusMessage?: string;
  isPolling?: boolean;
};

type Props = {
  binding: FeishuUserBinding;
  busyAction: BusyAction;
  currentUserName?: string | null;
  pendingAuthorization?: FeishuBindingFlowState | null;
  onStartBinding: () => Promise<void>;
  onRefresh: () => Promise<void>;
  onClearBinding: () => Promise<void>;
  onOpenBindingInBrowser: () => Promise<void>;
  onClosePendingAuthorization: () => void;
};

function statusTone(binding: FeishuUserBinding) {
  if (binding.linked) return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  if (!binding.readyForAuthorization) return 'border-amber-100 bg-amber-50 text-amber-700';
  return 'border-slate-100 bg-slate-50 text-slate-600';
}

export function FeishuAccountBindingPanel({
  binding,
  busyAction,
  currentUserName,
  pendingAuthorization,
  onStartBinding,
  onRefresh,
  onClearBinding,
  onOpenBindingInBrowser,
  onClosePendingAuthorization,
}: Props) {
  const isBusy = busyAction !== 'idle';
  const canShowQr = Boolean(pendingAuthorization?.qrReady && pendingAuthorization?.qrCodeDataUrl);
  const [copyStatus, setCopyStatus] = useState<'idle' | 'copied' | 'failed'>('idle');

  useEffect(() => {
    setCopyStatus('idle');
  }, [pendingAuthorization?.authorizeUrl]);

  const handleCopyAuthorizeUrl = async () => {
    if (!pendingAuthorization?.authorizeUrl) return;
    try {
      await navigator.clipboard.writeText(pendingAuthorization.authorizeUrl);
      setCopyStatus('copied');
      window.setTimeout(() => setCopyStatus('idle'), 1800);
    } catch {
      setCopyStatus('failed');
      window.setTimeout(() => setCopyStatus('idle'), 1800);
    }
  };

  return (
    <>
      <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm space-y-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-[16px] font-bold text-gray-900 flex items-center gap-2">
              <Link2 size={17} />
              飞书账号绑定
            </h2>
            <p className="text-[12px] text-gray-500 mt-1 leading-relaxed">
              当前登录用户先绑定自己的飞书身份，任务与日历里发起飞书会议时，系统会优先按你的绑定账号发送。
            </p>
          </div>
          <div className={`text-[11px] font-bold px-3 py-1.5 rounded-full border ${statusTone(binding)}`}>
            {binding.linked ? '已绑定个人飞书' : binding.readyForAuthorization ? '待绑定' : '缺少飞书授权底座'}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-2xl bg-slate-50 border border-slate-200 p-4">
            <p className="text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-2">当前登录用户</p>
            <p className="text-[13px] font-bold text-slate-900">{currentUserName || binding.userId || '未识别'}</p>
            <p className="text-[12px] text-slate-600 mt-1 break-all">{binding.userId || '尚未加载用户 ID'}</p>
          </div>
          <div className="rounded-2xl bg-slate-50 border border-slate-200 p-4">
            <p className="text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-2">飞书应用</p>
            <p className="text-[13px] font-bold text-slate-900">{binding.appId || '尚未配置 App ID'}</p>
            <p className="text-[12px] text-slate-600 mt-1">
              {binding.linked
                ? `最近校验：${binding.lastVerifiedAt || binding.boundAt || '刚刚'}`
                : binding.readyForAuthorization
                  ? '当前已经具备授权条件'
                  : '需要管理员先配置飞书 App ID、App Secret 和机器人基础设置'}
            </p>
          </div>
        </div>

        {binding.linked ? (
          <div className="rounded-2xl border border-emerald-100 bg-emerald-50/70 px-4 py-4 text-[12px] text-emerald-800 space-y-2">
            <div className="flex items-center gap-2 font-bold">
              <ShieldCheck size={14} />
              已绑定飞书身份
            </div>
            <p>显示名称：{binding.name || binding.enName || '未返回姓名'}</p>
            <p>飞书邮箱：{binding.email || '飞书未返回邮箱'}</p>
            <p className="break-all">open_id：{binding.openId || '未返回 open_id'}</p>
          </div>
        ) : (
          <div className={`rounded-2xl border px-4 py-4 text-[12px] leading-relaxed ${binding.readyForAuthorization ? 'border-blue-100 bg-blue-50/70 text-slate-700' : 'border-amber-100 bg-amber-50 text-amber-800'}`}>
            <div className="flex items-center gap-2 font-bold mb-2">
              {binding.readyForAuthorization ? <QrCode size={14} /> : <ShieldAlert size={14} />}
              {binding.readyForAuthorization ? '还没有绑定个人飞书账号' : '当前还不能发起个人飞书绑定'}
            </div>
            <p>
              {binding.readyForAuthorization
                ? '点击“绑定飞书账号”后会弹出二维码/授权面板。系统会优先尝试使用云端 HTTPS 中继让手机扫码完成授权；如果当前环境还没有公网入口，仍可在当前电脑浏览器完成授权。'
                : '请先让管理员在“飞书单机器人”里配置飞书 App ID、App Secret；如果需要自定义回调地址，也可以单独配置个人绑定回调 URL。'}
            </p>
            {binding.lastError ? <p className="mt-2 text-rose-700">最近错误：{binding.lastError}</p> : null}
          </div>
        )}

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="inline-flex items-center gap-2 px-4 py-3 rounded-2xl bg-[#335CFF] text-white text-[13px] font-bold disabled:opacity-50"
            onClick={() => void onStartBinding()}
            disabled={!binding.readyForAuthorization || isBusy}
          >
            {busyAction === 'starting' ? <RefreshCw size={16} className="animate-spin" /> : <QrCode size={16} />}
            {binding.linked ? '重新绑定飞书账号' : '绑定飞书账号'}
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-2 px-4 py-3 rounded-2xl bg-white border border-gray-200 text-[13px] font-bold text-gray-700 disabled:opacity-50"
            onClick={() => void onRefresh()}
            disabled={isBusy}
          >
            {busyAction === 'refreshing' ? <RefreshCw size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            刷新绑定状态
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-2 px-4 py-3 rounded-2xl bg-white border border-gray-200 text-[13px] font-bold text-gray-700 disabled:opacity-50"
            onClick={() => void onClearBinding()}
            disabled={!binding.linked || isBusy}
          >
            {busyAction === 'clearing' ? <RefreshCw size={16} className="animate-spin" /> : <Unplug size={16} />}
            解除绑定
          </button>
        </div>
      </div>

      {pendingAuthorization ? (
        <div className="fixed inset-0 z-50 bg-slate-950/35 backdrop-blur-sm flex items-center justify-center p-5">
          <div className="w-full max-w-4xl bg-white rounded-[28px] shadow-[0_24px_80px_rgba(15,23,42,0.18)] border border-slate-100 overflow-hidden" onClick={(event) => event.stopPropagation()}>
            <div className="flex items-center gap-4 px-6 py-5 border-b border-slate-100">
              <button type="button" className="w-10 h-10 shrink-0 rounded-2xl border border-slate-200 text-slate-500 hover:text-slate-800 hover:bg-slate-50 flex items-center justify-center" onClick={onClosePendingAuthorization} aria-label="关闭飞书授权绑定">
                <X size={16} />
              </button>
              <div className="flex-1">
                <h3 className="text-[18px] font-bold text-slate-900">飞书授权绑定</h3>
                <p className="text-[12px] text-slate-500 mt-1">授权完成后，工作台会自动刷新个人绑定状态。</p>
              </div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-[280px_minmax(0,1fr)] gap-6 px-6 py-6">
              <div className="rounded-[24px] border border-slate-100 bg-slate-50 p-5 flex flex-col items-center justify-center text-center min-h-[320px]">
                {canShowQr ? (
                  <>
                    <div className="w-[232px] h-[232px] rounded-[24px] bg-white border border-slate-200 shadow-sm flex items-center justify-center overflow-hidden">
                      <img src={pendingAuthorization.qrCodeDataUrl || undefined} alt="飞书绑定二维码" className="w-[208px] h-[208px]" />
                    </div>
                    <p className="mt-4 text-[13px] font-bold text-slate-900">请用飞书扫码完成授权</p>
                    <p className="mt-2 text-[12px] leading-6 text-slate-500">扫码后在飞书里确认授权，工作台会自动刷新绑定结果。</p>
                  </>
                ) : (
                  <>
                    <div className="w-14 h-14 rounded-2xl bg-amber-50 border border-amber-100 flex items-center justify-center text-amber-500">
                      <ShieldAlert size={24} />
                    </div>
                    <p className="mt-4 text-[13px] font-bold text-slate-900">当前还不能用手机扫码完成绑定</p>
                    <p className="mt-2 text-[12px] leading-6 text-slate-500">{pendingAuthorization.qrBlockedReason || '当前授权回调仍指向本机地址。'}</p>
                  </>
                )}
              </div>

              <div className="space-y-4">
                <div className="rounded-[24px] border border-slate-100 bg-white p-5">
                  <p className="text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-2">当前回调地址</p>
                  <p className="text-[13px] font-semibold text-slate-900 break-all">{pendingAuthorization.callbackUrl}</p>
                  <p className="text-[12px] text-slate-500 mt-2 leading-6">
                    手机扫码能否直接完成绑定，取决于这里是否是飞书后台允许的公网 HTTPS 回调地址。系统会优先走云端 HTTPS 中继；如果当前仍是本机地址，就只能在这台电脑浏览器继续授权。
                  </p>
                </div>

                <div className="rounded-[24px] border border-slate-100 bg-slate-50 p-5">
                  <p className="text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-2">当前状态</p>
                  <p className="text-[13px] font-semibold text-slate-900">{pendingAuthorization.statusMessage || '等待授权中'}</p>
                  <p className="text-[12px] text-slate-500 mt-2">
                    {pendingAuthorization.isPolling ? '工作台正在后台轮询绑定结果。' : `本次授权有效期到 ${pendingAuthorization.expiresAt.replace('T', ' ')}`}
                  </p>
                </div>

                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    className="inline-flex items-center gap-2 px-4 py-3 rounded-2xl bg-[#335CFF] text-white text-[13px] font-bold disabled:opacity-50"
                    onClick={() => void onOpenBindingInBrowser()}
                  >
                    <ExternalLink size={16} />
                    在浏览器中继续授权
                  </button>
                  <button
                    type="button"
                    className="inline-flex items-center gap-2 px-4 py-3 rounded-2xl bg-white border border-slate-200 text-[13px] font-bold text-slate-700"
                    onClick={() => void handleCopyAuthorizeUrl()}
                  >
                    <Copy size={16} />
                    {copyStatus === 'copied' ? '授权链接已复制' : copyStatus === 'failed' ? '复制失败' : '复制授权链接'}
                  </button>
                  <button
                    type="button"
                    className="inline-flex items-center gap-2 px-4 py-3 rounded-2xl bg-white border border-slate-200 text-[13px] font-bold text-slate-700"
                    onClick={() => void onRefresh()}
                  >
                    <RefreshCw size={16} />
                    手动刷新绑定状态
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
