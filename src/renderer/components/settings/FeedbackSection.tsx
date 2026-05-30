import React, { useState } from 'react';
import {
  MessageSquarePlus,
  ChevronDown,
  Camera,
  ShieldCheck,
  Send,
  CheckCircle2,
} from 'lucide-react';
import type { DesktopAppInfo } from '../../../shared/types';

/**
 * 软件内「报错 / 建议」入口 + 「我的反馈」列表。
 * 本阶段纯界面 mock:提交只走本地 state,不接数据。
 * 接入数据后:提交 → POST /api/v1/software-feedback(经桌面 backend proxy);
 * 列表 ← GET /api/v1/software-feedback?status=...(只看自己提交的)。
 */

type FeedbackCategory = 'bug' | 'lag' | 'inaccurate' | 'suggestion';
type FeedbackSeverity = 'normal' | 'affecting' | 'blocking';

const CATEGORIES: ReadonlyArray<{ key: FeedbackCategory; label: string }> = [
  { key: 'bug', label: '报错' },
  { key: 'lag', label: '卡顿' },
  { key: 'inaccurate', label: '结果不准' },
  { key: 'suggestion', label: '功能建议' },
];

const SEVERITIES: ReadonlyArray<{ key: FeedbackSeverity; label: string }> = [
  { key: 'normal', label: '一般' },
  { key: 'affecting', label: '影响使用' },
  { key: 'blocking', label: '用不了' },
];

interface MyFeedbackItem {
  readonly id: string;
  readonly title: string;
  readonly categoryLabel: string;
  readonly statusLabel: string;
  readonly tone: string;
  readonly submittedAt: string;
}

const MOCK_MY_FEEDBACK: readonly MyFeedbackItem[] = [
  { id: 'fb-1', title: '战略陪伴页状态偶尔闪回', categoryLabel: '报错', statusLabel: '修复中', tone: 'bg-indigo-50 text-indigo-700', submittedAt: '2026-05-29' },
  { id: 'fb-2', title: '希望任务支持批量改期', categoryLabel: '功能建议', statusLabel: '下版发布', tone: 'bg-sky-50 text-sky-700', submittedAt: '2026-05-27' },
  { id: 'fb-3', title: '导入大文件时转圈很久', categoryLabel: '卡顿', statusLabel: '已确认', tone: 'bg-amber-50 text-amber-700', submittedAt: '2026-05-24' },
];

interface ChipProps {
  active: boolean;
  label: string;
  onClick: () => void;
}

function Chip({ active, label, onClick }: ChipProps): React.ReactElement {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        'rounded-full border px-3 py-1.5 text-[12px] transition ' +
        (active
          ? 'border-[#5B7BFE] bg-[#5B7BFE]/8 font-medium text-[#3A53C5]'
          : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50')
      }
    >
      {label}
    </button>
  );
}

interface FeedbackSectionProps {
  desktopAppInfo: DesktopAppInfo | null;
}

export function FeedbackSection({ desktopAppInfo }: FeedbackSectionProps): React.ReactElement {
  const [formOpen, setFormOpen] = useState(false);
  const [category, setCategory] = useState<FeedbackCategory>('bug');
  const [severity, setSeverity] = useState<FeedbackSeverity>('normal');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [attachScreenshot, setAttachScreenshot] = useState(true);
  const [contextOpen, setContextOpen] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [listOpen, setListOpen] = useState(false);

  const versionLabel = desktopAppInfo?.appVersion ?? '未知';
  const platformLabel = desktopAppInfo ? `${desktopAppInfo.platform} · ${desktopAppInfo.arch}` : '未知';

  const resetForm = () => {
    setCategory('bug');
    setSeverity('normal');
    setTitle('');
    setDescription('');
    setAttachScreenshot(true);
    setContextOpen(false);
    setSubmitted(false);
  };

  const handleSubmit = () => {
    if (!title.trim()) return;
    // 纯界面阶段:不接数据,只本地标记已提交
    setSubmitted(true);
  };

  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">FEEDBACK</p>
          <h3 className="mt-2 text-[18px] font-light tracking-tight text-gray-900">报错 / 建议</h3>
          <p className="mt-1.5 text-[12px] leading-relaxed text-gray-500">
            用着不顺、报错、或者有想法,都可以直接告诉我们。提交时会自动带上当前版本、页面等信息帮助定位。
          </p>
        </div>
        {!formOpen && (
          <button
            type="button"
            onClick={() => setFormOpen(true)}
            className="inline-flex shrink-0 items-center gap-2 rounded-md bg-[#5B7BFE] px-4 py-2 text-[13px] font-medium text-white hover:bg-[#4A6AEF]"
          >
            <MessageSquarePlus size={14} />
            写一条反馈
          </button>
        )}
      </div>

      {/* 就地展开的表单 */}
      {formOpen && !submitted && (
        <div className="mt-5 space-y-4">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-gray-400">类型</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {CATEGORIES.map((c) => (
                <Chip key={c.key} active={category === c.key} label={c.label} onClick={() => setCategory(c.key)} />
              ))}
            </div>
          </div>

          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-gray-400">程度</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {SEVERITIES.map((s) => (
                <Chip key={s.key} active={severity === s.key} label={s.label} onClick={() => setSeverity(s.key)} />
              ))}
            </div>
          </div>

          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-gray-400">一句话标题</p>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="例如:战略陪伴页刷新后状态闪回"
              className="mt-2 w-full rounded-md border border-gray-200 px-3 py-2 text-[13px] text-gray-800 outline-none focus:border-[#5B7BFE]"
            />
          </div>

          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-gray-400">详细描述(可选)</p>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="发生了什么、怎么复现、期望是什么…"
              className="mt-2 w-full resize-none rounded-md border border-gray-200 px-3 py-2 text-[13px] text-gray-800 outline-none focus:border-[#5B7BFE]"
            />
          </div>

          {/* 自动附带上下文 */}
          <div className="rounded-lg border border-gray-100 bg-gray-50/60 p-3">
            <button
              type="button"
              onClick={() => setContextOpen((v) => !v)}
              className="flex w-full items-center justify-between text-left"
            >
              <span className="text-[12px] text-gray-600">已自动附带:版本 {versionLabel} · 当前页面 · 系统 · 最近报错</span>
              <ChevronDown size={14} className={`shrink-0 text-gray-400 transition ${contextOpen ? 'rotate-180' : ''}`} />
            </button>
            {contextOpen && (
              <dl className="mt-3 grid grid-cols-2 gap-2 text-[12px]">
                <div><dt className="text-gray-400">版本</dt><dd className="text-gray-700">{versionLabel}</dd></div>
                <div><dt className="text-gray-400">系统</dt><dd className="text-gray-700">{platformLabel}</dd></div>
                <div><dt className="text-gray-400">当前页面</dt><dd className="text-gray-700">关于本软件</dd></div>
                <div><dt className="text-gray-400">最近报错</dt><dd className="text-gray-700">暂无</dd></div>
              </dl>
            )}
            <label className="mt-3 flex cursor-pointer items-center gap-2 text-[12px] text-gray-600">
              <input
                type="checkbox"
                checked={attachScreenshot}
                onChange={(e) => setAttachScreenshot(e.target.checked)}
                className="h-3.5 w-3.5 accent-[#5B7BFE]"
              />
              <Camera size={13} className="text-gray-400" />
              附当前界面截图
            </label>
            <p className="mt-2 flex items-center gap-1.5 text-[11px] text-gray-400">
              <ShieldCheck size={12} />
              客户名等敏感信息不会上报,仅传客户内部编号用于定位。
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!title.trim()}
              className="inline-flex items-center gap-2 rounded-md bg-[#5B7BFE] px-4 py-2 text-[13px] font-medium text-white hover:bg-[#4A6AEF] disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Send size={14} />
              提交
            </button>
            <button
              type="button"
              onClick={() => { setFormOpen(false); resetForm(); }}
              className="text-[12px] text-gray-400 hover:text-gray-600"
            >
              取消
            </button>
          </div>
        </div>
      )}

      {/* 提交成功(mock) */}
      {formOpen && submitted && (
        <div className="mt-5 flex items-start gap-2 rounded-md bg-emerald-50 px-3 py-3 text-[12px] text-emerald-700">
          <CheckCircle2 size={14} className="mt-[2px] shrink-0" />
          <div>
            <p className="font-medium">已收到,谢谢反馈!</p>
            <p className="mt-0.5 text-emerald-600">我们会在「我的反馈」里同步处理进度。</p>
            <button
              type="button"
              onClick={resetForm}
              className="mt-2 text-[12px] font-medium text-emerald-700 underline underline-offset-2"
            >
              再写一条
            </button>
          </div>
        </div>
      )}

      {/* 我的反馈 列表 */}
      <div className="mt-6 border-t border-gray-100 pt-4">
        <button
          type="button"
          onClick={() => setListOpen((v) => !v)}
          className="flex w-full items-center justify-between text-left"
        >
          <span className="text-[13px] font-medium text-gray-700">我的反馈 · {MOCK_MY_FEEDBACK.length}</span>
          <ChevronDown size={15} className={`text-gray-400 transition ${listOpen ? 'rotate-180' : ''}`} />
        </button>
        {listOpen && (
          <ul className="mt-3 space-y-2">
            {MOCK_MY_FEEDBACK.map((item) => (
              <li key={item.id} className="flex items-center justify-between gap-3 rounded-lg border border-gray-100 px-3 py-2.5">
                <div className="min-w-0">
                  <p className="truncate text-[13px] text-gray-800">{item.title}</p>
                  <p className="mt-0.5 text-[11px] text-gray-400">{item.categoryLabel} · {item.submittedAt}</p>
                </div>
                <span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium ${item.tone}`}>
                  {item.statusLabel}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
