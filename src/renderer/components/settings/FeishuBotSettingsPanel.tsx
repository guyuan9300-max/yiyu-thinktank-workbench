import React, { useEffect, useMemo, useState } from 'react';
import { AlertCircle, Bot, CheckCircle2, KeyRound, RefreshCw, Send } from 'lucide-react';

import type { FeishuBotSettings, FeishuBotSettingsPayload, FeishuReceiveIdType } from '../../../shared/types';

type Props = {
  settings: FeishuBotSettings;
  canManage: boolean;
  defaultReceiverEmail?: string | null;
  onSubmit: (payload: FeishuBotSettingsPayload) => Promise<FeishuBotSettings>;
};

const RECEIVE_TYPE_LABELS: Record<FeishuReceiveIdType, string> = {
  open_id: 'open_id',
  user_id: 'user_id',
  email: '邮箱',
  chat_id: 'chat_id',
};

const RECEIVE_TYPE_HINTS: Record<FeishuReceiveIdType, string> = {
  open_id: '适合已经拿到飞书用户 open_id 的场景。',
  user_id: '适合企业内已知 user_id 的场景。',
  email: '如果你的飞书邮箱和当前账号一致，优先用这个。',
  chat_id: '适合先发到群或机器人私聊 chat。',
};

function statusTone(status: FeishuBotSettings['lastConnectionStatus']) {
  if (status === 'success') return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  if (status === 'failed') return 'border-rose-100 bg-rose-50 text-rose-700';
  return 'border-slate-100 bg-slate-50 text-slate-600';
}

export function FeishuBotSettingsPanel({ settings, canManage, defaultReceiverEmail, onSubmit }: Props) {
  const [appId, setAppId] = useState(settings.appId);
  const [receiveIdType, setReceiveIdType] = useState<FeishuReceiveIdType>(settings.receiveIdType);
  const [receiverId, setReceiverId] = useState(settings.receiverId);
  const [botName, setBotName] = useState(settings.botName);
  const [userBindingCallbackUrl, setUserBindingCallbackUrl] = useState(settings.userBindingCallbackUrl);
  const [appSecret, setAppSecret] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);

  useEffect(() => {
    setAppId(settings.appId);
    setReceiveIdType(settings.receiveIdType);
    setReceiverId(settings.receiverId);
    setBotName(settings.botName);
    setUserBindingCallbackUrl(settings.userBindingCallbackUrl);
  }, [settings]);

  const receiverPlaceholder = useMemo(() => {
    if (receiveIdType === 'email') return '请输入你的飞书邮箱';
    if (receiveIdType === 'chat_id') return '请输入 chat_id';
    if (receiveIdType === 'user_id') return '请输入 user_id';
    return '请输入 open_id';
  }, [receiveIdType]);

  const canSendTestMessage = appId.trim() && receiverId.trim() && (settings.hasAppSecret || appSecret.trim());
  const defaultTestMessage = `${botName.trim() || '罗茜茜'} 已接通成功，现在可以给你发消息了。`;

  async function handleSave() {
    setIsSaving(true);
    try {
      await onSubmit({
        appId: appId.trim(),
        receiveIdType,
        receiverId: receiverId.trim(),
        botName: botName.trim() || '罗茜茜',
        userBindingCallbackUrl: userBindingCallbackUrl.trim() || undefined,
        appSecret: appSecret.trim() || undefined,
      });
      setAppSecret('');
    } finally {
      setIsSaving(false);
    }
  }

  async function handleConnectAndSend() {
    setIsTesting(true);
    try {
      await onSubmit({
        appId: appId.trim(),
        receiveIdType,
        receiverId: receiverId.trim(),
        botName: botName.trim() || '罗茜茜',
        userBindingCallbackUrl: userBindingCallbackUrl.trim() || undefined,
        appSecret: appSecret.trim() || undefined,
        sendTestMessage: true,
        testMessage: defaultTestMessage,
      });
      setAppSecret('');
    } finally {
      setIsTesting(false);
    }
  }

  async function handleClearSecret() {
    setIsSaving(true);
    try {
      await onSubmit({
        appId: appId.trim(),
        receiveIdType,
        receiverId: receiverId.trim(),
        botName: botName.trim() || '罗茜茜',
        userBindingCallbackUrl: userBindingCallbackUrl.trim() || undefined,
        clearAppSecret: true,
      });
      setAppSecret('');
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm">
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          <h2 className="text-[16px] font-bold text-gray-900 flex items-center gap-2">
            <Bot size={17} />
            飞书单机器人
          </h2>
          <p className="text-[12px] text-gray-500 mt-1">
            先打通“接通成功即发测试消息”的最小闭环。App Secret 只进本机钥匙串，不落本地业务库。
          </p>
        </div>
        <div className={`text-[11px] font-bold px-3 py-1.5 rounded-full border ${statusTone(settings.lastConnectionStatus)}`}>
          {settings.lastConnectionStatus === 'success' ? '最近连接成功' : settings.lastConnectionStatus === 'failed' ? '最近连接失败' : '尚未测试'}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <input
              value={appId}
              onChange={(event) => setAppId(event.target.value)}
              placeholder="飞书 App ID"
              className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none"
              disabled={!canManage}
            />
            <input
              value={botName}
              onChange={(event) => setBotName(event.target.value)}
              placeholder="机器人称呼，例如 罗茜茜"
              className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none"
              disabled={!canManage}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-[180px_1fr_auto] gap-4">
            <select
              value={receiveIdType}
              onChange={(event) => setReceiveIdType(event.target.value as FeishuReceiveIdType)}
              className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none"
              disabled={!canManage}
            >
              {Object.entries(RECEIVE_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  接收方类型：{label}
                </option>
              ))}
            </select>
            <input
              value={receiverId}
              onChange={(event) => setReceiverId(event.target.value)}
              placeholder={receiverPlaceholder}
              className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none"
              disabled={!canManage}
            />
            {receiveIdType === 'email' && defaultReceiverEmail ? (
              <button
                type="button"
                className="px-4 py-3 rounded-2xl border border-blue-100 bg-blue-50 text-[12px] font-bold text-[#5B7BFE] disabled:opacity-50"
                onClick={() => setReceiverId(defaultReceiverEmail)}
                disabled={!canManage}
              >
                使用当前邮箱
              </button>
            ) : (
              <div />
            )}
          </div>

          <div className="rounded-2xl border border-gray-100 bg-gray-50 px-4 py-4">
            <div className="flex items-center gap-2 mb-3">
              <KeyRound size={15} className="text-slate-500" />
              <p className="text-[12px] font-bold text-gray-900">App Secret</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-3">
              <input
                type="password"
                value={appSecret}
                onChange={(event) => setAppSecret(event.target.value)}
                placeholder={settings.hasAppSecret ? '已保存到钥匙串；如要更新可重新输入' : '请输入飞书 App Secret'}
                className="w-full bg-white border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none"
                disabled={!canManage}
              />
              <button
                type="button"
                className="px-4 py-3 rounded-2xl border border-gray-200 bg-white text-[12px] font-bold text-gray-600 disabled:opacity-50"
                onClick={() => void handleClearSecret()}
                disabled={!canManage || (!settings.hasAppSecret && !appSecret.trim()) || isSaving || isTesting}
              >
                清空密钥
              </button>
            </div>
            <p className="text-[12px] text-gray-500 mt-3 leading-relaxed">
              {settings.hasAppSecret ? `当前密钥来源：${settings.secretSource}` : '当前还没有可用密钥。'}
              {settings.secretFingerprint ? ` · 指纹 ${settings.secretFingerprint}` : ''}
            </p>
          </div>

          <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-4">
            <p className="text-[12px] font-bold text-slate-900">飞书事件回调路径</p>
            <p className="text-[12px] text-slate-700 mt-2 break-all">/api/v1/channels/feishu/events</p>
            <p className="text-[12px] text-slate-500 mt-2 leading-relaxed">
              当前桌面版后端默认只跑在本机 `127.0.0.1`。如果要让飞书真正收到“你是谁？”并自动回复，还需要把这条路径暴露成公网可访问地址。
            </p>
          </div>

          <div className="rounded-2xl border border-dashed border-blue-100 bg-blue-50/70 px-4 py-4 space-y-3">
            <div>
              <p className="text-[12px] font-bold text-slate-900">个人绑定回调 URL（可选）</p>
              <p className="text-[12px] text-slate-500 mt-2 leading-relaxed">
                如果这里留空，系统会优先尝试使用云端 HTTPS 中继来支持手机扫码绑定；只有在没有公网入口时，才会退回当前桌面端本机浏览器授权。需要自定义回调时，再填写飞书后台允许的公网 HTTPS 回调地址。
              </p>
            </div>
            <input
              value={userBindingCallbackUrl}
              onChange={(event) => setUserBindingCallbackUrl(event.target.value)}
              placeholder="https://your-domain.example.com/api/v1/auth/feishu/callback"
              className="w-full bg-white border border-blue-100 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none"
              disabled={!canManage}
            />
            <p className="text-[12px] text-slate-600 break-all">
              当前保存值：{settings.userBindingCallbackUrl || '未单独配置，将优先尝试云端 HTTPS 中继；不可用时再回到本机 http://127.0.0.1:47829/api/v1/auth/feishu/callback'}
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-white border border-gray-200 text-[13px] font-bold text-gray-700 disabled:opacity-50"
              onClick={() => void handleSave()}
              disabled={!canManage || isSaving || isTesting}
            >
              {isSaving ? <RefreshCw size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}
              保存飞书配置
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-[#5B7BFE] text-white text-[13px] font-bold shadow-sm disabled:opacity-50"
              onClick={() => void handleConnectAndSend()}
              disabled={!canManage || isSaving || isTesting || !canSendTestMessage}
            >
              {isTesting ? <RefreshCw size={15} className="animate-spin" /> : <Send size={15} />}
              连接并发测试消息
            </button>
          </div>

          {!canManage && (
            <div className="rounded-2xl border border-amber-100 bg-amber-50 px-4 py-3 text-[12px] text-amber-700">
              当前账号只能查看飞书连接状态，不能修改凭据或发送测试消息。
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className={`rounded-2xl border px-4 py-4 ${statusTone(settings.lastConnectionStatus)}`}>
            <div className="flex items-start gap-3">
              {settings.lastConnectionStatus === 'failed' ? <AlertCircle size={18} /> : <CheckCircle2 size={18} />}
              <div className="min-w-0">
                <p className="text-[13px] font-bold">
                  {settings.lastConnectionStatus === 'success' ? '最近一次连接结果正常' : settings.lastConnectionStatus === 'failed' ? '最近一次连接失败' : '尚未执行连通性测试'}
                </p>
                <p className="text-[12px] mt-1 leading-relaxed">
                  {settings.lastConnectionMessage || '填好 App ID、密钥和接收方标识后，点击“连接并发测试消息”。'}
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-gray-100 bg-gray-50 px-4 py-4 space-y-3">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">接收方</p>
              <p className="text-[13px] font-bold text-gray-900 mt-1">
                {RECEIVE_TYPE_LABELS[receiveIdType]} · {receiverId || '尚未填写'}
              </p>
              <p className="text-[12px] text-gray-500 mt-1">{RECEIVE_TYPE_HINTS[receiveIdType]}</p>
            </div>
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">测试消息文案</p>
              <p className="text-[12px] text-gray-700 mt-1 leading-relaxed">{defaultTestMessage}</p>
            </div>
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">个人绑定回调</p>
              <p className="text-[12px] text-gray-700 mt-1 break-all">
                {settings.userBindingCallbackUrl || '未单独配置，默认回到本机回调'}
              </p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="rounded-2xl bg-white border border-gray-100 px-4 py-3">
                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">最近连接</p>
                <p className="text-[12px] text-gray-700 mt-1">{settings.lastConnectedAt || '尚未连接'}</p>
              </div>
              <div className="rounded-2xl bg-white border border-gray-100 px-4 py-3">
                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">最近发消息</p>
                <p className="text-[12px] text-gray-700 mt-1">{settings.lastTestMessageAt || '尚未发送'}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
