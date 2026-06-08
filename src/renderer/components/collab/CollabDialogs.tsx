import React from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Database,
  Download,
  Eye,
  Layers3,
  RefreshCw,
  UploadCloud,
  X,
} from 'lucide-react';
import type {
  CollabConflictDecision,
  CollabConflictDecisionChoice,
  CollabConflictGroup,
  PullPreview,
  PushPreview,
} from '../../../shared/types';

type PreviewMode = 'push' | 'pull';

type CollabPreviewDialogProps = {
  open: boolean;
  mode: PreviewMode;
  preview: PushPreview | PullPreview | null;
  selectedPaths: string[];
  conflictGroups: CollabConflictGroup[];
  conflictDecisions: CollabConflictDecision[];
  message: string;
  errorMessage?: string | null;
  busy: boolean;
  onClose: () => void;
  onConflictDecisionChange: (groupId: string, choice: CollabConflictDecisionChoice) => void;
  onSelectPullCommit?: (targetCommit: string | null) => void;
  onMessageChange: (nextValue: string) => void;
  onConfirm: () => void;
};

function ActionButton({
  primary,
  disabled,
  className = '',
  onClick,
  children,
}: {
  primary?: boolean;
  disabled?: boolean;
  className?: string;
  onClick?: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-2 rounded-2xl px-4 py-2.5 text-[13px] font-bold transition-all ${
        primary
          ? 'bg-[#5B7BFE] text-white shadow-[0_8px_24px_rgba(91,123,254,0.24)] hover:bg-[#4a6be6] disabled:cursor-not-allowed disabled:opacity-60'
          : 'border border-gray-200 bg-white text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60'
      } ${className}`}
    >
      {children}
    </button>
  );
}

function visibilityIcon(mode: 'visible' | 'mixed' | 'background') {
  if (mode === 'visible') return <Eye size={15} className="text-[#5B7BFE]" />;
  if (mode === 'mixed') return <Layers3 size={15} className="text-emerald-600" />;
  return <Database size={15} className="text-amber-600" />;
}

function visibilityText(mode: 'visible' | 'mixed' | 'background') {
  if (mode === 'visible') return '你能直接看到';
  if (mode === 'mixed') return '界面和行为都会受影响';
  return '主要影响后台/配置';
}

function formatCommitDate(value: string) {
  if (!value) return '未知时间';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date);
}

export function CollabPreviewDialog({
  open,
  mode,
  preview,
  selectedPaths,
  conflictGroups,
  conflictDecisions,
  message,
  errorMessage,
  busy,
  onClose,
  onConflictDecisionChange,
  onSelectPullCommit,
  onMessageChange,
  onConfirm,
}: CollabPreviewDialogProps) {
  if (!open || !preview) return null;
  const selectedSet = new Set(selectedPaths);
  const hasConflicts = conflictGroups.length > 0;
  const decisionByGroup = new Map(conflictDecisions.map((decision) => [decision.groupId, decision.choice]));
  const allConflictsDecided = !hasConflicts || conflictGroups.every((group) => decisionByGroup.has(group.id));
  const actionLabel = hasConflicts
    ? '确认真实冲突怎么合并'
    : mode === 'push' ? '完整合并并推送我的修改' : '完整合并 main 修改到本机';
  const noPushChanges = mode === 'push' && preview.executionBlockReason === '当前没有可提交的本地文件改动。';
  const alreadySynced = mode === 'pull' && preview.executionBlockReason === 'main 当前已经是最新。';
  const confirmLabel = noPushChanges
    ? '当前已同步到 main'
    : alreadySynced
      ? '当前已经是最新版本'
      : hasConflicts
        ? '按选择完成合并'
        : mode === 'push'
          ? '完整合并并推到 main'
          : '完整合并 main 到本机';
  const confirmDisabled = busy || Boolean(preview.executionBlockReason) || (hasConflicts && !allConflictsDecided);

  return (
    <div className="fixed inset-0 z-[80] overflow-y-auto bg-black/30 px-4 py-8 backdrop-blur-sm">
      <div className="mx-auto flex min-h-full items-center justify-center">
      <div className="flex max-h-[calc(100vh-4rem)] w-full max-w-6xl flex-col overflow-hidden rounded-[28px] border border-white/70 bg-white shadow-[0_24px_90px_rgba(15,23,42,0.16)]">
        <div className="flex items-start justify-between gap-4 border-b border-gray-100 px-6 py-5">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-[#5B7BFE]">协作同步</p>
            <h2 className="mt-2 text-[22px] font-bold text-gray-900">{actionLabel}</h2>
            <p className="mt-2 text-[13px] leading-6 text-gray-500">
              当前仓库：{preview.status.repoName || '未命名仓库'} · 分支 {preview.status.branch || '未知'}
            </p>
          </div>
          <button
            type="button"
            className="rounded-2xl border border-gray-200 bg-white p-2 text-gray-400 transition hover:text-gray-700"
            onClick={busy ? undefined : onClose}
            aria-label="关闭协作预览"
          >
            <X size={18} />
          </button>
        </div>

        <div className="min-h-0 overflow-y-auto px-6 py-6">
        <div className="grid gap-6 lg:grid-cols-[1.25fr_0.75fr]">
          <div className="space-y-4">
            {preview.notice && (
              <div className="rounded-2xl border border-blue-200 bg-blue-50 px-4 py-3 text-[12px] font-semibold leading-6 text-[#4256C5]">
                <div className="flex items-start gap-2">
                  <AlertCircle size={16} className="mt-0.5 shrink-0" />
                  <span>{preview.notice}</span>
                </div>
              </div>
            )}

            {preview.executionBlockReason && (
              <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-[12px] font-semibold leading-6 text-amber-800">
                <div className="flex items-start gap-2">
                  <AlertCircle size={16} className="mt-0.5 shrink-0" />
                  <span>{preview.executionBlockReason}</span>
                </div>
              </div>
            )}

            {errorMessage && (
              <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-[12px] font-semibold leading-6 text-rose-800">
                <div className="flex items-start gap-2">
                  <AlertCircle size={16} className="mt-0.5 shrink-0" />
                  <span>{errorMessage}</span>
                </div>
              </div>
            )}

            {hasConflicts && (
              <div className="rounded-3xl border border-rose-100 bg-rose-50 px-4 py-4">
                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-rose-500">真实 Git 冲突</p>
                <p className="mt-2 text-[13px] leading-6 text-rose-700">
                  这些不是“同一文件被改过”的机械提醒，而是 Git 已经无法自动判断的冲突。请按用户功能理解后逐项选择。
                </p>
                <div className="mt-4 space-y-3">
                  {conflictGroups.map((group) => {
                    const currentChoice = decisionByGroup.get(group.id) || null;
                    const options: { choice: CollabConflictDecisionChoice; label: string; description: string; disabled?: boolean }[] = [
                      {
                        choice: 'keep_both',
                        label: '保留双方',
                        description: group.aiAvailable
                          ? '让软件 AI 尽量把本地和远端功能合在一起。'
                          : group.aiUnavailableReason || '当前 AI 合并不可用，暂不能选择。',
                        disabled: !group.aiAvailable,
                      },
                      {
                        choice: 'remote_main',
                        label: '采用远端 main',
                        description: '这组冲突按 GitHub main 上的版本处理。',
                      },
                      {
                        choice: 'local',
                        label: '采用本地修改',
                        description: '这组冲突按当前本机版本处理。',
                      },
                    ];
                    return (
                      <div key={group.id} className="rounded-[24px] border border-white/70 bg-white px-4 py-4 shadow-sm">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0 flex-1">
                            <p className="text-[15px] font-bold text-gray-900">{group.title}</p>
                            <p className="mt-2 text-[13px] leading-6 text-gray-600">{group.summary}</p>
                            <p className="mt-2 text-[12px] font-semibold text-rose-700">{group.operationHint}</p>
                          </div>
                          <span className="rounded-full bg-rose-50 px-3 py-1 text-[11px] font-bold text-rose-700 ring-1 ring-rose-100">
                            {group.paths.length} 个冲突文件
                          </span>
                        </div>
                        <div className="mt-4 grid gap-2 sm:grid-cols-3">
                          {options.map((option) => (
                            <button
                              key={option.choice}
                              type="button"
                              disabled={busy || option.disabled}
                              onClick={() => onConflictDecisionChange(group.id, option.choice)}
                              className={`rounded-2xl border px-3 py-3 text-left transition ${
                                currentChoice === option.choice
                                  ? 'border-[#5B7BFE] bg-[#5B7BFE]/[0.06] text-gray-900'
                                  : 'border-gray-100 bg-gray-50 text-gray-700 hover:border-[#5B7BFE]/30 hover:bg-white'
                              } disabled:cursor-not-allowed disabled:opacity-50`}
                            >
                              <p className="text-[13px] font-bold">{option.label}</p>
                              <p className="mt-1 text-[11px] leading-5 text-gray-500">{option.description}</p>
                            </button>
                          ))}
                        </div>
                        <details className="mt-3 rounded-2xl border border-gray-100 bg-gray-50 px-3 py-2">
                          <summary className="cursor-pointer text-[12px] font-bold text-gray-500">查看技术证据</summary>
                          <div className="mt-2 space-y-1">
                            {group.paths.map((targetPath) => (
                              <p key={targetPath} className="break-all text-[11px] text-gray-500">{targetPath}</p>
                            ))}
                          </div>
                        </details>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="rounded-3xl border border-gray-100 bg-gray-50 px-4 py-4">
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">你会先看到这些变化</p>
              <p className="mt-2 text-[13px] leading-6 text-gray-600">
                这里解释的是用户能感受到的功能变化。文件清单只作为技术证据，不再用于决定哪些功能进来。
              </p>
              <div className="mt-4 grid gap-3">
                {preview.effects.map((effect) => {
                  const selectedCount = effect.relatedPaths.filter((targetPath) => selectedSet.has(targetPath)).length;
                  return (
                    <div
                      key={effect.id}
                      className="rounded-[24px] border border-[#5B7BFE]/20 bg-white px-4 py-4 shadow-[0_12px_28px_rgba(91,123,254,0.08)]"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            {visibilityIcon(effect.visibility)}
                            <p className="text-[15px] font-bold text-gray-900">{effect.title}</p>
                            <span className="rounded-full bg-gray-50 px-2.5 py-1 text-[11px] font-semibold text-gray-500 ring-1 ring-gray-200">
                              {effect.scopeLabel}
                            </span>
                            <span className="rounded-full bg-gray-50 px-2.5 py-1 text-[11px] font-semibold text-gray-500 ring-1 ring-gray-200">
                              {visibilityText(effect.visibility)}
                            </span>
                          </div>
                          <p className="mt-2 text-[13px] leading-6 text-gray-600">{effect.summary}</p>
                        </div>
                      </div>

                      {effect.details.length > 0 && (
                        <div className="mt-4 space-y-2">
                          {effect.details.map((detail) => (
                            <div key={detail} className="flex items-start gap-2 text-[12px] leading-6 text-gray-600">
                              <span className="mt-[9px] h-1.5 w-1.5 rounded-full bg-[#5B7BFE]" />
                              <span>{detail}</span>
                            </div>
                          ))}
                        </div>
                      )}

                      <p className="mt-4 text-[12px] text-gray-400">
                        这组功能变化对应 {effect.relatedPaths.length} 个底层文件，完整合并会一起处理{selectedCount > 0 ? `（当前预览覆盖 ${selectedCount} 个）` : ''}。
                      </p>
                    </div>
                  );
                })}
                {preview.effects.length === 0 && (
                  <div className="rounded-2xl border border-dashed border-gray-200 bg-white px-4 py-4 text-[13px] leading-6 text-gray-500">
                    这次改动还没有被翻译成直观的软件效果，暂时只能通过下方文件清单确认。
                  </div>
                )}
              </div>
            </div>

            {mode === 'pull' && 'remoteCommits' in preview && preview.remoteCommits.length > 0 && (
              <div className="rounded-3xl border border-gray-100 bg-white px-4 py-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">按提交时间选择同步范围</p>
                    <p className="mt-2 text-[13px] leading-6 text-gray-600">
                      每一张卡是一条 main 上尚未进入本地的提交。选择某条提交后，本次同步只截止到这条提交；后面的提交会留到下次再判断。
                    </p>
                    {preview.syncTargetLabel && (
                      <p className="mt-2 text-[12px] font-bold text-[#5B7BFE]">当前截止点：{preview.syncTargetLabel}</p>
                    )}
                  </div>
                  <ActionButton disabled={busy || !preview.syncTargetCommit} onClick={() => onSelectPullCommit?.(null)}>
                    同步到最新 main
                  </ActionButton>
                </div>
                <div className="mt-4 space-y-2">
                  {preview.remoteCommits.map((commit, index) => {
                    const isLatest = index === preview.remoteCommits.length - 1;
                    const isActive = preview.syncTargetCommit ? preview.syncTargetCommit === commit.hash : isLatest;
                    return (
                      <button
                        key={commit.hash}
                        type="button"
                        disabled={busy || isActive}
                        onClick={() => onSelectPullCommit?.(commit.hash)}
                        className={`w-full rounded-2xl border px-3 py-3 text-left transition ${
                          isActive
                            ? 'border-[#5B7BFE]/30 bg-[#5B7BFE]/[0.06] shadow-[0_10px_24px_rgba(91,123,254,0.10)]'
                            : 'border-gray-100 bg-gray-50 hover:border-[#5B7BFE]/30 hover:bg-white'
                        } disabled:cursor-default`}
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-bold text-gray-700 ring-1 ring-gray-200">
                            {formatCommitDate(commit.authoredAt)}
                          </span>
                          <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-bold text-[#5B7BFE] ring-1 ring-[#5B7BFE]/20">
                            {commit.shortHash}
                          </span>
                          {isLatest && (
                            <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-bold text-emerald-700 ring-1 ring-emerald-100">
                              最新
                            </span>
                          )}
                          {isActive && (
                            <span className="rounded-full bg-[#5B7BFE] px-2.5 py-1 text-[11px] font-bold text-white">
                              当前选择
                            </span>
                          )}
                        </div>
                        <p className="mt-2 text-[13px] font-bold leading-6 text-gray-900">{commit.subject || '未填写提交说明'}</p>
                        <p className="mt-1 text-[12px] leading-5 text-gray-500">
                          {commit.identityLabel} · {commit.sourceLabel} · {commit.fileCount} 个文件
                        </p>
                        {commit.changedPaths.length > 0 && (
                          <p className="mt-2 line-clamp-2 text-[11px] leading-5 text-gray-400">
                            {commit.changedPaths.slice(0, 6).join('、')}{commit.changedPaths.length > 6 ? ` 等 ${commit.changedPaths.length} 个文件` : ''}
                          </p>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <details className="rounded-3xl border border-gray-100 bg-white open:shadow-sm">
              <summary className="cursor-pointer list-none px-4 py-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">涉及文件</p>
                    <p className="mt-1 text-[12px] text-gray-500">这里只是技术证据，不能再逐文件取消，避免功能被拆散。</p>
                  </div>
                  <span className="rounded-full bg-[#5B7BFE]/10 px-3 py-1 text-[12px] font-bold text-[#5B7BFE]">
                    完整合并 {preview.files.length}
                  </span>
                </div>
              </summary>
              <div className="border-t border-gray-100 px-4 py-3">
                <div className="space-y-3">
                  {preview.files.map((file) => {
                    const linkedEffects = preview.effects
                      .filter((effect) => effect.relatedPaths.includes(file.path))
                      .map((effect) => effect.title);
                    return (
                      <div
                        key={file.path}
                        className="block rounded-2xl border border-gray-100 bg-gray-50/80 px-4 py-3"
                      >
                        <div className="flex items-start gap-3">
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="truncate text-[13px] font-bold text-gray-900">{file.path}</p>
                              <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-gray-500 ring-1 ring-gray-200">
                                {file.groupLabel}
                              </span>
                              <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-gray-500 ring-1 ring-gray-200">
                                {file.summary}
                              </span>
                            </div>
                            {linkedEffects.length > 0 && (
                              <p className="mt-2 text-[12px] text-gray-500">主要体现在：{linkedEffects.join('、')}</p>
                            )}
                            {file.previousPath && (
                              <p className="mt-2 text-[12px] text-gray-500">原路径：{file.previousPath}</p>
                            )}
                            {file.risk && (
                              <div className="mt-3 rounded-2xl border border-rose-100 bg-rose-50 px-3 py-3">
                                <div className="flex items-start gap-2 text-[12px] font-semibold text-rose-700">
                                  <AlertCircle size={15} className="mt-0.5 shrink-0" />
                                  <span>这只是文件重叠风险提示；真正冲突以 Git 合并结果为准。{file.risk.message}</span>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </details>
          </div>

          <div className="space-y-4">
            <div className="rounded-3xl border border-gray-100 bg-gray-50 px-4 py-4">
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">本次主要修改</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {preview.groups.map((group) => (
                  <span
                    key={group.key}
                    className="rounded-full border border-gray-200 bg-white px-3 py-1.5 text-[12px] font-bold text-gray-700"
                  >
                    {group.label} · {group.fileCount}
                  </span>
                ))}
                {preview.groups.length === 0 && (
                  <span className="text-[12px] text-gray-400">当前没有可操作的文件。</span>
                )}
              </div>
            </div>

            <div className="rounded-3xl border border-gray-100 bg-gray-50 px-4 py-4">
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">提交说明</p>
              <textarea
                value={message}
                onChange={(event) => onMessageChange(event.target.value)}
                disabled={busy}
                rows={4}
                className="mt-3 w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-semibold text-gray-700 outline-none transition focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/20"
                placeholder={preview.suggestedMessage}
              />
              <p className="mt-2 text-[12px] text-gray-400">默认会先填好建议说明，你也可以手动修改。</p>
            </div>

            <div className="rounded-3xl border border-gray-100 bg-white px-4 py-4">
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">执行前提醒</p>
              <div className="mt-3 space-y-3 text-[12px] leading-6 text-gray-600">
                <div className="flex items-start gap-2">
                  <CheckCircle2 size={15} className="mt-1 shrink-0 text-emerald-500" />
                  <span>现在先看“用户功能会怎么变”，文件清单只作为第二层证据。</span>
                </div>
                <div className="flex items-start gap-2">
                  <CheckCircle2 size={15} className="mt-1 shrink-0 text-emerald-500" />
                  <span>{hasConflicts ? '确认后会按你选择的方式解决真实冲突。' : mode === 'push' ? '确认后会完整合并本地修改与远端 main，再推送。' : '确认后会完整合并远端 main 与本地修改。'}</span>
                </div>
                <div className="flex items-start gap-2">
                  <AlertCircle size={15} className="mt-1 shrink-0 text-amber-500" />
                  <span>不会再因为文件重叠就默认跳过功能；只有真实 Git 冲突才进入三选一。</span>
                </div>
                {mode === 'pull' && (
                  <div className="flex items-start gap-2">
                    <AlertCircle size={15} className="mt-1 shrink-0 text-amber-500" />
                    <span>同步完成后，你还可以决定是否顺手自动更新当前安装版。</span>
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-3xl border border-gray-100 bg-white px-4 py-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">确认执行</p>
                  <p className="mt-1 text-[12px] text-gray-500">
                    {hasConflicts
                      ? allConflictsDecided
                        ? '所有冲突都已选择处理方式。'
                        : '还有冲突未选择处理方式。'
                      : `将完整处理 ${preview.files.length} 个底层文件，不做文件级跳过。`}
                  </p>
                </div>
                {mode === 'push' ? <UploadCloud size={18} className="text-[#5B7BFE]" /> : <Download size={18} className="text-[#5B7BFE]" />}
              </div>
              <div className="mt-4 flex flex-wrap justify-end gap-3">
                <ActionButton onClick={busy ? undefined : onClose}>取消</ActionButton>
                <ActionButton primary disabled={confirmDisabled} onClick={onConfirm}>
                  {busy ? <RefreshCw size={14} className="animate-spin" /> : mode === 'push' ? <UploadCloud size={14} /> : <Download size={14} />}
                  {confirmLabel}
                </ActionButton>
              </div>
            </div>
          </div>
        </div>
        </div>
      </div>
      </div>
    </div>
  );
}
