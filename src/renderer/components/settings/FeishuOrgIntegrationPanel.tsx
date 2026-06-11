import React, { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, ExternalLink, KeyRound, RefreshCw, Unlink, Users } from 'lucide-react';

import type {
  FeishuDeliveryProfile,
  FeishuDeliveryProfilePayload,
  FeishuMemberAuthorization,
  LocalInputMemoryFeishuIntegration,
  OrgFeishuIntegration,
  OrgFeishuIntegrationPayload,
  OrgMembershipSummary,
} from '../../../shared/types';

type MemberAuthorizationFlow = {
  authorizeUrl: string;
  callbackUrl: string;
  expiresAt: string;
  qrReady: boolean;
  qrBlockedReason?: string | null;
  qrCodeDataUrl: string | null;
  isPolling: boolean;
  statusMessage: string;
};

type Props = {
  sessionMode: 'local' | 'cloud';
  membership: OrgMembershipSummary;
  integration: OrgFeishuIntegration;
  deliveryProfile: FeishuDeliveryProfile;
  memberAuthorization: FeishuMemberAuthorization;
  memberAuthorizationFlow: MemberAuthorizationFlow | null;
  memberAuthorizationBusy: boolean;
  currentUserName?: string | null;
  saveBusy: boolean;
  savePhoneBusy: boolean;
  rememberedInputs: LocalInputMemoryFeishuIntegration;
  onSaveIntegration: (payload: OrgFeishuIntegrationPayload) => Promise<void>;
  onSaveRememberedInputs: (payload: LocalInputMemoryFeishuIntegration) => Promise<void>;
  onSaveDeliveryProfile: (payload: FeishuDeliveryProfilePayload) => Promise<void>;
  onStartMemberAuthorization: () => Promise<void>;
  onRefreshMemberAuthorization: () => Promise<void>;
  onClearMemberAuthorization: () => Promise<void>;
  onOpenMemberAuthorization: () => Promise<void>;
  onOpenOrganizationSetup?: () => void;
  onOpenCloudAuth?: () => void;
};

function statusTone(status: 'idle' | 'success' | 'failed') {
  if (status === 'success') {
    return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  }
  if (status === 'failed') {
    return 'border-rose-100 bg-rose-50 text-rose-700';
  }
  return 'border-slate-100 bg-slate-50 text-slate-600';
}

function deliveryTone(status: FeishuDeliveryProfile['deliveryStatus']) {
  if (status === 'matched') {
    return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  }
  if (status === 'failed') {
    return 'border-rose-100 bg-rose-50 text-rose-700';
  }
  if (status === 'not_found') {
    return 'border-amber-100 bg-amber-50 text-amber-700';
  }
  return 'border-slate-100 bg-slate-50 text-slate-600';
}

export function FeishuOrgIntegrationPanel({
  sessionMode,
  membership,
  integration,
  deliveryProfile,
  memberAuthorization,
  memberAuthorizationFlow,
  memberAuthorizationBusy,
  currentUserName,
  saveBusy,
  savePhoneBusy,
  rememberedInputs,
  onSaveIntegration,
  onSaveRememberedInputs,
  onSaveDeliveryProfile,
  onStartMemberAuthorization,
  onRefreshMemberAuthorization,
  onClearMemberAuthorization,
  onOpenMemberAuthorization,
}: Props) {
  const [appId, setAppId] = useState(integration.appId || rememberedInputs.appId || '');
  const [appSecret, setAppSecret] = useState(rememberedInputs.appSecret || '');
  const [rememberLocalInputs, setRememberLocalInputs] = useState(rememberedInputs.rememberInputs);
  const [mobile, setMobile] = useState(deliveryProfile.mobile || '');

  useEffect(() => {
    setAppId(integration.appId || rememberedInputs.appId || '');
    setAppSecret(rememberedInputs.appSecret || '');
    setRememberLocalInputs(rememberedInputs.rememberInputs);
  }, [
    integration.appId,
    rememberedInputs.appId,
    rememberedInputs.appSecret,
    rememberedInputs.rememberInputs,
  ]);

  useEffect(() => {
    setMobile(deliveryProfile.mobile || '');
  }, [deliveryProfile.mobile]);

  const integrationChanges =
    appId.trim() !== (integration.appId || '')
    || Boolean(appSecret.trim());
  const canConfigureIntegration = sessionMode === 'cloud' && membership.hasOrganization;
  const canConfigureDeliveryProfile = sessionMode === 'cloud' && membership.hasOrganization && integration.enabled;
  const canAuthorizeMember = sessionMode === 'cloud' && membership.hasOrganization && integration.enabled;
  const canSaveIntegration = canConfigureIntegration && integrationChanges && !saveBusy;
  const canSaveDeliveryProfile = canConfigureDeliveryProfile && mobile.trim() !== (deliveryProfile.mobile || '') && !savePhoneBusy;

  const integrationHelper = useMemo(() => {
    if (sessionMode !== 'cloud') {
      return '连接云端并加入组织后，才能启用飞书任务提醒。';
    }
    if (!membership.hasOrganization) {
      return '你还没有加入任何组织。飞书提醒依赖组织信息，请先加入组织或创建组织。';
    }
    if (integration.enabled) {
      return '当前组织飞书应用已验证。成员填写飞书手机号后，任务提醒即可自动按手机号匹配发送。';
    }
    return integration.lastValidationMessage || '完成后，软件会按成员填写的飞书手机号自动发送任务提醒。';
  }, [integration.lastValidationMessage, membership.hasOrganization, sessionMode]);

  const deliveryHelper = useMemo(() => {
    if (sessionMode !== 'cloud') {
      return '先连接云端，再填写你的飞书接收手机号。';
    }
    if (!membership.hasOrganization) {
      return '先加入或创建组织，再填写你的飞书接收手机号。';
    }
    if (!integration.enabled) {
      return '当前组织尚未接通飞书。接通后，软件才会按手机号匹配并发送任务提醒。';
    }
    return deliveryProfile.blockedReason
      || '请填写你登录飞书时使用的手机号。软件会按这个手机号匹配你的飞书身份并发送任务提醒。';
  }, [deliveryProfile.blockedReason, integration.enabled, membership.hasOrganization, sessionMode]);

  const handleSaveIntegration = async () => {
    const payload: OrgFeishuIntegrationPayload = {
      appId: appId.trim(),
      appSecret: appSecret.trim() || undefined,
    };
    await onSaveIntegration(payload);
	    await onSaveRememberedInputs({
	      rememberInputs: rememberLocalInputs,
	      appId: payload.appId || '',
	      callbackMode: payload.callbackMode || 'cloud_relay',
	      customCallbackUrl: payload.customCallbackUrl || '',
	      appSecret: payload.appSecret || '',
	    });
    if (!rememberLocalInputs) {
      setAppSecret('');
    }
  };

  const handleSaveDeliveryProfile = async () => {
    await onSaveDeliveryProfile({ mobile: mobile.trim() || null });
  };

  return (
    <div className="space-y-8">
      <div className="space-y-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-gray-500">组织飞书接入</p>
            <p className="text-[12px] text-gray-500 mt-1.5 leading-relaxed">
              这一步配置的是整个组织共用的飞书应用。验证通过后，软件会按成员填写的飞书手机号自动发送任务提醒。
            </p>
            <div className="mt-3 rounded-2xl border border-indigo-100 bg-indigo-50/70 px-4 py-3 text-[12px] leading-6 text-slate-700">
              <p className="font-bold text-slate-900">组织飞书接入需要管理员完成 5 步：</p>
              <ol className="mt-2 list-decimal space-y-1 pl-5">
                <li>
                  打开飞书开放平台：
                  <a
                    href="https://open.feishu.cn/app"
                    target="_blank"
                    rel="noreferrer"
                    className="ml-1 font-bold text-indigo-600 hover:text-indigo-700"
                  >
                    https://open.feishu.cn/app
                  </a>
                </li>
                <li>创建“企业自建应用”。</li>
                <li>复制 App ID 和 App Secret，填写到本页。</li>
                <li>启用应用的“机器人”能力，用于任务通知。</li>
                <li>
                  在“开发配置 → 安全设置 → 重定向 URL”中添加：
                  <span className="mt-1 block break-all rounded-xl bg-white px-3 py-2 font-mono text-[11px] text-indigo-700">
                    https://yiyu.love/oauth/feishu/member/callback
                  </span>
                </li>
              </ol>
              <p className="mt-2 text-[11px] text-slate-500">
                完成后点击“验证并保存组织飞书接入”。检测通过后，成员即可绑定自己的飞书身份并使用飞书文档同步。
              </p>
            </div>
          </div>
          <div className={`text-[10px] font-bold uppercase tracking-[0.12em] px-2.5 py-1 rounded-full border ${statusTone(integration.lastValidationStatus)}`}>
            {integration.enabled ? '已接通' : '未接通'}
          </div>
        </div>

        {canConfigureIntegration && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <input
                value={appId}
                onChange={(event) => setAppId(event.target.value)}
                placeholder="飞书 App ID"
                className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none disabled:text-gray-400 disabled:bg-gray-100"
              />
              <input
                type="password"
                value={appSecret}
                onChange={(event) => setAppSecret(event.target.value)}
                placeholder={integration.hasAppSecret ? '已保存组织密钥；如需更新请重新输入' : '飞书 App Secret'}
                className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none disabled:text-gray-400 disabled:bg-gray-100"
              />
            </div>

            <label className="flex items-center gap-2 text-[12px] font-medium text-gray-700">
              <input
                type="checkbox"
                checked={rememberLocalInputs}
                onChange={(event) => setRememberLocalInputs(event.target.checked)}
              />
              在本机记住 App ID / App Secret
            </label>
          </>
        )}

        <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
          <p className="text-[12px] font-bold text-slate-900">
            当前组织：{membership.organizationName || '尚未加入组织'}
          </p>
          <p className="text-[12px] text-slate-600 mt-2 leading-6">{integrationHelper}</p>
          {integration.configuredBy && integration.configuredAt ? (
            <p className="text-[11px] text-slate-400 mt-2">
              最近配置：{integration.configuredBy} · {integration.configuredAt}
            </p>
          ) : null}
        </div>

        {canConfigureIntegration && (
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => void handleSaveIntegration()}
              disabled={!canSaveIntegration}
              className="inline-flex items-center gap-2 rounded-2xl px-5 py-3 text-[13px] font-bold text-white bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saveBusy ? <RefreshCw size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
              验证并保存组织飞书接入
            </button>
          </div>
        )}
      </div>

      <div className="border-t border-gray-100 pt-6 space-y-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-gray-500">我的飞书文档授权</p>
            <p className="text-[12px] text-gray-500 mt-1.5 leading-relaxed">
              这一步绑定的是当前成员的个人飞书身份，用于创建、打开和从飞书导入文档；授权由益语统一 HTTPS 回调入口承接，不需要成员配置云地址或手机号。
            </p>
          </div>
          <div className={`text-[10px] font-bold uppercase tracking-[0.12em] px-2.5 py-1 rounded-full border ${
            memberAuthorization.linked
              ? 'border-emerald-100 bg-emerald-50 text-emerald-700'
              : memberAuthorization.readyForAuthorization
                ? 'border-amber-100 bg-amber-50 text-amber-700'
                : 'border-slate-100 bg-slate-50 text-slate-600'
          }`}>
            {memberAuthorization.linked ? '已授权' : memberAuthorization.readyForAuthorization ? '待授权' : '不可授权'}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
          <p className="text-[12px] font-bold text-slate-900 flex items-center gap-2">
            <KeyRound size={14} />
            当前成员：{currentUserName || '当前账号'}
          </p>
          <p className="text-[12px] text-slate-600 mt-2 leading-6">
            {memberAuthorization.linked
              ? `已绑定：${memberAuthorization.name || memberAuthorization.email || memberAuthorization.openId || '当前飞书成员'}`
              : memberAuthorization.blockedReason || '组织飞书应用已接通。绑定后，软件创建的飞书文档会确保当前成员可打开和编辑，也可以从飞书导入文档。'}
          </p>
          {memberAuthorization.boundAt ? (
            <p className="text-[11px] text-slate-400 mt-2">授权时间：{memberAuthorization.boundAt}</p>
          ) : null}
          {memberAuthorization.lastError ? (
            <p className="text-[11px] text-rose-500 mt-2">{memberAuthorization.lastError}</p>
          ) : null}
          {memberAuthorizationFlow ? (
            <div className="mt-3 rounded-2xl border border-blue-100 bg-white px-4 py-3">
              <p className="text-[12px] font-bold text-blue-700">{memberAuthorizationFlow.statusMessage}</p>
              {memberAuthorizationFlow.qrCodeDataUrl ? (
                <img src={memberAuthorizationFlow.qrCodeDataUrl} alt="飞书成员授权二维码" className="mt-3 h-32 w-32 rounded-xl border border-gray-100 bg-white p-1" />
              ) : null}
              <button
                type="button"
                onClick={() => void onOpenMemberAuthorization()}
                className="mt-3 inline-flex items-center gap-2 rounded-xl border border-blue-100 bg-blue-50 px-3 py-2 text-[12px] font-bold text-blue-700 transition hover:bg-blue-100"
              >
                <ExternalLink size={14} />
                打开授权页
              </button>
            </div>
          ) : null}
        </div>

        {canAuthorizeMember && (
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => void onStartMemberAuthorization()}
              disabled={memberAuthorizationBusy || !memberAuthorization.readyForAuthorization}
              className="inline-flex items-center gap-2 rounded-2xl px-5 py-3 text-[13px] font-bold text-white bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {memberAuthorizationBusy ? <RefreshCw size={16} className="animate-spin" /> : <ExternalLink size={16} />}
              {memberAuthorization.linked ? '重新绑定飞书身份' : '绑定飞书身份'}
            </button>
            <button
              type="button"
              onClick={() => void onRefreshMemberAuthorization()}
              disabled={memberAuthorizationBusy}
              className="inline-flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-5 py-3 text-[13px] font-bold text-slate-700 disabled:opacity-50"
            >
              <RefreshCw size={16} />
              刷新授权状态
            </button>
            {memberAuthorization.linked && (
              <button
                type="button"
                onClick={() => void onClearMemberAuthorization()}
                disabled={memberAuthorizationBusy}
                className="inline-flex items-center gap-2 rounded-2xl border border-rose-100 bg-white px-5 py-3 text-[13px] font-bold text-rose-600 disabled:opacity-50"
              >
                <Unlink size={16} />
                解除授权
              </button>
            )}
          </div>
        )}
      </div>

	      <div className="border-t border-gray-100 pt-6 space-y-5">
	        <div className="flex items-start justify-between gap-4">
	          <div className="min-w-0 flex-1">
	            <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-gray-500">任务提醒手机号（可选）</p>
	            <p className="text-[12px] text-gray-500 mt-1.5 leading-relaxed">
	              只用于飞书机器人给你发送任务提醒。文档创建、打开和导入看上面的“我的飞书文档授权”，不靠手机号完成。
	            </p>
	          </div>
          <div className={`text-[10px] font-bold uppercase tracking-[0.12em] px-2.5 py-1 rounded-full border ${deliveryTone(deliveryProfile.deliveryStatus)}`}>
            {deliveryProfile.deliveryStatusLabel}
          </div>
        </div>

        {canConfigureDeliveryProfile && (
          <input
            value={mobile}
            onChange={(event) => setMobile(event.target.value)}
            placeholder="飞书账号对应手机号"
            className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none"
          />
        )}

        <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
          <p className="text-[12px] font-bold text-slate-900 flex items-center gap-2">
            <Users size={14} />
            当前成员：{currentUserName || '当前账号'}
          </p>
          <p className="text-[12px] text-slate-600 mt-2 leading-6">{deliveryHelper}</p>
          {deliveryProfile.lastVerifiedAt ? (
            <p className="text-[11px] text-slate-400 mt-2">
              最近校验：{deliveryProfile.lastVerifiedAt}
              {deliveryProfile.receiveId ? ` · 已匹配 ${deliveryProfile.receiveId}` : ''}
            </p>
          ) : null}
          {deliveryProfile.lastError ? (
            <p className="text-[11px] text-rose-500 mt-2">{deliveryProfile.lastError}</p>
          ) : null}
        </div>

        {canConfigureDeliveryProfile && (
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => void handleSaveDeliveryProfile()}
              disabled={!canSaveDeliveryProfile}
              className="inline-flex items-center gap-2 rounded-2xl px-5 py-3 text-[13px] font-bold text-white bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {savePhoneBusy ? <RefreshCw size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
              {deliveryProfile.mobile ? '更新飞书手机号' : '保存飞书手机号'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
