import React, { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, Landmark, RefreshCw } from 'lucide-react';

import type {
  OrgDingtalkFinanceIntegration,
  OrgDingtalkFinanceIntegrationPayload,
  OrgMembershipSummary,
} from '../../../shared/types';

type Props = {
  sessionMode: 'local' | 'cloud';
  membership: OrgMembershipSummary;
  integration: OrgDingtalkFinanceIntegration;
  saveBusy: boolean;
  canManage: boolean;
  onSaveIntegration: (payload: OrgDingtalkFinanceIntegrationPayload) => Promise<void>;
  onOpenOrganizationSetup: () => void;
  onOpenCloudAuth: () => void;
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

export function DingtalkFinanceIntegrationPanel({
  sessionMode,
  membership,
  integration,
  saveBusy,
  canManage,
  onSaveIntegration,
  onOpenOrganizationSetup,
  onOpenCloudAuth,
}: Props) {
  const [appKey, setAppKey] = useState(integration.appKey || '');
  const [appSecret, setAppSecret] = useState('');
  const [operatorMobile, setOperatorMobile] = useState(integration.operatorMobile || '');
  const [syncEnabled, setSyncEnabled] = useState(integration.syncEnabled);
  const [templateNamesText, setTemplateNamesText] = useState((integration.mappedTemplateNames || []).join('，'));

  useEffect(() => {
    setAppKey(integration.appKey || '');
    setAppSecret('');
    setOperatorMobile(integration.operatorMobile || '');
    setSyncEnabled(integration.syncEnabled);
    setTemplateNamesText((integration.mappedTemplateNames || []).join('，'));
  }, [integration.appKey, integration.mappedTemplateNames, integration.operatorMobile, integration.syncEnabled]);

  const canConfigure = sessionMode === 'cloud' && membership.hasOrganization && canManage;
  const templateNames = useMemo(
    () =>
      templateNamesText
        .split(/[，,\n]/)
        .map((item) => item.trim())
        .filter(Boolean),
    [templateNamesText],
  );
  const integrationChanged =
    appKey.trim() !== (integration.appKey || '')
    || Boolean(appSecret.trim())
    || operatorMobile.trim() !== (integration.operatorMobile || '')
    || syncEnabled !== integration.syncEnabled
    || templateNames.join('|') !== (integration.mappedTemplateNames || []).join('|');
  const canSave = canConfigure && integrationChanged && !saveBusy;

  const helperText = useMemo(() => {
    if (sessionMode !== 'cloud') {
      return '连接云端并加入组织后，才能启用钉钉票据导入。';
    }
    if (!membership.hasOrganization) {
      return '你还没有加入任何组织。钉钉财务接入依赖组织信息，请先加入组织或创建组织。';
    }
    if (!canManage) {
      return '当前账号只有查看权限。组织钉钉财务接入需要管理员统一维护。';
    }
    if (integration.enabled) {
      return '当前组织已接通钉钉财务。票据池会按“元数据先入池、附件按需抓取”的方式工作。';
    }
    return integration.lastValidationMessage || '先完成组织级钉钉财务接入，工作对象里的票据证明池才会有真实数据可导入。';
  }, [canManage, integration.enabled, integration.lastValidationMessage, membership.hasOrganization, sessionMode]);

  const handleSave = async () => {
    await onSaveIntegration({
      appKey: appKey.trim() || null,
      appSecret: appSecret.trim() || undefined,
      operatorMobile: operatorMobile.trim() || null,
      syncEnabled,
      mappedTemplateNames: templateNames,
    });
    setAppSecret('');
  };

  return (
    <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[16px] font-bold text-gray-900 flex items-center gap-2">
            <Landmark size={17} />
            组织钉钉财务接入
          </h2>
          <p className="text-[12px] text-gray-500 mt-1 leading-relaxed">
            这一步配置的是整个组织共用的钉钉财务导入能力。钉钉是报销真源，益语只负责票据整理、事件线引用和导出汇报。
          </p>
        </div>
        <div className={`text-[11px] font-bold px-3 py-1.5 rounded-full border ${statusTone(integration.lastValidationStatus)}`}>
          {integration.enabled ? '组织已接通钉钉财务' : '组织尚未接通钉钉财务'}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <input
          value={appKey}
          onChange={(event) => setAppKey(event.target.value)}
          placeholder="钉钉 AppKey"
          className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none disabled:text-gray-400 disabled:bg-gray-100"
          disabled={!canConfigure}
        />
        <input
          value={operatorMobile}
          onChange={(event) => setOperatorMobile(event.target.value)}
          placeholder="有审批查看权限的钉钉手机号"
          className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none disabled:text-gray-400 disabled:bg-gray-100"
          disabled={!canConfigure}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <input
          type="password"
          value={appSecret}
          onChange={(event) => setAppSecret(event.target.value)}
          placeholder={integration.hasAppSecret ? '已保存组织密钥；如需更新请重新输入' : '钉钉 AppSecret'}
          className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none disabled:text-gray-400 disabled:bg-gray-100"
          disabled={!canConfigure}
        />
      </div>

      {integration.resolvedOperatorUserId ? (
        <div className="rounded-2xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-[12px] leading-6 text-emerald-700">
          当前已校验的操作人 userId：{integration.resolvedOperatorUserId}
        </div>
      ) : null}

      <label className="block">
        <span className="mb-2 block text-[12px] font-bold text-gray-500">票据相关审批模板（可选）</span>
        <textarea
          value={templateNamesText}
          onChange={(event) => setTemplateNamesText(event.target.value)}
          rows={3}
          placeholder="可填写报销单、借款单等模板名称，逗号或换行分隔"
          className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] leading-6 font-medium outline-none disabled:text-gray-400 disabled:bg-gray-100"
          disabled={!canConfigure}
        />
      </label>

      <label className="flex items-center gap-2 text-[12px] font-medium text-gray-700">
        <input
          type="checkbox"
          checked={syncEnabled}
          onChange={(event) => setSyncEnabled(event.target.checked)}
          disabled={!canConfigure}
        />
        开启每日票据元数据同步
      </label>

      <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
        <p className="text-[12px] font-bold text-slate-900">
          当前组织：{membership.organizationName || '尚未加入组织'}
        </p>
        <p className="text-[12px] text-slate-600 mt-2 leading-6">{helperText}</p>
        {integration.configuredBy && integration.configuredAt ? (
          <p className="text-[11px] text-slate-400 mt-2">
            最近配置：{integration.configuredBy} · {integration.configuredAt}
          </p>
        ) : null}
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => {
            if (sessionMode !== 'cloud') {
              onOpenCloudAuth();
              return;
            }
            if (!membership.hasOrganization) {
              onOpenOrganizationSetup();
              return;
            }
            if (!canManage) return;
            void handleSave();
          }}
          disabled={sessionMode === 'cloud' && membership.hasOrganization ? !canSave : false}
          className="inline-flex items-center gap-2 rounded-2xl px-5 py-3 text-[13px] font-bold text-white bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saveBusy ? <RefreshCw size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
          {sessionMode !== 'cloud'
            ? '连接云端'
            : !membership.hasOrganization
              ? '加入 / 创建组织'
              : !canManage
                ? '仅管理员可配置'
                : '验证并保存钉钉接入'}
        </button>
      </div>
    </div>
  );
}

export default DingtalkFinanceIntegrationPanel;
