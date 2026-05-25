# A · M7 · AI 工作指令 inline @mention picker (微信群体验)

> 顾源源 5/25 拍板: "不用专门做一个选框选 @同事, 而是在那个对话框里面直接输入 @ 就会上弹出一个让你选择人名的弹窗, 就像在微信群里的弹窗一样."
>
> 完成: A AI · 0afda13 之上, 2026-05-25.

---

## 真改 (file:line)

只动 1 个文件: `src/renderer/components/ai_command/AICommandModal.tsx`

### M7.1 删旧独立按钮 dropdown
- 删: 原 line 339-385 整段 (mode === 'ai_command' && 按钮 + dropdown).
- 删: `showBotDropdown` state + 闭包 (`setShowBotDropdown`) — grep 0 命中.
- 保留: `availableBots` state + `useEffect` 拉数据 (76-91 行原位) — picker 用.
- 保留: `handleSelectBot` 工具方法 (顾源源 hard rule M7.3 明说不动); picker 改走新 `insertMentionFromPicker`, 老方法保留供未来 quick fill 路径.

### M7.2 inline mention picker 真加
- L76-86 `availableBots` 注释不变; 新加 `mentionState` / `highlightedIndex` / `isComposingRef`:
  ```ts
  const [mentionState, setMentionState] = useState<{open:boolean;query:string;atPos:number}|null>(null);
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const isComposingRef = useRef(false);
  ```
- L160-205 `detectMention(value, cursor)`:
  - 从 cursor-1 往回扫到最近 `@`; 遇空白则放弃.
  - `@` 前必须是空白/换行/字符串开头, 否则不触发 (避免 email 等情况).
  - `query` = `@` 后到 cursor 之间, 必须匹配 `/^[一-龥A-Za-z0-9_]*$/`.
  - IME 中 (isComposingRef.current) 直接 return.
- L207-212 `handleTextareaChange`: setText + detectMention.
- L214-223 `filteredBots`: 大小写不敏感, 中文用原 query 再 includes 一次 (兼容中文输入).
- L225-244 `insertMentionFromPicker`:
  - 用当前 cursor 切 before/after, 中间插入 `@<handle> ` (含尾空格);
  - setMode('ai_command');
  - setTimeout 0 → setSelectionRange(atPos + insert.length).
- L246-279 `handleTextareaKeyDown`:
  - picker open 时, ↑↓ 改 highlightedIndex, Enter/Tab 选中, Esc 关 — 全 preventDefault;
  - 否则原 Cmd/Ctrl+Enter 提交.
- L470-498 textarea 替换:
  - 包了一层 `<div className="relative">`, picker 绝对定位在下方;
  - 加 `onCompositionStart` / `onCompositionEnd` (IME 兼容; end 后再跑一次 detectMention).
- L744-810 文件末尾 inline `MentionPicker` 组件 (不单独建文件 — 顾源源 hard rule):
  - `z-[70]` (modal 是 `z-[60]`, 不撞);
  - `ring-1 ring-inset ring-gray-200 shadow-lg rounded-lg` 风格统一 LeaderPicker;
  - `max-h-[280px] overflow-y-auto`, 宽 `320px`;
  - 表项: Bot 图标 + display_name + 灰 @handle + 部门名 + actor_type 角标;
  - 高亮: `bg-[#5B7BFE]/10`, 字色深一档;
  - 无匹配文案: "无匹配的机器人同事 — 你可以手动输 @庆华" (温柔灰字);
  - `onMouseDown={e.preventDefault()}` 阻止 click 抢走 textarea focus.

### M7.3 兼容现有解析
- `parseUserMessage` (在 `aiCommand.ts`) 用 `/@([一-龥A-Za-z0-9_]+)/` regex, 与本 picker 的 `MENTION_TOKEN_RE` 字符集对齐 (中文 + 英文 + 数字 + 下划线), 真兼容.
- `handleSelectBot` 不动, 不在 render 树中触发.
- 审批流 / 模式切换 / parseSmartCommand 真没动.

---

## 验收 4 步 (M7.4)

### 1. grep 旧 UI 真清干净
```
$ grep -n "showBotDropdown\|选 AI 同事 (@)" src/renderer/components/ai_command/AICommandModal.tsx
(0 命中)
```
PASS.

### 2. grep 新机制真加
```
$ grep -n "mentionState\|MentionPicker\|isComposing" src/renderer/components/ai_command/AICommandModal.tsx
78:  // mentionState: ...
81:  const [mentionState, ...]
84:  const isComposingRef = useRef(false);
172, 214, 215, 220, 225, 229, 236, 248, 270  (检测+插入+按键)
477:  onCompositionStart=...
479:  isComposingRef.current = false;
490-493:  <MentionPicker ... query={mentionState.query} ...
746:  type MentionPickerProps = ...
754:  function MentionPicker(...)
```
PASS — 13+ 处真出现.

### 3. tsc --noEmit
```
$ npx tsc --noEmit
exit=0
```
PASS — 0 新增 error.

### 4. UI 手测 (agent 跑不了, 顾源源真测清单)
启动后请逐项核对:

| # | 操作 | 期望 |
| - | ---- | ---- |
| a | 打开 AI Command Modal | 看不到独立 "选 AI 同事 (@)" 按钮 (原按钮已删) |
| b | textarea 单独输 `@` | 下方 popup 弹出列所有 active bot |
| c | 继续输 `庆` (变成 `@庆`) | popup filter 到 "庆华" |
| d | 按 ↓ Enter | 文本变 `@庆华 ` (含尾空格), 光标停在尾巴 |
| e | 继续输 ` 帮我...` (空格开头) | popup 真关 (因为 @ 后只允许合法 mention 字符) |
| f | 再输 `@`, 按 Esc | popup 真关, 不插入任何东西 |
| g | 切中文 IME 输 "@庆华" composition 期间 | 不弹 picker; composition end 后才弹 |
| h | 输 `email@x.com` 这种 | 不弹 (因为 `@` 前是字母, 不是空白/行首) |

---

## git diff stat
```
src/renderer/components/ai_command/AICommandModal.tsx | 354 ++++++++++++-----
1 file changed, 270 insertions(+), 84 deletions(-)
```

## commit
`92ee93d` — feat(v2.1-lab ai-command M7): @mention inline picker (微信群体验)
分支: `v2.2-arch-v2`
父: `0afda13` (M6)

---

## 留下的 P2 (顾源源没要求, 标 P2)

- **picker 位置在 modal scroll 时漂移**: 当前 picker 用 `absolute top-full`, 跟随 textarea 容器, 但 modal 整体若上下滚动, popup 不会跟随 textarea 在 viewport 中的真实位置 (相对位置 OK, 视觉无问题, 因为 textarea 不长). 想要绝对像微信那种 portal 到 body + position:fixed 可以做, 但顾源源没要求, 视觉够用. — P2.
- **handleSelectBot 现已成死代码** (没有调用点): 顾源源 M7.3 明说不动, 故保留. 下一轮 cleanup 可删. — P2.
- **picker 没做键盘 PageUp/PageDown 跳页**: bot 多时翻页慢, 等 bot 数量真上 20+ 再考虑. — P3.
- **filteredBots 在父组件和 MentionPicker 里算了 2 次**: 一次是为了 key 拦截判断 length 和 highlightedIndex, 一次是 picker 自己再算一次显示. 后续可提到顶上 useMemo 一次性传给 picker. — P3 (无性能问题, bot 数量 <20).
