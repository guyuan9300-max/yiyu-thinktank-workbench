import React, { useEffect, useState } from 'react';
import {
  Bot,
  CheckCircle2,
  Copy,
  ExternalLink,
  Link2,
  QrCode,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Unplug,
  Users,
  X,
} from 'lucide-react';

import type {
  FeishuMemberAuthorization,
  FeishuMemberAuthorizationStartResult,
  LocalInputMemoryFeishuIntegration,
  OrgFeishuIntegration,
  OrgFeishuIntegrationPayload,
  OrgMembershipSummary,
} from '../../../shared/types';

type BusyAction = 'idle' | 'starting' | 'refreshing' | 'clearing';

export type FeishuAuthorizationFlowState = FeishuMemberAuthorizationStartResult & {
  qrCodeDataUrl?: string | null;
  statusMessage?: string;
  isPolling?: boolean;
};

type Props = {
  sessionMode: 'local' | 'cloud';
  membership: OrgMembershipSummary;
  integration: OrgFeishuIntegration;
  authorization: FeishuMemberAuthorization;
  currentUserName?: string | null;
  saveBusy: boolean;
  busyAction: BusyAction;
  pendingAuthorization?: FeishuAuthorizationFlowState | null;
  rememberedInputs: LocalInputMemoryFeishuIntegration;
  onSaveIntegration: (payload: OrgFeishuIntegrationPayload) => Promise<void>;
  onSaveRememberedInputs: (payload: LocalInputMemoryFeishuIntegration) => Promise<void>;
  onStartAuthorization: () => Promise<void>;
  onRefreshAuthorization: () => Promise<void>;
  onClearAuthorization: () => Promise<void>;
  onOpenAuthorizationInBrowser: () => Promise<void>;
  onClosePendingAuthorization: () => void;
  onOpenOrganizationSetup: () => void;
  onOpenCloudAuth: () => void;
};

export function FeishuOrgIntegrationPanel({
  sessionMode,
  membership,
  integration,
  authorization,
  currentUserName,
  saveBusy,
  busyAction,
  pendingAuthorization,
  rememberedInputs,
  onSaveIntegration,
  onSaveRememberedInputs,
  onStartAuthorization,
  onRefreshAuthorization,
  onClearAuthorization,
  onOpenAuthorizationInBrowser,
  onClosePendingAuthorization,
  onOpenOrganizationSetup,
  onOpenCloudAuth,
}: Props) {
  const [appId, setAppId] = useState(integration.appId || rememberedInputs.appId || '');
  const [callbackMode, setCallbackMode] = useState<'cloud_relay' | 'custom'>(integration.callbackMode || rememberedInputs.callbackMode || 'cloud_relay');
  const [customCallbackUrl, setCustomCallbackUrl] = useState(integration.customCallbackUrl || rememberedInputs.customCallbackUrl || '');
  const [appSecret, setAppSecret] = useState(rememberedInputs.appSecret || '');
  const [rememberLocalInputs, setRememberLocalInputs] = useState(rememberedInputs.rememberInputs);
  const [showConfigEditor, setShowConfigEditor] = useState(false);
  const [copyStatus, setCopyStatus] = useState<'idle' | 'copied' | 'failed'>('idle');

  useEffect(() => {
    setAppId(integration.appId || rememberedInputs.appId || '');
    setCallbackMode(integration.callbackMode || rememberedInputs.callbackMode || 'cloud_relay');
    setCustomCallbackUrl(integration.customCallbackUrl || rememberedInputs.customCallbackUrl || '');
    setAppSecret(rememberedInputs.appSecret || '');
    setRememberLocalInputs(rememberedInputs.rememberInputs);
  }, [
    integration.appId,
    integration.callbackMode,
    integration.customCallbackUrl,
    rememberedInputs.appId,
    rememberedInputs.callbackMode,
    rememberedInputs.customCallbackUrl,
    rememberedInputs.appSecret,
    rememberedInputs.rememberInputs,
  ]);

  useEffect(() => {
    setCopyStatus('idle');
  }, [pendingAuthorization?.authorizeUrl]);

  const isBusy = busyAction !== 'idle';
  const canShowQr = Boolean(pendingAuthorization?.qrReady && pendingAuthorization?.qrCodeDataUrl);
  const hasPendingAuthorization = Boolean(pendingAuthorization);
  const hasChanges =
    appId.trim() !== (integration.appId || '')
    || callbackMode !== (integration.callbackMode || 'cloud_relay')
    || customCallbackUrl.trim() !== (integration.customCallbackUrl || '')
    || Boolean(appSecret.trim());

  const handleSave = async () => {
    const payload = {
      appId: appId.trim(),
      callbackMode,
      customCallbackUrl: callbackMode === 'custom' ? customCallbackUrl.trim() : '',
      appSecret: appSecret.trim() || undefined,
    };
    await onSaveIntegration(payload);
    await onSaveRememberedInputs({
      rememberInputs: rememberLocalInputs,
      appId: payload.appId,
      callbackMode: payload.callbackMode,
      customCallbackUrl: payload.customCallbackUrl,
      appSecret: payload.appSecret || '',
    });
    if (!rememberLocalInputs) {
      setAppSecret('');
    }
    setShowConfigEditor(false);
  };

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

  const renderAuditList = () => (
    integration.recentAudits?.length ? (
      <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-4">
        <p className="text-[12px] font-bold text-slate-900 mb-3">最近验证记录</p>
        <div className="space-y-3">
          {integration.recentAudits.slice(0, 4).map((item) => (
            <div key={item.id} className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-[12px] font-bold text-slate-900">
                  {item.validationStatus === 'success' ? '验证通过' : '验证失败'}
                </p>
                <span className="text-[11px] text-slate-400">{item.createdAt}</span>
              </div>
              <p className="text-[12px] text-slate-600 mt-2 leading-6">{item.validationMessage}</p>
              <p className="text-[11px] text-slate-400 mt-2">
                {item.actorName || item.actorUserId || '未知成员'} · {item.callbackMode === 'custom' ? '自定义回调' : '云端中继回调'}
              </p>
            </div>
          ))}
        </div>
      </div>
    ) : null
  );

  const renderIntegrationEditor = () => (
    <div className="rounded-3xl border border-slate-100 bg-white p-6 shadow-sm space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[16px] font-bold text-gray-900 flex items-center gap-2">
            <Bot size={17} />
            组织飞书接入
          </h2>
          <p className="text-[12px] text-gray-500 mt-1 leading-relaxed">
            这一步配置的是整个组织共用的飞书应用。保存前系统会先验证参数，只有验证通过才会生效。
          </p>
        </div>
        <div className={`text-[11px] font-bold px-3 py-1.5 rounded-full border ${
          integration.lastValidationStatus === 'success'
            ? 'border-emerald-100 bg-emerald-50 text-emerald-700'
            : integration.lastValidationStatus === 'failed'
              ? 'border-rose-100 bg-rose-50 text-rose-700'
              : 'border-slate-100 bg-slate-50 text-slate-600'
        }`}>
          {integration.enabled ? '组织已接通飞书' : '组织尚未接通飞书'}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <input
          value={appId}
          onChange={(event) => setAppId(event.target.value)}
          placeholder="飞书 App ID"
          className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none"
        />
        <input
          type="password"
          value={appSecret}
          onChange={(event) => setAppSecret(event.target.value)}
          placeholder={integration.hasAppSecret ? '已保存组织密钥；如要更新可重新输入' : '飞书 App Secret'}
          className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <select
          value={callbackMode}
          onChange={(event) => setCallbackMode(event.target.value as 'cloud_relay' | 'custom')}
          className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none"
        >
          <option value="cloud_relay">优先使用云端中继回调</option>
          <option value="custom">使用自定义 HTTPS 回调</option>
        </select>
        <input
          value={customCallbackUrl}
          onChange={(event) => setCustomCallbackUrl(event.target.value)}
          placeholder={callbackMode === 'custom' ? 'https://your-domain.example.com/feishu/callback' : '当前模式无需填写'}
          className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none"
          disabled={callbackMode !== 'custom'}
        />
      </div>

      <label className="flex items-center gap-2 text-[12px] font-medium text-slate-700">
        <input
          type="checkbox"
          checked={rememberLocalInputs}
          onChange={(event) => setRememberLocalInputs(event.target.checked)}
        />
        记住 App ID、回调地址和 App Secret（仅本机）
      </label>

      <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-4 text-[12px] text-slate-700 leading-6">
        <p>当前组织：{membership.organizationName || '未命名组织'}</p>
        <p>当前有效回调：{integration.effectiveCallbackUrl || '尚未形成可用回调地址'}</p>
        <p>最近状态：{integration.lastValidationMessage || '尚未验证组织飞书接入。'}</p>
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          className="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-[#335CFF] text-white text-[13px] font-bold shadow-sm disabled:opacity-50"
          onClick={() => void handleSave()}
          disabled={saveBusy || !appId.trim() || !hasChanges}
        >
          {saveBusy ? <RefreshCw size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}
          验证并保存组织飞书接入
        </button>
        {integration.enabled ? (
          <button
            type="button"
            className="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-white border border-gray-200 text-[13px] font-bold text-gray-700"
            onClick={() => setShowConfigEditor(false)}
          >
            取消更新
          </button>
        ) : null}
      </div>

      {renderAuditList()}
    </div>
  );

  if (sessionMode !== 'cloud') {
    return (
      <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm space-y-4">
        <div className="flex items-center gap-2 text-gray-900 font-bold text-[16px]">
          <Link2 size={17} />
          飞书协作
        </div>
        <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-4 text-[12px] text-slate-700 leading-6">
          连接云端后，加入或创建组织，才能启用飞书协作。
        </div>
        <button
          type="button"
          className="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-[#335CFF] text-white text-[13px] font-bold"
          onClick={onOpenCloudAuth}
        >
          <Users size={16} />
          注册 / 登录云端
        </button>
      </div>
    );
  }

  if (!membership.hasOrganization) {
    return (
      <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm space-y-4">
        <div className="flex items-center gap-2 text-gray-900 font-bold text-[16px]">
          <Link2 size={17} />
          飞书协作
        </div>
        <div className="rounded-2xl border border-amber-100 bg-amber-50 px-4 py-4 text-[12px] text-amber-800 leading-6">
          你还没有加入任何组织。飞书接通依赖组织信息，请先加入组织或创建组织。
        </div>
        <button
          type="button"
          className="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-[#335CFF] text-white text-[13px] font-bold"
          onClick={onOpenOrganizationSetup}
        >
          <Users size={16} />
          加入组织 / 创建组织
        </button>
      </div>
    );
  }

  if (!integration.enabled || showConfigEditor) {
    return renderIntegrationEditor();
  }

  return (
    <>
      <div className="space-y-6">
        <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm space-y-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-[16px] font-bold text-gray-900 flex items-center gap-2">
                <Bot size={17} />
                组织飞书接入
              </h2>
              <p className="text-[12px] text-gray-500 mt-1 leading-relaxed">
                当前组织已经接通飞书。组织成员现在可以授权自己的飞书身份，用于飞书协作、会议与通知联动。
              </p>
            </div>
            <div className="text-[11px] font-bold px-3 py-1.5 rounded-full border border-emerald-100 bg-emerald-50 text-emerald-700">
              组织已接通飞书
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-4 text-[12px] text-slate-700 space-y-2">
              <p><span className="font-bold text-slate-900">当前组织：</span>{membership.organizationName || '未命名组织'}</p>
              <p><span className="font-bold text-slate-900">飞书 App ID：</span>{integration.appId || '未填写'}</p>
              <p><span className="font-bold text-slate-900">当前回调：</span>{integration.effectiveCallbackUrl || '尚未形成可用回调地址'}</p>
            </div>
            <div className={`rounded-2xl border px-4 py-4 text-[12px] ${
              integration.authorizationReady
                ? 'border-emerald-100 bg-emerald-50 text-emerald-800'
                : 'border-amber-100 bg-amber-50 text-amber-800'
            }`}>
              <p className="font-bold mb-2">{integration.authorizationReady ? '成员授权已就绪' : '成员授权暂不可用'}</p>
              <p className="leading-6">{integration.lastValidationMessage || integration.authorizationBlockedReason || '组织飞书接入状态正常。'}</p>
            </div>
          </div>

          <button
            type="button"
            className="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-white border border-gray-200 text-[13px] font-bold text-gray-700"
            onClick={() => setShowConfigEditor(true)}
          >
            更新组织飞书接入
          </button>

          {renderAuditList()}
        </div>

        <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm space-y-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-[16px] font-bold text-gray-900 flex items-center gap-2">
                <Users size={17} />
                成员飞书授权
              </h2>
              <p className="text-[12px] text-gray-500 mt-1 leading-relaxed">
                这一步只授权你当前组织成员身份对应的飞书账号，不会修改整个组织的飞书应用配置。
              </p>
            </div>
            <div className={`text-[11px] font-bold px-3 py-1.5 rounded-full border ${
              authorization.linked
                ? 'border-emerald-100 bg-emerald-50 text-emerald-700'
                : authorization.readyForAuthorization
                  ? 'border-blue-100 bg-blue-50 text-[#335CFF]'
                  : 'border-amber-100 bg-amber-50 text-amber-700'
            }`}>
              {authorization.linked ? '已授权当前成员身份' : authorization.readyForAuthorization ? '待授权' : '暂不可授权'}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-2xl bg-slate-50 border border-slate-200 p-4">
              <p className="text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-2">当前组织成员</p>
              <p className="text-[13px] font-bold text-slate-900">{currentUserName || authorization.userId || '未识别'}</p>
              <p className="text-[12px] text-slate-600 mt-1 break-all">{authorization.userId || '尚未加载用户 ID'}</p>
            </div>
            <div className="rounded-2xl bg-slate-50 border border-slate-200 p-4">
              <p className="text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-2">当前状态</p>
              <p className="text-[13px] font-bold text-slate-900">
                {authorization.linked ? '当前成员已完成飞书授权' : authorization.readyForAuthorization ? '现在可以发起成员飞书授权' : '还不能发起成员飞书授权'}
              </p>
              <p className="text-[12px] text-slate-600 mt-1">{authorization.blockedReason || authorization.lastError || '授权完成后，这个组织成员身份就能参与飞书协作。'}</p>
            </div>
          </div>

          {authorization.linked ? (
            <div className="rounded-2xl border border-emerald-100 bg-emerald-50/70 px-4 py-4 text-[12px] text-emerald-800 space-y-2">
              <div className="flex items-center gap-2 font-bold">
                <ShieldCheck size={14} />
                已授权飞书身份
              </div>
              <p>显示名称：{authorization.name || authorization.enName || '未返回姓名'}</p>
              <p>飞书邮箱：{authorization.email || '飞书未返回邮箱'}</p>
              <p className="break-all">open_id：{authorization.openId || '未返回 open_id'}</p>
            </div>
          ) : (
            <div className={`rounded-2xl border px-4 py-4 text-[12px] leading-relaxed ${
              authorization.readyForAuthorization
                ? 'border-blue-100 bg-blue-50/70 text-slate-700'
                : 'border-amber-100 bg-amber-50 text-amber-800'
            }`}>
              <div className="flex items-center gap-2 font-bold mb-2">
                {authorization.readyForAuthorization ? <QrCode size={14} /> : <ShieldAlert size={14} />}
                {authorization.readyForAuthorization ? '当前成员还没有完成飞书授权' : '当前还不能发起成员飞书授权'}
              </div>
              <p>
                {authorization.readyForAuthorization
                  ? '点击“授权我的飞书身份”后会弹出授权面板。当前组织已接通飞书，你只需要完成自己的成员飞书授权。'
                  : authorization.blockedReason || authorization.lastError || '请先完成组织飞书接入。'}
              </p>
            </div>
          )}

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              className="inline-flex items-center gap-2 px-4 py-3 rounded-2xl bg-[#335CFF] text-white text-[13px] font-bold disabled:opacity-50"
              onClick={() => void onStartAuthorization()}
              disabled={!authorization.readyForAuthorization || isBusy}
            >
              {busyAction === 'starting' ? <RefreshCw size={16} className="animate-spin" /> : <QrCode size={16} />}
              {authorization.linked ? '重新授权飞书身份' : '授权我的飞书身份'}
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-2 px-4 py-3 rounded-2xl bg-white border border-gray-200 text-[13px] font-bold text-gray-700 disabled:opacity-50"
              onClick={() => void onRefreshAuthorization()}
              disabled={isBusy}
            >
              {busyAction === 'refreshing' ? <RefreshCw size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              刷新授权状态
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-2 px-4 py-3 rounded-2xl bg-white border border-gray-200 text-[13px] font-bold text-gray-700 disabled:opacity-50"
              onClick={() => void onClearAuthorization()}
              disabled={!authorization.linked || isBusy}
            >
              {busyAction === 'clearing' ? <RefreshCw size={16} className="animate-spin" /> : <Unplug size={16} />}
              解除授权
            </button>
          </div>
        </div>
      </div>

      {hasPendingAuthorization ? (
        <div className="fixed inset-0 z-50 bg-slate-950/35 backdrop-blur-sm flex items-center justify-center p-5">
          <div className="w-full max-w-4xl bg-white rounded-[28px] shadow-[0_24px_80px_rgba(15,23,42,0.18)] border border-slate-100 overflow-hidden" onClick={(event) => event.stopPropagation()}>
            <div className="flex items-center gap-4 px-6 py-5 border-b border-slate-100">
              <button type="button" className="w-10 h-10 shrink-0 rounded-2xl border border-slate-200 text-slate-500 hover:text-slate-800 hover:bg-slate-50 flex items-center justify-center" onClick={onClosePendingAuthorization} aria-label="关闭飞书成员授权">
                <X size={16} />
              </button>
              <div className="flex-1">
                <h3 className="text-[18px] font-bold text-slate-900">成员飞书授权</h3>
                <p className="text-[12px] text-slate-500 mt-1">授权完成后，工作台会自动刷新当前组织成员的飞书授权状态。</p>
              </div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-[280px_minmax(0,1fr)] gap-6 px-6 py-6">
              <div className="rounded-[24px] border border-slate-100 bg-slate-50 p-5 flex flex-col items-center justify-center text-center min-h-[320px]">
                {canShowQr ? (
                  <>
                    <div className="w-[232px] h-[232px] rounded-[24px] bg-white border border-slate-200 shadow-sm flex items-center justify-center overflow-hidden">
                      <img src={pendingAuthorization?.qrCodeDataUrl || undefined} alt="成员飞书授权二维码" className="w-[208px] h-[208px]" />
                    </div>
                    <p className="mt-4 text-[13px] font-bold text-slate-900">请用飞书扫码完成授权</p>
                    <p className="mt-2 text-[12px] leading-6 text-slate-500">扫码后在飞书里确认授权，工作台会自动刷新当前组织成员的飞书授权结果。</p>
                  </>
                ) : (
                  <>
                    <div className="w-14 h-14 rounded-2xl bg-amber-50 border border-amber-100 flex items-center justify-center text-amber-500">
                      <ShieldAlert size={24} />
                    </div>
                    <p className="mt-4 text-[13px] font-bold text-slate-900">当前还不能用手机扫码完成授权</p>
                    <p className="mt-2 text-[12px] leading-6 text-slate-500">{pendingAuthorization?.qrBlockedReason || '当前授权回调不可用。'}</p>
                  </>
                )}
              </div>

              <div className="space-y-4">
                <div className="rounded-[24px] border border-slate-100 bg-white p-5">
                  <p className="text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-2">当前回调地址</p>
                  <p className="text-[13px] font-semibold text-slate-900 break-all">{pendingAuthorization?.callbackUrl}</p>
                  <p className="text-[12px] text-slate-500 mt-2 leading-6">
                    手机扫码能否直接完成授权，取决于这里是否是可公网访问的 HTTPS 回调地址。
                  </p>
                </div>

                <div className="rounded-[24px] border border-slate-100 bg-slate-50 p-5">
                  <p className="text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-2">当前状态</p>
                  <p className="text-[13px] font-semibold text-slate-900">{pendingAuthorization?.statusMessage || '等待授权中'}</p>
                  <p className="text-[12px] text-slate-500 mt-2">
                    {pendingAuthorization?.isPolling ? '工作台正在后台轮询当前成员的授权状态。' : `本次授权有效期到 ${pendingAuthorization?.expiresAt.replace('T', ' ')}`}
                  </p>
                </div>

                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    className="inline-flex items-center gap-2 px-4 py-3 rounded-2xl bg-[#335CFF] text-white text-[13px] font-bold disabled:opacity-50"
                    onClick={() => void onOpenAuthorizationInBrowser()}
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
                    onClick={() => void onRefreshAuthorization()}
                  >
                    <RefreshCw size={16} />
                    手动刷新授权状态
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
