import React, { useImperativeHandle, useRef, useState } from 'react';
import {
  Sparkles,
  Wand2,
  FileText,
  Languages,
  PenTool as PenToolIcon,
  Type,
  Palette,
  Download,
  History,
  Users as UsersIcon,
  Maximize2,
  Table as TableIcon,
  Image as ImageIcon,
  Link as LinkIcon,
  Scale,
  ShieldCheck,
  Loader2,
  X,
  Play,
} from 'lucide-react';

import type { DocumentAiAction, DocumentAiCreativityMode } from '../../lib/api';

export type RichTextDocumentEditorWritingSkill = {
  id: string;
  name: string;
};

export type RichTextDocumentEditorAiOpts = {
  userRequest: string;
  creativityMode: DocumentAiCreativityMode;
  activeSkillId: string | null;
  // P14a：当前用户在编辑器里框选的纯文本（window.getSelection()）。
  // 非空 → 后端只处理这段、前端只替换这段；空 → 处理整篇。
  selectionText: string;
};

// P14a：onAiAction 的返回值。
// targetScope = "selection" → 前端用 insertMarkdown 只替换选区
// targetScope = "full_doc"  → 前端用 setMarkdown 整篇替换
// 不返回（undefined）→ App 层已经自己处理过（兼容 __export_docx / __toggle_fullscreen）
export type RichTextDocumentEditorAiResult = {
  content: string;
  targetScope: 'selection' | 'full_doc';
};

import {
  MDXEditor,
  type MDXEditorMethods,
  headingsPlugin,
  listsPlugin,
  quotePlugin,
  thematicBreakPlugin,
  markdownShortcutPlugin,
  linkPlugin,
  linkDialogPlugin,
  tablePlugin,
  imagePlugin,
  toolbarPlugin,
  BoldItalicUnderlineToggles,
  StrikeThroughSupSubToggles,
  BlockTypeSelect,
  UndoRedo,
  ListsToggle,
} from '@mdxeditor/editor';
import '@mdxeditor/editor/style.css';

/**
 * 客户工作台内嵌"WPS / Word 风格"文档编辑器。
 *
 * Ribbon UI：5 个 tab，模仿 Word 的功能组分布
 *   开始     —— 字体/段落/列表（全 wire，复用 MDXEditor primitives）
 *   插入     —— 表格/图片/链接/代码块/分割线（全 wire）
 *   AI 助手  —— 扩写/改写/总结/翻译/风格切换（stub，下一步打通 AI）
 *   文档     —— 历史/版本/导出/可见性（stub）
 *   样式     —— 主题色/字号（stub）
 *
 * MDXEditor primitives（BoldItalicUnderlineToggles 等）必须在 toolbarPlugin
 * 的 toolbarContents 里渲染，否则没 lexical context 会崩——所以整个 ribbon UI
 * 也必须包在 toolbarContents 内。
 */
export type RichTextDocumentEditorProps = {
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  /** 强制最小高度（默认 360px） */
  minHeight?: number;
  /** 是否禁用编辑（保存中可以传 true） */
  readOnly?: boolean;
  /**
   * AI action 执行回调。
   * - action ∈ DocumentAiAction：调 backend，**应该 return 后端结果**（编辑器据此决定替换选区还是替换全文）。
   * - action='__export_docx' / '__toggle_fullscreen' 等本地动作：App 层自己处理，返回 void/undefined 即可。
   * opts.selectionText 是用户当前框选的纯文本，由编辑器组件在调用前抓取塞进来。
   */
  onAiAction?: (
    action: string,
    opts?: RichTextDocumentEditorAiOpts,
  ) => Promise<RichTextDocumentEditorAiResult | void> | RichTextDocumentEditorAiResult | void;
  /** 写作风格 skill 列表（来自 listWritingSkills 接口） */
  writingSkills?: RichTextDocumentEditorWritingSkill[];
  /** 默认选中的 skill id（从外部 chat 同步） */
  defaultActiveSkillId?: string | null;
  /** 默认写作模式（从外部 chat 同步） */
  defaultCreativityMode?: DocumentAiCreativityMode;
};

// P12：字号 + 主题 内置 state（不污染 App.tsx）
type EditorFontSize = 'sm' | 'md' | 'lg' | 'xl';
type EditorTheme = 'light' | 'sepia' | 'dark';

const FONT_SIZE_CLASS: Record<EditorFontSize, string> = {
  sm: 'text-[13px] leading-6',
  md: 'text-[14px] leading-7',
  lg: 'text-[16px] leading-8',
  xl: 'text-[18px] leading-9',
};
const FONT_SIZE_LABEL: Record<EditorFontSize, string> = {
  sm: '小', md: '中', lg: '大', xl: '特大',
};

const THEME_WRAPPER_CLASS: Record<EditorTheme, string> = {
  light: 'bg-white',
  sepia: 'bg-[#FBF7EC]',
  dark: 'bg-slate-900',
};
const THEME_CONTENT_CLASS: Record<EditorTheme, string> = {
  light: 'text-gray-900',
  sepia: 'text-stone-800',
  dark: 'text-slate-100 prose-invert',
};
const THEME_LABEL: Record<EditorTheme, string> = {
  light: '默认', sepia: '米黄', dark: '暗夜',
};

export const RichTextDocumentEditor = React.forwardRef<MDXEditorMethods, RichTextDocumentEditorProps>(
  function RichTextDocumentEditor(
    {
      value,
      onChange,
      placeholder,
      minHeight = 360,
      readOnly = false,
      onAiAction,
      writingSkills,
      defaultActiveSkillId,
      defaultCreativityMode,
    },
    ref,
  ) {
    const editorRef = useRef<MDXEditorMethods>(null);
    useImperativeHandle(ref, () => editorRef.current as MDXEditorMethods, []);
    const [fontSize, setFontSize] = useState<EditorFontSize>('md');
    const [theme, setTheme] = useState<EditorTheme>('light');

    const contentClass = `prose prose-sm mx-auto max-w-[880px] px-10 py-10 min-h-[480px] outline-none ${FONT_SIZE_CLASS[fontSize]} ${THEME_CONTENT_CLASS[theme]}`;

    return (
      <div
        className={`transition ${THEME_WRAPPER_CLASS[theme]}`}
        style={{ minHeight }}
      >
        <MDXEditor
          ref={editorRef}
          markdown={value}
          onChange={onChange}
          placeholder={placeholder || '把文档贴在这里，或直接开始写。⌘B 加粗、⌘I 斜体；从飞书/网页粘贴时格式保留。'}
          readOnly={readOnly}
          contentEditableClassName={contentClass}
          plugins={[
            headingsPlugin(),
            listsPlugin(),
            quotePlugin(),
            thematicBreakPlugin(),
            linkPlugin(),
            linkDialogPlugin(),
            tablePlugin(),
            imagePlugin(),
            markdownShortcutPlugin(),
            toolbarPlugin({
              toolbarClassName:
                'sticky top-0 z-20 border-b border-gray-200 bg-white px-0 py-0 flex flex-col items-stretch',
              toolbarContents: () => (
                <RibbonToolbar
                  onAiAction={onAiAction}
                  editorRef={editorRef}
                  notifyContentChange={onChange}
                  writingSkills={writingSkills || []}
                  defaultActiveSkillId={defaultActiveSkillId ?? null}
                  defaultCreativityMode={defaultCreativityMode ?? 'balanced'}
                  fontSize={fontSize}
                  setFontSize={setFontSize}
                  theme={theme}
                  setTheme={setTheme}
                />
              ),
            }),
          ]}
        />
      </div>
    );
  },
);

// ─── Ribbon Toolbar ───────────────────────────────────────────────
// 模仿 Word/WPS 顶部多 tab 工具栏。MDXEditor primitives（B I U / 块类型 / 列表
// / 链接 / 表格 / 图片）保持原生组件，外层 wrap tailwind 样式让视觉一致。

type RibbonTab = 'start' | 'insert' | 'ai' | 'document' | 'style';

const RIBBON_TABS: { key: RibbonTab; label: string }[] = [
  { key: 'start', label: '开始' },
  { key: 'insert', label: '插入' },
  { key: 'ai', label: 'AI 助手' },
  { key: 'document', label: '文档' },
  { key: 'style', label: '样式' },
];

// AI 提示面板的 UI state（点 AI 按钮才显示）
type AiPromptState = {
  action: DocumentAiAction;
  label: string;
  userRequest: string;
  creativityMode: DocumentAiCreativityMode;
  activeSkillId: string | null;
  submitting: boolean;
};

const AI_ACTION_LABELS: Record<DocumentAiAction, string> = {
  expand: '扩写',
  rewrite_pro: '改写 · 专业',
  rewrite_short: '改写 · 简洁',
  summarize: '总结',
  extract: '提取要点',
  translate: '翻译',
  style_distilled: '切换语言风格',
  // P13b/c：资料增强类 op 人话名（UI 暴露见 P13c 改版）
  insert_from_materials: '从资料生成此处',
  rewrite_by_strategy: '按战略方向重写',
  insert_data_table: '插入数据表',
};

function RibbonToolbar({
  onAiAction,
  editorRef,
  notifyContentChange,
  writingSkills,
  defaultActiveSkillId,
  defaultCreativityMode,
  fontSize,
  setFontSize,
  theme,
  setTheme,
}: {
  onAiAction?: (
    action: string,
    opts?: RichTextDocumentEditorAiOpts,
  ) => Promise<RichTextDocumentEditorAiResult | void> | RichTextDocumentEditorAiResult | void;
  editorRef: React.RefObject<MDXEditorMethods | null>;
  /** P14a：editor.setMarkdown() 不一定触发 onChange，AI 应用结果后手动通知父组件同步 */
  notifyContentChange?: (next: string) => void;
  writingSkills: RichTextDocumentEditorWritingSkill[];
  defaultActiveSkillId: string | null;
  defaultCreativityMode: DocumentAiCreativityMode;
  fontSize: EditorFontSize;
  setFontSize: React.Dispatch<React.SetStateAction<EditorFontSize>>;
  theme: EditorTheme;
  setTheme: React.Dispatch<React.SetStateAction<EditorTheme>>;
}) {
  const [active, setActive] = useState<RibbonTab>('start');
  const [aiPrompt, setAiPrompt] = useState<AiPromptState | null>(null);
  // P14a：用户点 AI 按钮"那一刻"的选区快照（用于送到后端做 prompt 上下文）。
  const [capturedSelection, setCapturedSelection] = useState<string>('');
  // P14a-fix：DOM Range 快照。点 AI 按钮后 AiPromptPanel textarea 抢 focus 会把
  // window selection 清空，提交时已经没法用 window.getSelection() 拿回选区。
  // 用 ref 而不是 state——Range 是 mutable DOM 对象，存在 ref 里避免 stale closure。
  // submit 时把这个 Range 还原回 window selection，editor 内部 Lexical 选区会
  // 自动从 DOM selection 同步，然后 editor.insertMarkdown() 就能精确替换选区。
  const capturedRangeRef = useRef<Range | null>(null);

  const captureCurrentSelection = (): { text: string; range: Range | null } => {
    try {
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed || sel.rangeCount === 0) return { text: '', range: null };
      const text = sel.toString().trim();
      // cloneRange()：Range 是 mutable 的，sel 后续改了会污染我们的快照。
      const range = sel.getRangeAt(0).cloneRange();
      return { text, range };
    } catch {
      return { text: '', range: null };
    }
  };

  const openAiPrompt = (action: DocumentAiAction) => {
    // 先抓选区再开面板，否则面板的 textarea focus 会把 window selection 清掉
    const { text, range } = captureCurrentSelection();
    setCapturedSelection(text);
    capturedRangeRef.current = range;
    setAiPrompt({
      action,
      label: AI_ACTION_LABELS[action],
      userRequest: '',
      creativityMode: defaultCreativityMode,
      activeSkillId: defaultActiveSkillId,
      submitting: false,
    });
  };

  // P14a-fix：把 capturedRangeRef 里的 DOM Range 还原回 window selection，
  // 让 editor 重新拿到这段选区。返回 true 表示还原成功。
  // 失败情况：Range 引用的 DOM 节点已被卸载/重渲染（极少数，比如 AI 调用期间
  // 父组件强制更新了 value prop）。
  const restoreCapturedRange = (): boolean => {
    const range = capturedRangeRef.current;
    if (!range) return false;
    try {
      // Range.startContainer 仍在 document 里才能用
      if (!document.contains(range.startContainer) || !document.contains(range.endContainer)) {
        return false;
      }
      const sel = window.getSelection();
      if (!sel) return false;
      sel.removeAllRanges();
      sel.addRange(range);
      return !sel.isCollapsed;
    } catch {
      return false;
    }
  };

  const submitAiPrompt = async () => {
    if (!aiPrompt || aiPrompt.submitting || !onAiAction) return;
    setAiPrompt({ ...aiPrompt, submitting: true });
    try {
      const result = await onAiAction(aiPrompt.action, {
        userRequest: aiPrompt.userRequest.trim(),
        creativityMode: aiPrompt.creativityMode,
        activeSkillId: aiPrompt.activeSkillId,
        selectionText: capturedSelection,
      });
      if (result && result.content) {
        const editor = editorRef.current;
        if (editor) {
          if (result.targetScope === 'selection' && capturedRangeRef.current) {
            // 选区模式：还原 DOM Range → focus editor →
            // editor.insertMarkdown() 在 Lexical 非折叠选区上等价于"删除选区 + 在原位插入"
            const restored = restoreCapturedRange();
            if (restored) {
              editor.focus();
              // focus() 之后 Lexical 会从 DOM selection 同步内部 selection，
              // 此时 insertMarkdown 命中真选区做替换
              editor.insertMarkdown(result.content);
              // insertMarkdown 会触发 onChange，父组件 value 自动同步，
              // 不需要再手动 notifyContentChange
            } else {
              // Range 失效（DOM 重渲染了），不静默追加到末尾——那是错误的产品行为。
              // 抛错让父组件 flash('error') 让用户知道并重试。
              throw new Error('选区已失效，请重新选中文字再点 AI');
            }
          } else {
            // 整篇模式：直接替换全文
            editor.setMarkdown(result.content);
            notifyContentChange?.(result.content);
            editor.focus();
          }
        }
      }
      setAiPrompt(null);
      setCapturedSelection('');
      capturedRangeRef.current = null;
    } catch {
      setAiPrompt((prev) => (prev ? { ...prev, submitting: false } : null));
    }
  };

  return (
    <>
      {/* Tab Bar */}
      <div className="flex items-center gap-0 border-b border-gray-100 bg-[#FAFAFB] px-3">
        {RIBBON_TABS.map((tab) => {
          const isActive = active === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => {
                setActive(tab.key);
                if (tab.key !== 'ai') setAiPrompt(null);
              }}
              className={`relative px-4 py-2 text-[12px] font-medium transition-colors ${
                isActive
                  ? 'text-[#5B7BFE]'
                  : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              {tab.label}
              {isActive && (
                <span className="absolute inset-x-2 -bottom-px h-0.5 bg-[#5B7BFE] rounded-t" />
              )}
            </button>
          );
        })}
      </div>

      {/* Tool Area */}
      <div className="flex flex-wrap items-center gap-2 px-3 py-2 bg-white">
        {active === 'start' && <StartGroup />}
        {active === 'insert' && <InsertGroup editorRef={editorRef} />}
        {active === 'ai' && <AiGroup onOpenPrompt={openAiPrompt} currentAction={aiPrompt?.action ?? null} />}
        {active === 'document' && <DocumentGroup onAction={(a) => onAiAction?.(a)} />}
        {active === 'style' && (
          <StyleGroup
            fontSize={fontSize}
            setFontSize={setFontSize}
            theme={theme}
            setTheme={setTheme}
          />
        )}
      </div>

      {/* AI Prompt Panel —— 仅 AI tab + 点了某个 action 时展开 */}
      {active === 'ai' && aiPrompt && (
        <AiPromptPanel
          state={aiPrompt}
          setState={setAiPrompt}
          writingSkills={writingSkills}
          capturedSelection={capturedSelection}
          onCancel={() => {
            setAiPrompt(null);
            setCapturedSelection('');
          }}
          onSubmit={submitAiPrompt}
        />
      )}
    </>
  );
}

function AiPromptPanel({
  state,
  setState,
  writingSkills,
  capturedSelection,
  onCancel,
  onSubmit,
}: {
  state: AiPromptState;
  setState: React.Dispatch<React.SetStateAction<AiPromptState | null>>;
  writingSkills: RichTextDocumentEditorWritingSkill[];
  capturedSelection: string;
  onCancel: () => void;
  onSubmit: () => void;
}) {
  // P14a：用 capturedSelection 决定面板顶部说的是「处理这段」还是「处理整篇」
  const hasSelection = capturedSelection.length > 0;
  const selectionPreview = capturedSelection.length > 80
    ? capturedSelection.slice(0, 80) + '…'
    : capturedSelection;

  return (
    <div className="border-t border-gray-100 bg-blue-50/30 px-4 py-3">
      <div className="mx-auto max-w-[880px] space-y-3">
        {/* 标题：当前 action + 作用范围 */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#5B7BFE]">AI · {state.label}</span>
          {hasSelection ? (
            <span className="inline-flex items-center gap-1 rounded-md bg-blue-100 px-2 py-0.5 text-[11px] font-medium text-[#5B7BFE]">
              作用范围 · 选区（{capturedSelection.length} 字）
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded-md bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-600">
              作用范围 · 整篇文档
            </span>
          )}
          <span className="text-[11px] text-gray-500">
            {hasSelection
              ? '只处理你框选的这段，结果替换原选区'
              : '没框选 → 处理整篇；想只处理一段，请先在文档里框选'}
          </span>
        </div>

        {/* P14a：选区预览（只读，让用户确认 AI 看到的是不是想要的那段） */}
        {hasSelection && (
          <div className="rounded-md border border-blue-200 bg-white/70 px-3 py-2 text-[12px] leading-5 text-gray-700">
            <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-blue-400 mr-2">选区预览</span>
            <span className="whitespace-pre-wrap break-words">{selectionPreview}</span>
          </div>
        )}

        {/* userRequest 输入框 */}
        <textarea
          value={state.userRequest}
          onChange={(event) => setState((prev) => (prev ? { ...prev, userRequest: event.target.value } : prev))}
          placeholder="例如：重点强调财务影响 / 翻译成日文 / 用更口语化的风格 / 限制在 300 字以内"
          rows={2}
          disabled={state.submitting}
          autoFocus
          className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-[12.5px] leading-6 text-gray-800 outline-none focus:border-[#5B7BFE] resize-none disabled:opacity-60"
        />

        {/* 写作模式（creative / balanced / strict） */}
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-[11px] font-bold text-gray-500 min-w-[68px]">写作模式</span>
          <div className="flex gap-1">
            {(
              [
                { key: 'creative' as DocumentAiCreativityMode, label: '创意优先', icon: Sparkles, hint: '不受原文限制，自由发挥' },
                { key: 'balanced' as DocumentAiCreativityMode, label: '兼顾资料', icon: Scale, hint: '事实底色 + 自由措辞（默认）' },
                { key: 'strict' as DocumentAiCreativityMode, label: '完全客观', icon: ShieldCheck, hint: '严格依据原文，不臆测' },
              ] as const
            ).map((m) => {
              const isActive = state.creativityMode === m.key;
              const Icon = m.icon;
              return (
                <button
                  key={m.key}
                  type="button"
                  onClick={() => setState((prev) => (prev ? { ...prev, creativityMode: m.key } : prev))}
                  disabled={state.submitting}
                  title={m.hint}
                  className={`inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-[11.5px] font-medium transition-colors ${
                    isActive
                      ? 'border-[#5B7BFE] bg-white text-[#5B7BFE]'
                      : 'border-gray-200 bg-white text-gray-500 hover:border-gray-300 hover:text-gray-800'
                  }`}
                >
                  <Icon size={12} />
                  {m.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* 写作风格 skill 下拉 */}
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-[11px] font-bold text-gray-500 min-w-[68px]">写作风格</span>
          <select
            value={state.activeSkillId || ''}
            onChange={(event) =>
              setState((prev) => (prev ? { ...prev, activeSkillId: event.target.value || null } : prev))
            }
            disabled={state.submitting || writingSkills.length === 0}
            className="rounded-md border border-gray-200 bg-white px-2 py-1 text-[11.5px] text-gray-700 outline-none focus:border-[#5B7BFE] disabled:opacity-60"
          >
            <option value="">{writingSkills.length === 0 ? '（暂无蒸馏的风格档案）' : '不指定风格'}</option>
            {writingSkills.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          {writingSkills.length === 0 && (
            <span className="text-[10.5px] text-gray-400">在战略陪伴 chat 那边可以蒸馏出新的写作风格</span>
          )}
        </div>

        {/* 操作按钮 */}
        <div className="flex items-center justify-end gap-2 pt-1">
          <button
            type="button"
            onClick={onCancel}
            disabled={state.submitting}
            className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-3 py-1.5 text-[11.5px] font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-60"
          >
            <X size={12} />
            取消
          </button>
          <button
            type="button"
            onClick={onSubmit}
            disabled={state.submitting}
            className="inline-flex items-center gap-1.5 rounded-md bg-[#5B7BFE] px-4 py-1.5 text-[11.5px] font-bold text-white hover:bg-[#4a6ae8] disabled:opacity-60"
          >
            {state.submitting ? (
              <>
                <Loader2 size={12} className="animate-spin" />
                AI 处理中...
              </>
            ) : (
              <>
                <Play size={12} />
                执行 {state.label}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// 工具组：每组用细分隔线分开，跟 Word 的 ribbon 风格一致
function ToolGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center px-2 py-0.5 border-r border-gray-100 last:border-r-0">
      <div className="flex items-center gap-0.5">{children}</div>
      <p className="text-[9px] text-gray-400 mt-0.5 select-none">{label}</p>
    </div>
  );
}

// ─── 开始 tab ───
function StartGroup() {
  return (
    <>
      <ToolGroup label="撤销">
        <UndoRedo />
      </ToolGroup>
      <ToolGroup label="字体">
        <BoldItalicUnderlineToggles />
        <StrikeThroughSupSubToggles />
      </ToolGroup>
      <ToolGroup label="段落">
        <BlockTypeSelect />
      </ToolGroup>
      <ToolGroup label="列表">
        <ListsToggle />
      </ToolGroup>
    </>
  );
}

// ─── 插入 tab ───
// 用自定义按钮 + window.prompt 直接插入 markdown：
//   - MDXEditor 内置 <InsertTable/> <InsertImage/> <CreateLink/> 的 dialog 在 inline
//     editor 的 absolute overlay stacking context 内被遮，点击无反应；
//   - 改用 editorRef.current.insertMarkdown() 直接写入，100% 可工作。
function InsertGroup({ editorRef }: { editorRef: React.RefObject<MDXEditorMethods | null> }) {
  const insertAt = (text: string) => {
    const editor = editorRef.current;
    if (!editor) return;
    editor.insertMarkdown(text);
    editor.focus();
  };
  const handleInsertTable = () => {
    insertAt('\n\n| 列 1 | 列 2 | 列 3 |\n| --- | --- | --- |\n|  |  |  |\n|  |  |  |\n\n');
  };
  const handleInsertImage = () => {
    const url = window.prompt('图片 URL（http/https 或 data:）');
    if (!url) return;
    const alt = window.prompt('图片说明（可选，回车跳过）') || '';
    insertAt(`![${alt}](${url})`);
  };
  const handleInsertLink = () => {
    const url = window.prompt('链接 URL（含 https://）');
    if (!url) return;
    const text = window.prompt('显示文字（回车用 URL 本身）') || url;
    insertAt(`[${text}](${url})`);
  };
  return (
    <>
      <ToolGroup label="表格">
        <RibbonInsertButton icon={<TableIcon size={16} />} title="插入 3 列表格" onClick={handleInsertTable} />
      </ToolGroup>
      <ToolGroup label="图片">
        <RibbonInsertButton icon={<ImageIcon size={16} />} title="插入图片" onClick={handleInsertImage} />
      </ToolGroup>
      <ToolGroup label="链接">
        <RibbonInsertButton icon={<LinkIcon size={16} />} title="插入链接" onClick={handleInsertLink} />
      </ToolGroup>
    </>
  );
}

function RibbonInsertButton({
  icon,
  title,
  onClick,
}: {
  icon: React.ReactNode;
  title: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className="inline-flex h-7 w-7 items-center justify-center rounded text-gray-600 hover:bg-blue-50 hover:text-[#5B7BFE] transition-colors"
    >
      {icon}
    </button>
  );
}

// ─── AI 助手 tab —— stub ───
function AiGroup({
  onOpenPrompt,
  currentAction,
}: {
  onOpenPrompt: (action: DocumentAiAction) => void;
  currentAction: DocumentAiAction | null;
}) {
  const buttons: { key: DocumentAiAction; icon: React.ReactNode; label: string }[] = [
    { key: 'expand', icon: <Wand2 size={16} />, label: '扩写' },
    { key: 'rewrite_pro', icon: <PenToolIcon size={16} />, label: '改写 · 专业' },
    { key: 'rewrite_short', icon: <PenToolIcon size={16} />, label: '改写 · 简洁' },
    { key: 'summarize', icon: <FileText size={16} />, label: '总结' },
    { key: 'extract', icon: <Sparkles size={16} />, label: '提取要点' },
    { key: 'translate', icon: <Languages size={16} />, label: '翻译' },
    { key: 'style_distilled', icon: <Sparkles size={16} />, label: '切换风格' },
  ];
  return (
    <>
      {buttons.map((b) => {
        const isActive = currentAction === b.key;
        return (
          <button
            key={b.key}
            type="button"
            onClick={() => onOpenPrompt(b.key)}
            className={`flex flex-col items-center justify-center gap-1 rounded-md px-3 py-1.5 transition-colors ${
              isActive
                ? 'bg-blue-50 text-[#5B7BFE]'
                : 'text-gray-600 hover:bg-blue-50 hover:text-[#5B7BFE]'
            }`}
            title={`${b.label}（点击后展开输入框写具体要求）`}
          >
            {b.icon}
            <span className="text-[10px] leading-tight whitespace-nowrap">{b.label}</span>
          </button>
        );
      })}
    </>
  );
}

// ─── 文档 tab —— stub ───
// ─── 文档 tab：导出 docx + 全屏已 wire；版本历史 / 相关同事可见仍 stub ───
function DocumentGroup({ onAction }: { onAction: (a: string) => void }) {
  return (
    <>
      <button
        type="button"
        onClick={() => onAction('history')}
        className="flex flex-col items-center justify-center gap-1 rounded-md px-3 py-1.5 text-gray-600 hover:bg-blue-50 hover:text-[#5B7BFE] transition-colors"
        title="版本历史（下一步打通）"
      >
        <History size={16} />
        <span className="text-[10px] leading-tight">版本历史</span>
      </button>
      <button
        type="button"
        onClick={() => onAction('__export_docx')}
        className="flex flex-col items-center justify-center gap-1 rounded-md px-3 py-1.5 text-gray-600 hover:bg-blue-50 hover:text-[#5B7BFE] transition-colors"
        title="把当前内容生成 docx 并打开"
      >
        <Download size={16} />
        <span className="text-[10px] leading-tight">导出 docx</span>
      </button>
      <button
        type="button"
        onClick={() => onAction('share')}
        className="flex flex-col items-center justify-center gap-1 rounded-md px-3 py-1.5 text-gray-600 hover:bg-blue-50 hover:text-[#5B7BFE] transition-colors"
        title="相关同事可见（下一步打通）"
      >
        <UsersIcon size={16} />
        <span className="text-[10px] leading-tight">相关同事可见</span>
      </button>
      <button
        type="button"
        onClick={() => onAction('__toggle_fullscreen')}
        className="flex flex-col items-center justify-center gap-1 rounded-md px-3 py-1.5 text-gray-600 hover:bg-blue-50 hover:text-[#5B7BFE] transition-colors"
        title="切换全屏（隐藏左右栏，更专注写作）"
      >
        <Maximize2 size={16} />
        <span className="text-[10px] leading-tight">全屏</span>
      </button>
    </>
  );
}

// ─── 样式 tab：字号 + 主题 cycle 按钮，都 wire 到 RichTextDocumentEditor 内部 state ───
function StyleGroup({
  fontSize,
  setFontSize,
  theme,
  setTheme,
}: {
  fontSize: EditorFontSize;
  setFontSize: React.Dispatch<React.SetStateAction<EditorFontSize>>;
  theme: EditorTheme;
  setTheme: React.Dispatch<React.SetStateAction<EditorTheme>>;
}) {
  const cycleFontSize = () => {
    const order: EditorFontSize[] = ['sm', 'md', 'lg', 'xl'];
    setFontSize(order[(order.indexOf(fontSize) + 1) % order.length]);
  };
  const cycleTheme = () => {
    const order: EditorTheme[] = ['light', 'sepia', 'dark'];
    setTheme(order[(order.indexOf(theme) + 1) % order.length]);
  };
  return (
    <>
      <button
        type="button"
        onClick={cycleFontSize}
        className="flex flex-col items-center justify-center gap-1 rounded-md px-3 py-1.5 text-gray-600 hover:bg-blue-50 hover:text-[#5B7BFE] transition-colors"
        title="切换字号（小 → 中 → 大 → 特大 → 小）"
      >
        <Type size={16} />
        <span className="text-[10px] leading-tight">字号 · {FONT_SIZE_LABEL[fontSize]}</span>
      </button>
      <button
        type="button"
        onClick={cycleTheme}
        className="flex flex-col items-center justify-center gap-1 rounded-md px-3 py-1.5 text-gray-600 hover:bg-blue-50 hover:text-[#5B7BFE] transition-colors"
        title="切换主题（默认 → 米黄护眼 → 暗夜 → 默认）"
      >
        <Palette size={16} />
        <span className="text-[10px] leading-tight">主题 · {THEME_LABEL[theme]}</span>
      </button>
    </>
  );
}

/** 给用户预览效果用的样例 markdown */
export const SAMPLE_DOCUMENT_MARKDOWN = `# 善加基金会 2025 Q2 项目复盘

## 一、主要进展

- **资助项目**已完成 12 个，超额完成季度目标（计划 10 个）
- *妈妈岗*再就业项目覆盖了 3 个新城市：广州、佛山、东莞
- 完成 1 次理事会，主要议题：
  1. 2026 年度预算审议
  2. 鲁冰花舍项目延期方案
  3. 大额捐赠人 KYC 流程优化

> 本季度获得广东省社会组织评估 **3A 级**，具备公益性捐赠税前扣除资格。

---

## 二、当前关注的问题

- [ ] 缘救宝贝项目南方扩张方案 *待定*
- [ ] Q3 募捐目标与渠道分配
- [ ] 鲁冰花舍 2025 年度支出占比临近上限

## 三、关键数据

| 指标 | Q1 | Q2 | 同比 |
|---|---|---|---|
| 累计募捐 | 380 万 | 520 万 | +37% |
| 公益支出 | 290 万 | 410 万 | +41% |
| 受益家庭 | 4,200 | 5,800 | +38% |

## 四、下一步

详细数据见 [Q2 财务快报](https://example.com/q2-report)，
后续按 \`Q3 工作清单\` 推进。
`;
