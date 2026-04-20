import React from 'react';
import {
  AlertCircle,
  Building2,
  CheckCircle2,
  Download,
  FileBadge,
  Link2,
  RefreshCw,
  Search,
  Unlink2,
  X,
} from 'lucide-react';
import type {
  EventLineExpenseEvidenceLink,
  ExpenseEvidenceRecord,
  ExpenseImportSearchPayload,
  ExpenseImportSearchResponse,
  OrgDingtalkFinanceIntegration,
} from '../../../shared/types.js';

type Props = {
  open: boolean;
  workObjectLabel: string;
  workObjectName: string;
  eventLineName?: string | null;
  taskTitle?: string | null;
  integration: OrgDingtalkFinanceIntegration | null;
  integrationLoading: boolean;
  evidenceItems: ExpenseEvidenceRecord[];
  evidenceLoading: boolean;
  existingQuery: string;
  onExistingQueryChange: (value: string) => void;
  onRefreshEvidence: () => void;
  importSearchDraft: ExpenseImportSearchPayload;
  onImportSearchDraftChange: (patch: Partial<ExpenseImportSearchPayload>) => void;
  importSearchResult: ExpenseImportSearchResponse | null;
  importSearchLoading: boolean;
  selectedImportSourceIds: string[];
  onToggleImportSource: (sourceInstanceId: string) => void;
  onRunImportSearch: () => void;
  onImportSelected: () => void;
  onFetchAttachments: (evidenceId: string) => void;
  linkedEvidenceIds: string[];
  onLinkEvidence?: (evidenceId: string) => void;
  onUnlinkEvidence?: (evidenceId: string) => void;
  onClose: () => void;
};

function formatAmount(amount?: number | null, currency = 'CNY') {
  if (typeof amount !== 'number' || Number.isNaN(amount)) return '金额待补';
  try {
    return new Intl.NumberFormat('zh-CN', {
      style: 'currency',
      currency,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${amount.toFixed(2)} ${currency}`;
  }
}

function formatMoment(value?: string | null) {
  if (!value) return '未记录';
  return value.replace('T', ' ').slice(0, 16);
}

export function ExpenseEvidenceModal({
  open,
  workObjectLabel,
  workObjectName,
  eventLineName,
  taskTitle,
  integration,
  integrationLoading,
  evidenceItems,
  evidenceLoading,
  existingQuery,
  onExistingQueryChange,
  onRefreshEvidence,
  importSearchDraft,
  onImportSearchDraftChange,
  importSearchResult,
  importSearchLoading,
  selectedImportSourceIds,
  onToggleImportSource,
  onRunImportSearch,
  onImportSelected,
  onFetchAttachments,
  linkedEvidenceIds,
  onLinkEvidence,
  onUnlinkEvidence,
  onClose,
}: Props) {
  if (!open) return null;

  const selectedImportCount = selectedImportSourceIds.length;
  const canOperateIntegration = Boolean(integration?.enabled && integration?.appKey);

  return (
    <div className="fixed inset-0 z-[130] flex items-center justify-center bg-black/30 px-4 py-6 backdrop-blur-sm" onClick={onClose}>
      <div
        className="flex max-h-[88vh] w-full max-w-[1180px] flex-col overflow-hidden rounded-[30px] border border-gray-100 bg-white shadow-[0_24px_80px_rgba(15,23,42,0.16)]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-gray-100 px-6 py-5">
          <div className="min-w-0">
            <p className="text-[12px] font-bold uppercase tracking-[0.12em] text-[#5B7BFE]">票据证明</p>
            <h2 className="mt-1 truncate text-[22px] font-bold text-gray-900">
              {workObjectName || `当前${workObjectLabel}`}
            </h2>
            <p className="mt-2 text-[12px] leading-6 text-gray-500">
              这里承接钉钉财务票据的导入、标准化和事件线关联。钉钉是报销真源，益语负责整理、搜索和汇报引用。
            </p>
            {eventLineName ? (
              <p className="mt-2 inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-[12px] font-bold text-emerald-700">
                <Link2 size={12} />
                当前准备关联到事件线：{eventLineName}
              </p>
            ) : null}
            {taskTitle ? (
              <p className="mt-2 inline-flex items-center gap-2 rounded-full bg-blue-50 px-3 py-1 text-[12px] font-bold text-[#5B7BFE]">
                <Link2 size={12} />
                当前准备关联到任务：{taskTitle}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-10 w-10 items-center justify-center rounded-2xl border border-gray-200 text-gray-400 transition hover:bg-gray-50 hover:text-gray-700"
            aria-label="关闭票据证明弹窗"
          >
            <X size={16} />
          </button>
        </div>

        <div className="grid flex-1 gap-0 overflow-hidden lg:grid-cols-[1.08fr_0.92fr]">
          <div className="flex min-h-0 flex-col border-r border-gray-100">
            <div className="border-b border-gray-100 bg-gray-50/70 px-6 py-4">
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-2xl border border-gray-200 bg-white px-4 py-3">
                  <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.12em] text-gray-500">
                    <Building2 size={13} />
                    组织钉钉接入
                  </div>
                  {integrationLoading ? (
                    <p className="mt-3 text-[13px] text-gray-400">正在读取接入状态…</p>
                  ) : integration?.enabled ? (
                    <>
                      <p className="mt-3 text-[14px] font-bold text-gray-900">{integration.organizationName || '当前组织'}</p>
                      <p className="mt-1 text-[12px] text-gray-500">AppKey：{integration.appKey || '未显示'}</p>
                      <p className="mt-2 inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-[11px] font-bold text-emerald-700">
                        <CheckCircle2 size={12} />
                        已接通，可继续搜索与导入票据元数据
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="mt-3 text-[13px] text-gray-500">当前组织还没有完成钉钉财务接入。</p>
                      <p className="mt-2 inline-flex items-center gap-2 rounded-full bg-amber-50 px-3 py-1 text-[11px] font-bold text-amber-700">
                        <AlertCircle size={12} />
                        先去系统设置完成组织接入，这里才会有真实钉钉票据可导入
                      </p>
                    </>
                  )}
                </div>

                <div className="rounded-2xl border border-gray-200 bg-white px-4 py-3">
                  <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.12em] text-gray-500">
                    <FileBadge size={13} />
                    当前池子
                  </div>
                  <p className="mt-3 text-[14px] font-bold text-gray-900">{workObjectName || `当前${workObjectLabel}`}</p>
                  <p className="mt-1 text-[12px] text-gray-500">
                    已入池 {evidenceItems.length} 条票据记录
                    {taskTitle
                      ? ` · 已关联 ${linkedEvidenceIds.length} 条到当前任务`
                      : eventLineName
                        ? ` · 已关联 ${linkedEvidenceIds.length} 条到当前事件线`
                        : ''}
                  </p>
                  <p className="mt-2 text-[11px] leading-5 text-gray-400">
                    V1 先打通池子、搜索和关联；真实钉钉附件抓取与 OCR 只按需触发，不会一上来全量拉取。
                  </p>
                </div>
              </div>
            </div>

            <div className="flex min-h-0 flex-1 flex-col">
              <div className="flex items-center gap-3 border-b border-gray-100 px-6 py-4">
                <div className="relative flex-1">
                  <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    value={existingQuery}
                    onChange={(event) => onExistingQueryChange(event.target.value)}
                    placeholder="搜索已入池票据（标题 / 申请人 / 分类）"
                    className="w-full rounded-2xl border border-gray-200 bg-white py-2 pl-9 pr-4 text-[13px] font-medium text-gray-700 outline-none transition focus:border-[#5B7BFE]"
                  />
                </div>
                <button
                  type="button"
                  onClick={onRefreshEvidence}
                  className="inline-flex items-center gap-2 rounded-2xl border border-gray-200 px-3 py-2 text-[12px] font-bold text-gray-600 transition hover:border-[#D7E0FF] hover:bg-[#F8FAFF] hover:text-[#5B7BFE]"
                >
                  <RefreshCw size={14} />
                  刷新
                </button>
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
                {evidenceLoading ? (
                  <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50 px-4 py-8 text-center text-[13px] text-gray-400">
                    正在读取票据池…
                  </div>
                ) : evidenceItems.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50 px-4 py-8 text-center text-[13px] text-gray-400">
                    当前{workObjectLabel}还没有入池票据。可以先在右侧搜索可导入元数据，或者等钉钉接通后再来补。
                  </div>
                ) : (
                  <div className="space-y-3">
                    {evidenceItems.map((item) => {
                      const linked = linkedEvidenceIds.includes(item.id);
                      return (
                        <div key={item.id} className="rounded-2xl border border-gray-200 bg-white px-4 py-4 shadow-sm">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="truncate text-[14px] font-bold text-gray-900">{item.displayTitle || item.sourceTitle}</p>
                              <p className="mt-1 text-[12px] text-gray-500">
                                {item.applicantUserName || '申请人待补'} · {formatAmount(item.amount, item.currency)}
                              </p>
                            </div>
                            <span className="shrink-0 rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold text-slate-600">
                              {item.normalizedCategory || item.approvalStatus || '待归类'}
                            </span>
                          </div>

                          <div className="mt-2 text-[11px] leading-5 text-gray-400">
                            提交：{formatMoment(item.submittedAt)} · 审批：{formatMoment(item.approvedAt)}
                          </div>
                          {item.summary ? (
                            <p className="mt-3 text-[12px] leading-6 text-gray-600">{item.summary}</p>
                          ) : null}

                          <div className="mt-3 flex flex-wrap gap-2">
                            {(item.tags || []).map((tag) => (
                              <span key={`${item.id}-${tag}`} className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-bold text-[#5B7BFE]">
                                {tag}
                              </span>
                            ))}
                          </div>

                          <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
                            <div className="text-[11px] text-gray-400">
                              附件 {item.attachments.length} 个
                            </div>
                            <div className="flex flex-wrap items-center gap-2">
                              <button
                                type="button"
                                onClick={() => onFetchAttachments(item.id)}
                                className="inline-flex items-center gap-1 rounded-full border border-gray-200 px-3 py-1.5 text-[11px] font-bold text-gray-600 transition hover:border-[#D7E0FF] hover:bg-[#F8FAFF] hover:text-[#5B7BFE]"
                              >
                                <Download size={12} />
                                补抓附件
                              </button>
                              {(eventLineName || taskTitle) && onLinkEvidence ? (
                                linked ? (
                                  <button
                                    type="button"
                                    onClick={() => onUnlinkEvidence?.(item.id)}
                                    className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-3 py-1.5 text-[11px] font-bold text-amber-700 transition hover:bg-amber-100"
                                  >
                                    <Unlink2 size={12} />
                                    {taskTitle ? '解除任务关联' : '解除关联'}
                                  </button>
                                ) : (
                                  <button
                                    type="button"
                                    onClick={() => onLinkEvidence(item.id)}
                                    className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-[11px] font-bold text-emerald-700 transition hover:bg-emerald-100"
                                  >
                                    <Link2 size={12} />
                                    {taskTitle ? '关联到任务' : '关联到事件线'}
                                  </button>
                                )
                              ) : null}
                            </div>
                          </div>

                          {item.attachments.length ? (
                            <div className="mt-3 space-y-2 rounded-2xl border border-gray-100 bg-gray-50 px-3 py-3">
                              {item.attachments.map((attachment) => (
                                <div key={attachment.id} className="rounded-2xl bg-white px-3 py-2 text-[11px] text-gray-600 shadow-sm">
                                  <div className="flex items-center justify-between gap-3">
                                    <span className="truncate font-bold text-gray-800">{attachment.fileName}</span>
                                    <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-600">
                                      {attachment.downloadStatus === 'fetched' ? '已抓取' : attachment.downloadStatus === 'failed' ? '抓取失败' : '待抓取'}
                                    </span>
                                  </div>
                                  <div className="mt-1 text-[10px] text-gray-400">
                                    OCR：{attachment.ocrStatus === 'done' ? '已完成' : attachment.ocrStatus === 'failed' ? '失败' : attachment.ocrStatus === 'skipped' ? '跳过' : '待执行'}
                                  </div>
                                  {attachment.ocrSummary ? (
                                    <p className="mt-1 leading-5 text-gray-500">{attachment.ocrSummary}</p>
                                  ) : null}
                                </div>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="flex min-h-0 flex-col">
            <div className="border-b border-gray-100 bg-gray-50/70 px-6 py-4">
              <div className="flex items-center gap-2 text-[13px] font-bold text-gray-900">
                <Search size={15} className="text-[#5B7BFE]" />
                搜索并导入钉钉票据元数据
              </div>
              <p className="mt-2 text-[12px] leading-6 text-gray-500">
                V1 先走“元数据先入池、附件按需抓取”的链路。这里搜索的是可导入记录，不会直接改钉钉审批。
              </p>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
              <div className="grid gap-3 md:grid-cols-2">
                <label className="block">
                  <span className="mb-2 block text-[12px] font-bold text-gray-500">关键词</span>
                  <input
                    value={importSearchDraft.query || ''}
                    onChange={(event) => onImportSearchDraftChange({ query: event.target.value })}
                    placeholder="标题 / 模板 / 申请人"
                    className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium text-gray-700 outline-none transition focus:border-[#5B7BFE]"
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-[12px] font-bold text-gray-500">申请人</span>
                  <input
                    value={importSearchDraft.applicantUserName || ''}
                    onChange={(event) => onImportSearchDraftChange({ applicantUserName: event.target.value })}
                    placeholder="可按提交人缩小范围"
                    className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium text-gray-700 outline-none transition focus:border-[#5B7BFE]"
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-[12px] font-bold text-gray-500">审批状态</span>
                  <select
                    value={importSearchDraft.approvalStatus || ''}
                    onChange={(event) => onImportSearchDraftChange({ approvalStatus: event.target.value || null })}
                    className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium text-gray-700 outline-none transition focus:border-[#5B7BFE]"
                  >
                    <option value="">全部状态</option>
                    <option value="approved">已通过</option>
                    <option value="processing">审批中</option>
                    <option value="rejected">已驳回</option>
                  </select>
                </label>
                <label className="flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[12px] font-medium text-gray-600">
                  <input
                    type="checkbox"
                    checked={Boolean(importSearchDraft.includeImported)}
                    onChange={(event) => onImportSearchDraftChange({ includeImported: event.target.checked })}
                  />
                  包含已导入的票据记录
                </label>
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={onRunImportSearch}
                  disabled={importSearchLoading || !canOperateIntegration}
                  className="inline-flex items-center gap-2 rounded-2xl bg-[#5B7BFE] px-4 py-2.5 text-[12px] font-bold text-white transition hover:bg-[#4A6AE8] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Search size={14} />
                  {importSearchLoading ? '搜索中…' : '搜索可导入记录'}
                </button>
                <button
                  type="button"
                  onClick={onImportSelected}
                  disabled={selectedImportCount === 0 || importSearchLoading}
                  className="inline-flex items-center gap-2 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-[12px] font-bold text-emerald-700 transition hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Download size={14} />
                  导入已勾选（{selectedImportCount}）
                </button>
              </div>

              {importSearchResult?.message ? (
                <div className="mt-4 rounded-2xl border border-amber-100 bg-amber-50 px-4 py-3 text-[12px] leading-6 text-amber-700">
                  {importSearchResult.message}
                </div>
              ) : null}

              <div className="mt-5 space-y-3">
                {importSearchResult && importSearchResult.items.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50 px-4 py-8 text-center text-[13px] text-gray-400">
                    当前没有匹配的可导入记录。
                  </div>
                ) : null}
                {(importSearchResult?.items || []).map((item) => {
                  const selected = selectedImportSourceIds.includes(item.sourceInstanceId);
                  const imported = Boolean(item.importedEvidenceId);
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => {
                        if (imported) return;
                        onToggleImportSource(item.sourceInstanceId);
                      }}
                      className={`w-full rounded-2xl border px-4 py-4 text-left transition ${
                        imported
                          ? 'border-gray-200 bg-gray-50 text-gray-400'
                          : selected
                            ? 'border-[#BFD0FF] bg-[#F8FAFF]'
                            : 'border-gray-200 bg-white hover:border-[#D7E0FF] hover:bg-[#FAFBFF]'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-[14px] font-bold text-gray-900">{item.sourceTitle}</p>
                          <p className="mt-1 text-[12px] text-gray-500">
                            {item.applicantUserName || '申请人待补'} · {formatAmount(item.amount, item.currency)}
                          </p>
                        </div>
                        <span className={`shrink-0 rounded-full px-2.5 py-1 text-[10px] font-bold ${
                          imported
                            ? 'bg-gray-200 text-gray-500'
                            : selected
                              ? 'bg-[#5B7BFE] text-white'
                              : 'bg-slate-100 text-slate-600'
                        }`}>
                          {imported ? '已入池' : selected ? '已勾选' : '待导入'}
                        </span>
                      </div>
                      <div className="mt-2 text-[11px] leading-5 text-gray-400">
                        模板：{item.sourceTemplateName || item.sourceTemplateCode || '未标模板'} · 提交：{formatMoment(item.submittedAt)}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ExpenseEvidenceModal;
