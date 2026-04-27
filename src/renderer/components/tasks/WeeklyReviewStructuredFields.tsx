import { Check, Circle, X } from 'lucide-react';
import type { TaskStatus, WeeklyReviewTaskStructuredNote } from '../../../shared/types';

const LIGHTWEIGHT_TAGS = ['资料不足', '等待他人', '方向不清', '资源不够', '工作过度饱和'] as const;

const GROWTH_HINT_RULES = [
  { key: 'exec', label: '推进执行', keywords: ['推进', '闭环', '行动项', '排期', '拆解', '跟进', '完成', '延期'] },
  { key: 'collab', label: '协作沟通', keywords: ['协作', '沟通', '对齐', '会议', '负责人', '跨组', '边界', '配合'] },
  { key: 'analyze', label: '分析判断', keywords: ['分析', '判断', '原因', '本质', '结论', '规律', '为什么'] },
  { key: 'insight', label: '客户洞察', keywords: ['客户', '用户', '访谈', '需求', '顾虑', '诉求', '反馈'] },
  { key: 'risk', label: '风险识别', keywords: ['风险', '阻碍', '卡点', '依赖', '预警', '退回', '失败'] },
  { key: 'write', label: '写作表达', keywords: ['模板', '方法', '清单', '沉淀', '复用', '记录', '总结'] },
] as const;

export function createEmptyReviewStructuredNote(): WeeklyReviewTaskStructuredNote {
  return {
    reflection: '',
    lightweightTag: '',
    planCommitment: '',
    progress: '',
    completionStatus: 'in_progress',
    departmentPlanId: null,
    departmentPlanAlignment: 'unknown',
    organizationPlanId: null,
    organizationPlanAlignment: 'unknown',
    successReason: '',
    successExperience: '',
    blockerReason: '',
    failureInsight: '',
    supportNeeded: '',
    nextAction: '',
  };
}

function reviewModeFromValue(value: WeeklyReviewTaskStructuredNote, taskStatus?: TaskStatus) {
  if (taskStatus === 'done') return 'done' as const;
  if (value.completionStatus === 'done_on_time' || value.completionStatus === 'done_late') return 'done' as const;
  return 'pending' as const;
}

function normalizeSimpleReviewText(text: string) {
  return text
    .replace(/^任务完成心得：\s*/, '')
    .replace(/^需要支持\s*\/\s*思考：\s*/, '')
    .replace(/^支持需求：\s*/, '')
    .replace(/^失败心得：\s*/, '')
    .replace(/^阻碍原因：\s*/, '')
    .replace(/^本周推进：\s*/, '')
    .trim();
}

function detectGrowthHints(text: string) {
  const normalized = normalizeSimpleReviewText(text);
  if (!normalized) return [];
  return GROWTH_HINT_RULES.filter((rule) => rule.keywords.some((keyword) => normalized.includes(keyword))).map((rule) => rule.label);
}

function detectContributionPremiumHint(text: string) {
  const normalized = normalizeSimpleReviewText(text);
  if (!normalized) return null;
  if (['模板', '复用', '流程', '规则', '机制', '统一'].some((keyword) => normalized.includes(keyword))) {
    return '这条复盘有机会拿到 30%-50% 的组织贡献溢价';
  }
  if (['协作', '会议', '负责人', '时间点', '边界', '支持', '帮助', '风险', '预警'].some((keyword) => normalized.includes(keyword))) {
    return '这条复盘有机会拿到 20%-40% 的组织贡献溢价';
  }
  return null;
}

export function getSimpleReviewText(value: WeeklyReviewTaskStructuredNote, taskStatus?: TaskStatus) {
  if (value.reflection.trim()) {
    return normalizeSimpleReviewText(value.reflection);
  }
  const mode = reviewModeFromValue(value, taskStatus);
  const candidates = mode === 'done'
    ? [
        value.successExperience.trim(),
        value.successReason.trim(),
        value.progress.trim(),
        value.nextAction.trim(),
      ]
    : [
        value.supportNeeded.trim(),
        value.failureInsight.trim(),
        value.blockerReason.trim(),
        value.progress.trim(),
        value.nextAction.trim(),
      ];
  return normalizeSimpleReviewText(candidates.find(Boolean) || '');
}

export function applySimpleReviewText(
  value: WeeklyReviewTaskStructuredNote,
  nextText: string,
  taskStatus?: TaskStatus,
): WeeklyReviewTaskStructuredNote {
  const trimmed = nextText.trim();
  const mode = reviewModeFromValue(value, taskStatus);
  if (mode === 'done') {
    return {
      ...value,
      completionStatus: value.completionStatus === 'done_late' ? 'done_late' : 'done_on_time',
      reflection: trimmed,
    };
  }
  return {
    ...value,
    completionStatus: value.completionStatus === 'not_done' ? 'not_done' : 'in_progress',
    reflection: trimmed,
  };
}

export function hasMeaningfulReviewStructuredNote(value: WeeklyReviewTaskStructuredNote) {
  return [
    value.reflection.trim(),
    value.lightweightTag,
    value.planCommitment.trim(),
    value.progress.trim(),
    value.departmentPlanId || '',
    value.organizationPlanId || '',
    value.successReason.trim(),
    value.successExperience.trim(),
    value.blockerReason.trim(),
    value.failureInsight.trim(),
    value.supportNeeded.trim(),
    value.nextAction.trim(),
    value.completionStatus !== 'in_progress' ? value.completionStatus : '',
    value.departmentPlanAlignment !== 'unknown' ? value.departmentPlanAlignment : '',
    value.organizationPlanAlignment !== 'unknown' ? value.organizationPlanAlignment : '',
  ].some(Boolean);
}

export function composeReviewNoteFromStructuredFields(value: WeeklyReviewTaskStructuredNote, taskStatus?: TaskStatus) {
  const text = getSimpleReviewText(value, taskStatus);
  const tagSuffix = reviewModeFromValue(value, taskStatus) === 'pending' && value.lightweightTag
    ? `（当前卡点：${value.lightweightTag}）`
    : '';
  if (!text && tagSuffix) {
    return `需要支持 / 思考：${value.lightweightTag}`;
  }
  if (!text) return '';
  return reviewModeFromValue(value, taskStatus) === 'done'
    ? `任务完成心得：${text}`
    : `需要支持 / 思考：${text}${tagSuffix}`;
}

type WeeklyReviewStructuredFieldsProps = {
  scope: 'work' | 'personal';
  value: WeeklyReviewTaskStructuredNote;
  taskStatus: TaskStatus;
  onChange: (nextValue: WeeklyReviewTaskStructuredNote) => void;
  onSave?: () => void;
  isSaving?: boolean;
  saveDisabled?: boolean;
  saveSucceeded?: boolean;
  onStatusChange?: (nextStatus: 'done' | 'delayed' | 'cancelled') => void;
  isStatusChanging?: boolean;
  statusScopeLabel?: string;
  textareaLabel?: string;
  reflectionPlaceholder?: string;
};

export function WeeklyReviewStructuredFields({
  scope,
  value,
  taskStatus,
  onChange,
  onSave,
  isSaving = false,
  saveDisabled = false,
  saveSucceeded = false,
  onStatusChange,
  isStatusChanging = false,
  statusScopeLabel = '本条任务状态',
  textareaLabel: textareaLabelOverride,
  reflectionPlaceholder,
}: WeeklyReviewStructuredFieldsProps) {
  const mode = reviewModeFromValue(value, taskStatus);
  const helperLabel = mode === 'done'
    ? '已完成'
    : taskStatus === 'rejected'
      ? '已取消'
      : value.completionStatus === 'not_done'
        ? '已延迟'
        : taskStatus === 'doing'
          ? '仍在推进'
          : '未完成 / 逾期';
  const textareaLabel = textareaLabelOverride || (mode === 'done' ? '完成心得' : '需要支持 / 这周思考');
  const placeholder = mode === 'done'
    ? '任务完成了，有什么心得？'
    : scope === 'work'
      ? '这项任务还没收口，需要什么支持，或者有什么思考？'
      : '这件事还没推进完，需要什么支持，或者有什么思考？';
  const resolvedPlaceholder = reflectionPlaceholder?.trim() || placeholder;
  const currentValue = getSimpleReviewText(value, taskStatus);
  const growthHints = detectGrowthHints(currentValue);
  const contributionPremiumHint = detectContributionPremiumHint(currentValue);
  const saveButtonState = isSaving ? 'saving' : saveSucceeded ? 'saved' : saveDisabled ? 'disabled' : 'ready';
  const selectedStatus =
    taskStatus === 'done'
      ? 'done'
      : taskStatus === 'rejected'
        ? 'cancelled'
        : value.completionStatus === 'not_done'
          ? 'delayed'
          : null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex items-center gap-2 rounded-full bg-gray-100 px-3 py-1.5 text-[11px] font-bold text-gray-500">
          <span className={`h-2 w-2 rounded-full ${mode === 'done' ? 'bg-emerald-400' : taskStatus === 'rejected' ? 'bg-rose-400' : value.completionStatus === 'not_done' ? 'bg-amber-400' : 'bg-amber-300'}`} />
          系统识别：{helperLabel}
        </div>
        {onStatusChange ? (
          <div className="flex flex-wrap items-center justify-end gap-2">
            <span className="text-[11px] font-bold uppercase tracking-[0.16em] text-gray-400">{statusScopeLabel}</span>
            <button
              type="button"
              onClick={() => onStatusChange('done')}
              disabled={isStatusChanging}
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] font-bold transition ${
                selectedStatus === 'done'
                  ? 'border-emerald-300 bg-emerald-50 text-emerald-700'
                  : 'border-gray-200 bg-white text-gray-500 hover:border-emerald-200 hover:text-emerald-700'
              } ${isStatusChanging ? 'cursor-not-allowed opacity-60' : ''}`}
            >
              <Check size={13} />
              <span>完成</span>
            </button>
            <button
              type="button"
              onClick={() => onStatusChange('delayed')}
              disabled={isStatusChanging}
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] font-bold transition ${
                selectedStatus === 'delayed'
                  ? 'border-amber-300 bg-amber-50 text-amber-700'
                  : 'border-gray-200 bg-white text-gray-500 hover:border-amber-200 hover:text-amber-700'
              } ${isStatusChanging ? 'cursor-not-allowed opacity-60' : ''}`}
            >
              <Circle size={13} />
              <span>延迟</span>
            </button>
            <button
              type="button"
              onClick={() => onStatusChange('cancelled')}
              disabled={isStatusChanging}
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] font-bold transition ${
                selectedStatus === 'cancelled'
                  ? 'border-rose-300 bg-rose-50 text-rose-700'
                  : 'border-gray-200 bg-white text-gray-500 hover:border-rose-200 hover:text-rose-700'
              } ${isStatusChanging ? 'cursor-not-allowed opacity-60' : ''}`}
            >
              <X size={13} />
              <span>取消</span>
            </button>
          </div>
        ) : null}
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between gap-3">
          <p className="text-[12px] font-bold text-gray-700">{textareaLabel}</p>
          {onSave ? (
            <button
              type="button"
              onClick={onSave}
              disabled={isSaving || saveDisabled}
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] font-bold transition ${
                saveButtonState === 'disabled'
                  ? 'cursor-not-allowed border-gray-200 bg-gray-100 text-gray-400'
                  : saveButtonState === 'saved'
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                    : 'border-[#DCE7FF] bg-[#F8FAFF] text-[#335CFF] hover:border-[#BFD2FF] hover:bg-[#EEF4FF]'
              }`}
            >
              <span className="text-[13px] leading-none">{isSaving ? '…' : '✓'}</span>
              <span>{isSaving ? '保存中' : saveSucceeded ? '已保存' : '保存'}</span>
            </button>
          ) : null}
        </div>
        <textarea
          value={currentValue}
          onChange={(event) => onChange(applySimpleReviewText(value, event.target.value, taskStatus))}
          placeholder={resolvedPlaceholder}
          className="w-full min-h-[96px] rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] leading-6 text-gray-800 outline-none placeholder:text-gray-400"
        />
      </div>

      {mode === 'pending' ? (
        <div className="space-y-2">
          <p className="text-[12px] font-bold text-gray-700">当前主要卡点（可不选）</p>
          <div className="flex flex-wrap gap-2">
            {LIGHTWEIGHT_TAGS.map((tag) => {
              const active = value.lightweightTag === tag;
              return (
                <button
                  key={tag}
                  type="button"
                  onClick={() => onChange({ ...value, lightweightTag: active ? '' : tag })}
                  className={`rounded-full border px-3 py-1.5 text-[12px] font-semibold transition ${
                    active
                      ? 'border-[#5B7BFE] bg-[#EEF4FF] text-[#335CFF]'
                      : 'border-gray-200 bg-white text-gray-500 hover:border-gray-300 hover:text-gray-800'
                  }`}
                >
                  {tag}
                </button>
              );
            })}
          </div>
        </div>
      ) : null}

      {growthHints.length ? (
        <div className="space-y-2">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-gray-400">识别到的成长点</p>
          <div className="flex flex-wrap gap-2">
            {growthHints.map((label) => (
              <span key={label} className="rounded-full bg-[#EEF4FF] px-3 py-1 text-[11px] font-semibold text-[#335CFF]">
                {label}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {contributionPremiumHint ? (
        <div className="rounded-2xl border border-[#DCE7FF] bg-[#F8FAFF] px-4 py-3 text-[12px] font-medium leading-6 text-[#335CFF]">
          {contributionPremiumHint}
        </div>
      ) : null}
    </div>
  );
}
