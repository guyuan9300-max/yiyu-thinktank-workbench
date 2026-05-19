import React, { useState } from 'react';
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
} from 'lucide-react';

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
  codeBlockPlugin,
  imagePlugin,
  toolbarPlugin,
  BoldItalicUnderlineToggles,
  StrikeThroughSupSubToggles,
  BlockTypeSelect,
  UndoRedo,
  CreateLink,
  ListsToggle,
  InsertThematicBreak,
  InsertTable,
  InsertImage,
  InsertCodeBlock,
  Separator,
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
  /** 当 AI 按钮被点击时回调（先 stub，下一步接通 AI 时替换） */
  onAiStub?: (action: string) => void;
};

export const RichTextDocumentEditor = React.forwardRef<MDXEditorMethods, RichTextDocumentEditorProps>(
  function RichTextDocumentEditor(
    { value, onChange, placeholder, minHeight = 360, readOnly = false, onAiStub },
    ref,
  ) {
    return (
      <div
        className="rounded-2xl border border-gray-200 bg-white focus-within:border-[#5B7BFE] transition shadow-[0_2px_12px_rgba(15,23,42,0.04)]"
        style={{ minHeight }}
      >
        {/*
          工具栏 sticky 注意事项：
          - 移除根 div 的 overflow-hidden —— sticky 需要 ancestor 链没有截断 scroll
          - toolbarClassName 加 sticky top-0 z-20 bg-white，让它在外层滚动容器
            （App.tsx 的 Editor body `flex-1 overflow-y-auto`）顶部粘住。
          - rounded-2xl 视觉圆角靠 toolbar 本身的 rounded-t-2xl 维持。
        */}
        <MDXEditor
          ref={ref}
          markdown={value}
          onChange={onChange}
          placeholder={placeholder || '把文档贴在这里，或直接开始写。⌘B 加粗、⌘I 斜体；从飞书/网页粘贴时格式保留。'}
          readOnly={readOnly}
          contentEditableClassName="prose prose-sm max-w-none px-10 py-8 min-h-[480px] outline-none text-[14px] leading-7 text-gray-900"
          plugins={[
            headingsPlugin(),
            listsPlugin(),
            quotePlugin(),
            thematicBreakPlugin(),
            linkPlugin(),
            linkDialogPlugin(),
            tablePlugin(),
            codeBlockPlugin({ defaultCodeBlockLanguage: 'text' }),
            imagePlugin(),
            markdownShortcutPlugin(),
            toolbarPlugin({
              toolbarClassName:
                'sticky top-0 z-20 border-b border-gray-200 bg-white px-0 py-0 flex flex-col items-stretch rounded-t-2xl',
              toolbarContents: () => <RibbonToolbar onAiStub={onAiStub} />,
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

function RibbonToolbar({ onAiStub }: { onAiStub?: (action: string) => void }) {
  const [active, setActive] = useState<RibbonTab>('start');
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
              onClick={() => setActive(tab.key)}
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

      {/* Tool Area —— 各 tab 工具组 */}
      <div className="flex flex-wrap items-center gap-2 px-3 py-2 bg-white">
        {active === 'start' && <StartGroup />}
        {active === 'insert' && <InsertGroup />}
        {active === 'ai' && <AiGroup onAction={(a) => onAiStub?.(a)} />}
        {active === 'document' && <DocumentGroup onStub={(a) => onAiStub?.(a)} />}
        {active === 'style' && <StyleGroup onStub={(a) => onAiStub?.(a)} />}
      </div>
    </>
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
      <ToolGroup label="链接 / 分割">
        <CreateLink />
        <InsertThematicBreak />
      </ToolGroup>
    </>
  );
}

// ─── 插入 tab ───
function InsertGroup() {
  return (
    <>
      <ToolGroup label="表格">
        <InsertTable />
      </ToolGroup>
      <ToolGroup label="图片">
        <InsertImage />
      </ToolGroup>
      <ToolGroup label="链接">
        <CreateLink />
      </ToolGroup>
      <ToolGroup label="代码">
        <InsertCodeBlock />
      </ToolGroup>
      <ToolGroup label="分割线">
        <InsertThematicBreak />
      </ToolGroup>
    </>
  );
}

// ─── AI 助手 tab —— stub ───
function AiGroup({ onAction }: { onAction: (a: string) => void }) {
  const buttons: { key: string; icon: React.ReactNode; label: string }[] = [
    { key: 'expand', icon: <Wand2 size={16} />, label: '扩写' },
    { key: 'rewrite_pro', icon: <PenToolIcon size={16} />, label: '改写 · 专业' },
    { key: 'rewrite_short', icon: <PenToolIcon size={16} />, label: '改写 · 简洁' },
    { key: 'summarize', icon: <FileText size={16} />, label: '总结' },
    { key: 'extract', icon: <Sparkles size={16} />, label: '提取要点' },
    { key: 'translate', icon: <Languages size={16} />, label: '翻译' },
    { key: 'style_distilled', icon: <Sparkles size={16} />, label: '切换语言风格' },
  ];
  return (
    <>
      {buttons.map((b) => (
        <button
          key={b.key}
          type="button"
          onClick={() => onAction(b.key)}
          className="flex flex-col items-center justify-center gap-1 rounded-md px-3 py-1.5 text-gray-600 hover:bg-blue-50 hover:text-[#5B7BFE] transition-colors"
          title={`${b.label}（下一步打通 AI）`}
        >
          {b.icon}
          <span className="text-[10px] leading-tight whitespace-nowrap">{b.label}</span>
        </button>
      ))}
    </>
  );
}

// ─── 文档 tab —— stub ───
function DocumentGroup({ onStub }: { onStub: (a: string) => void }) {
  return (
    <>
      <button
        type="button"
        onClick={() => onStub('history')}
        className="flex flex-col items-center justify-center gap-1 rounded-md px-3 py-1.5 text-gray-600 hover:bg-blue-50 hover:text-[#5B7BFE] transition-colors"
      >
        <History size={16} />
        <span className="text-[10px] leading-tight">版本历史</span>
      </button>
      <button
        type="button"
        onClick={() => onStub('export_docx')}
        className="flex flex-col items-center justify-center gap-1 rounded-md px-3 py-1.5 text-gray-600 hover:bg-blue-50 hover:text-[#5B7BFE] transition-colors"
      >
        <Download size={16} />
        <span className="text-[10px] leading-tight">导出 docx</span>
      </button>
      <button
        type="button"
        onClick={() => onStub('share')}
        className="flex flex-col items-center justify-center gap-1 rounded-md px-3 py-1.5 text-gray-600 hover:bg-blue-50 hover:text-[#5B7BFE] transition-colors"
      >
        <UsersIcon size={16} />
        <span className="text-[10px] leading-tight">相关同事可见</span>
      </button>
      <button
        type="button"
        onClick={() => onStub('fullscreen')}
        className="flex flex-col items-center justify-center gap-1 rounded-md px-3 py-1.5 text-gray-600 hover:bg-blue-50 hover:text-[#5B7BFE] transition-colors"
      >
        <Maximize2 size={16} />
        <span className="text-[10px] leading-tight">全屏</span>
      </button>
    </>
  );
}

// ─── 样式 tab —— stub ───
function StyleGroup({ onStub }: { onStub: (a: string) => void }) {
  return (
    <>
      <button
        type="button"
        onClick={() => onStub('font')}
        className="flex flex-col items-center justify-center gap-1 rounded-md px-3 py-1.5 text-gray-600 hover:bg-blue-50 hover:text-[#5B7BFE] transition-colors"
      >
        <Type size={16} />
        <span className="text-[10px] leading-tight">字号 / 字体</span>
      </button>
      <button
        type="button"
        onClick={() => onStub('theme')}
        className="flex flex-col items-center justify-center gap-1 rounded-md px-3 py-1.5 text-gray-600 hover:bg-blue-50 hover:text-[#5B7BFE] transition-colors"
      >
        <Palette size={16} />
        <span className="text-[10px] leading-tight">主题</span>
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
