import React, { useEffect, useMemo, useState } from 'react';
import { Check, Copy, Phone, ShieldCheck } from 'lucide-react';

import {
  buildMobilePairingLink,
  hasCurrentMobilePairingQrError,
  normalizeMobilePairingEndpoint,
  resolveCurrentMobilePairingQrDataUrl,
  type MobilePairingQrResult,
} from '../../../shared/mobilePairingLink';

type MobilePairingCardProps = {
  endpoint?: string | null;
  email?: string | null;
  workspace?: string | null;
  cloudInstanceId?: string | null;
  organizationId?: string | null;
};

export function MobilePairingCard({ endpoint, email, workspace, cloudInstanceId, organizationId }: MobilePairingCardProps) {
  const pairingLink = useMemo(
    () => buildMobilePairingLink({ endpoint, email, workspace, cloudInstanceId, organizationId }),
    [cloudInstanceId, email, endpoint, organizationId, workspace],
  );
  const normalizedEndpoint = useMemo(() => normalizeMobilePairingEndpoint(endpoint), [endpoint]);
  const [qrCodeResult, setQrCodeResult] = useState<MobilePairingQrResult | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setQrCodeResult(null);
    if (!pairingLink) return () => { cancelled = true; };

    void import('qrcode')
      .then((qrcode) => qrcode.toDataURL(pairingLink, { width: 224, margin: 1, errorCorrectionLevel: 'M' }))
      .then((dataUrl) => {
        if (!cancelled) setQrCodeResult({ sourceLink: pairingLink, status: 'ready', dataUrl });
      })
      .catch(() => {
        if (!cancelled) setQrCodeResult({ sourceLink: pairingLink, status: 'error' });
      });

    return () => { cancelled = true; };
  }, [pairingLink]);

  useEffect(() => {
    if (!copied) return undefined;
    const timer = window.setTimeout(() => setCopied(false), 1800);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const qrCodeDataUrl = resolveCurrentMobilePairingQrDataUrl(qrCodeResult, pairingLink);
  const qrCodeError = hasCurrentMobilePairingQrError(qrCodeResult, pairingLink);

  const handleCopy = async () => {
    if (!pairingLink) return;
    try {
      await navigator.clipboard.writeText(pairingLink);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  if (!pairingLink) {
    return (
      <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50/70 px-5 py-6">
        <div className="flex items-start gap-3">
          <Phone size={18} className="mt-0.5 shrink-0 text-gray-400" />
          <div>
            <p className="text-[13px] font-semibold text-gray-900">当前工作空间暂不能添加到手机</p>
            <p className="mt-1.5 text-[12px] leading-5 text-gray-500">
              请先在电脑端登录云端账号，并确认当前活动工作空间已经配置云地址和账号邮箱。
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-[1fr_224px] md:items-start">
      <div className="min-w-0 space-y-4">
        <div className="rounded-2xl border border-blue-100 bg-blue-50/60 px-4 py-3.5">
          <div className="flex items-start gap-3">
            <Phone size={18} className="mt-0.5 shrink-0 text-[#5B7BFE]" />
            <div>
              <p className="text-[13px] font-semibold text-gray-900">用手机应用内的扫码入口添加</p>
              <p className="mt-1 text-[12px] leading-5 text-gray-600">
                打开手机登录页的「从电脑扫码添加」。扫码只会预填星丛官方云地址和账号，仍需在手机上确认、检测并输入密码。
              </p>
            </div>
          </div>
        </div>

        <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="rounded-xl border border-gray-100 bg-white px-3 py-2.5 sm:col-span-2">
            <dt className="text-[10px] font-bold uppercase tracking-[0.14em] text-gray-400">当前云地址</dt>
            <dd className="mt-1 break-all text-[12px] font-medium text-gray-800">{normalizedEndpoint}</dd>
          </div>
          <div className="rounded-xl border border-gray-100 bg-white px-3 py-2.5">
            <dt className="text-[10px] font-bold uppercase tracking-[0.14em] text-gray-400">当前账号</dt>
            <dd className="mt-1 truncate text-[12px] font-medium text-gray-800" title={String(email || '')}>{email}</dd>
          </div>
          <div className="rounded-xl border border-gray-100 bg-white px-3 py-2.5">
            <dt className="text-[10px] font-bold uppercase tracking-[0.14em] text-gray-400">工作空间</dt>
            <dd className="mt-1 truncate text-[12px] font-medium text-gray-800" title={String(workspace || '')}>{workspace}</dd>
          </div>
        </dl>

        <button
          type="button"
          onClick={() => { void handleCopy(); }}
          className="inline-flex items-center gap-2 rounded-xl bg-[#5B7BFE] px-4 py-2.5 text-[12px] font-semibold text-white transition-colors hover:bg-[#4968e8] focus:outline-none focus:ring-2 focus:ring-blue-200"
        >
          {copied ? <Check size={15} /> : <Copy size={15} />}
          {copied ? '已复制二维码内容' : '复制二维码内容'}
        </button>

        <div className="flex items-start gap-2 text-[11px] leading-5 text-gray-500">
          <ShieldCheck size={15} className="mt-0.5 shrink-0 text-emerald-600" />
          <span>二维码地址固定为星丛官方云 HTTPS；内容只含账号邮箱、工作空间名称及非敏感的云实例/组织标识，不含 endpoint 参数、密码、登录令牌、邀请码或 AI/API 密钥。</span>
        </div>
      </div>

      <div className="flex min-h-[224px] items-center justify-center rounded-2xl border border-gray-100 bg-white p-2 shadow-sm">
        {qrCodeDataUrl ? (
          <img src={qrCodeDataUrl} alt="手机端添加当前工作空间二维码" width={208} height={208} className="h-[208px] w-[208px]" />
        ) : qrCodeError ? (
          <p className="px-4 text-center text-[11px] leading-5 text-gray-400">二维码生成失败，请稍后重试；复制按钮仅复制同一二维码内容。</p>
        ) : (
          <div className="h-8 w-8 animate-pulse rounded-lg bg-gray-100" aria-label="正在生成二维码" />
        )}
      </div>
    </div>
  );
}
