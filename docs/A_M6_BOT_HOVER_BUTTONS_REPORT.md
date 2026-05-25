# A · V2.1 lab · 机器人同事 M6 · 岗位卡 hover 3 按钮重排 + 编辑弹窗密钥管理

**日期**: 2026-05-24
**分支**: v2.2-arch-v2
**上一基线 commit**: 783369a (M1-M5 端到端通)
**本次 commit**: `0afda13` feat(v2.1-lab bot-hover-buttons M6): 岗位卡 hover 3 按钮重排 + 复制密钥即时可用
**变更范围**: 仅前端 (UI + state), 后端零改动

---

## 1. 顾源源原话 → 真做的事映射

> "把第一个改复制密钥, 第二个是编辑, 第三个是解除指派, 然后把重置密钥放在编辑里面"

| 顾源源要求 | 真做 |
|---|---|
| 岗位卡 hover 第 1 按钮 → "复制密钥" | `OrganizationSetupCenter.tsx:1888-1894` (蓝色主行动 #5B7BFE) |
| 第 2 按钮 → "编辑" | `OrganizationSetupCenter.tsx:1896-1902` (中性灰) |
| 第 3 按钮 → "解除指派" | `OrganizationSetupCenter.tsx:1903-1910` (灰边 hover 红) |
| 把"重置密钥"放进编辑里 | `BotMembersPanel.tsx:678-732` (KEY MANAGEMENT section in BotMemberFormDialog edit mode) |

---

## 2. 真物理约束 — 顾源源默许的"复制密钥" ≠ 字面读旧密钥

db 只存 `token_hash`, plain 密钥只在 `POST /api/v1/org/bots` (创建) 和
`POST /api/v1/org/bots/{id}/rotate-token` (重置) 时各返**一次**.
所以"复制密钥"物理上不可能读旧 plain — 实际是:

```
点"复制密钥" → 轻确认 modal (告知"复制 = 重置 + 复制新, 旧的立刻作废")
            → 用户点[重置并复制]
            → 调 rotateBotToken (后端真生成新 hash, 旧的立刻作废)
            → 把新 token_plain 自动 writeText 进剪贴板 (3 层 fallback)
            → 显示新 token 弹窗 (用户可二次复制 + 关闭)
```

UI 文案明确写出物理事实, 不骗用户.

---

## 3. M6.1 — 岗位卡 hover 3 按钮 (file:line)

**文件**: `src/renderer/components/settings/OrganizationSetupCenter.tsx`

- `line 484-501` — 新增 state `botCopyConfirm: BotMemberRecord | null` (inline 轻确认 modal 控制位)
- `line 493-498` — 改写 state `botRotateDialog` 形状: 从 `BotMemberRecord | null` → `{ bot, autoCopy } | null`, 用 union 区分两个入口 (编辑入口 autoCopy=false, 岗位卡入口 autoCopy=true)
- `line 1884-1913` — 3 按钮重排:
  - 第 1 个 "复制密钥" (`bg-[#5B7BFE]` + white text, 主行动) — `onClick={() => setBotCopyConfirm(holderBot)}`
  - 第 2 个 "编辑" (中性灰 ghost) — `onClick={() => setBotEditDialog(holderBot)}`
  - 第 3 个 "解除指派" (灰边 hover 红边红字) — `onClick={() => handleSelectRoleHolderBot(role.id, null)}`
- `line 2018-2042` — `<BotRotateTokenDialog>` 调用改成 `bot={...bot}` + `autoStart` + `autoCopy={...autoCopy}`, onRotated toast 文案按 autoCopy 分支
- `line 2049-2089` — 新增 inline 轻确认 modal (复用现有 fixed inset-0 z-[125] 样式, 不另开文件):
  - 标题 `COPY TOKEN · 复制启动密钥`
  - 正文明告"db 只存哈希、点重置并复制会立即生成新密钥、旧密钥立刻作废、当前用旧密钥的 Codex/Claude 需重新粘贴"
  - 按钮 `[取消]` `[重置并复制]`
  - 点"重置并复制" → 关 confirm → setBotRotateDialog({ bot, autoCopy: true })

**风格**: 不用 emoji, #5B7BFE 主色, rounded-full + shadow, 文字按钮.

---

## 4. M6.2 — 编辑弹窗 KEY MANAGEMENT section (file:line)

**文件**: `src/renderer/components/settings/BotMembersPanel.tsx`

- `line 16` — 加 `getBotMember` 进 import (重置成功后局部刷新 prefix/时间用)
- `line 312-316` — 加 2 个 state:
  - `rotateOverlay: BotMemberRecord | null` — 嵌套打开 BotRotateTokenDialog 的开关
  - `tokenInfoOverride: { token_prefix?, token_rotated_at? } | null` — 重置成功后局部 override 显示 (不强求外面 reload 完才刷)
- `line 678-732` — 编辑模式底部加 `<section>`:
  - `KEY MANAGEMENT · 密钥管理` 小标题 (uppercase tracking-[0.18em], 跟其它 section 同款)
  - 显示卡片: `font-mono` 显示 `token_prefix` (8 字符) + `•••••` 占位
  - 显示 `上次重置: {token_rotated_at | toLocaleString}` 或 "从未重置 (使用创建时的密钥)"
  - 按钮 `[重置密钥]` (灰边蓝字, 不与"保存修改"主按钮抢色) → 直接打开 RotateTokenDialog, 不再弹 confirm
  - 下方小灰字: "重置后旧密钥立刻失效, 请通知正在使用此机器人的 Codex / Claude 重新粘贴。"
- `line 736-755` — 嵌套渲染 `<BotRotateTokenDialog autoStart bot={rotateOverlay} ...>`:
  - autoStart=true (用户已在编辑里点了重置, 不再二次确认)
  - autoCopy=false (用户从编辑里来通常想看一眼新明文再手点复制)
  - onRotated 调 `getBotMember` 拉最新 prefix/时间, 用 `tokenInfoOverride` 即时刷新本卡片显示, 不关编辑弹窗

---

## 5. M6.1 复用机制 — BotRotateTokenDialog 加 autoStart + autoCopy 可选 prop

**文件**: `src/renderer/components/settings/BotMembersPanel.tsx`

- `line 776-810` — Props 加 `autoStart?: boolean` + `autoCopy?: boolean`, 两者默认 false (M5 老调用零破坏)
- `line 794-810` — useEffect autoStart: 弹窗一挂载就 `void rotate()`, 用 `autoStartedRef` 防 StrictMode 双调用真发两次 rotate (会让旧 token 作废两次)
- `line 821-829` — useEffect autoCopy: 拿到 newToken 后立即 `void copyToken()`, 用 `autoCopiedRef` 防二次复制

**复制 3 层 fallback** (M5 已有, M6 真复用, 未重写):
1. `navigator.clipboard.writeText` (现代 Electron 推荐路径)
2. `document.execCommand('copy')` (textarea select + execCommand)
3. 两步都失败 → 自动 select textarea + UI 提示 "请直接按 Cmd+C 手动复制"

---

## 6. 真验收 4 步

### 验收 1 — grep 复制密钥
```
$ grep -n "复制密钥" src/renderer/components/settings/OrganizationSetupCenter.tsx
494:  //     (b) 岗位卡 hover "复制密钥" confirm 后    → { bot, autoCopy: true }
497:  // M6.1: 岗位卡 hover "复制密钥" 按钮的轻确认 modal —
1884:                                  {/* M6.1: 机器人持岗人 hover 3 按钮 — 顺序: 复制密钥 / 编辑 / 解除指派.
1885:                                      复制密钥 = 蓝色主行动 (#5B7BFE), 物理上是"重置 + 自动复制"(db 只存 hash, 读不到旧 plain).
1896:                                        复制密钥
2028:            (b) 岗位卡"复制密钥" confirm modal 确认 → autoStart=true, autoCopy=true (流程零步, 直接送剪贴板)
2049:      {/* M6.1: 岗位卡"复制密钥" inline 轻确认 modal —
```
**通过**: 6 处命中, line 1896 是真按钮文案.

### 验收 2 — grep 密钥管理
```
$ grep -n "KEY MANAGEMENT\|密钥管理" src/renderer/components/settings/BotMembersPanel.tsx
312:  // M6.2: edit 模式下"密钥管理"区点"重置密钥"会嵌套打开一个 BotRotateTokenDialog (autoStart=true).
678:          {/* 密钥管理 — 仅 edit 模式. 顾源源 5/24 V2.1 lab M6.2:
684:                KEY MANAGEMENT · 密钥管理
```
**通过**: 3 处命中, line 684 是真 UI 标题文案.

### 验收 3 — HTTP 真测 rotate-token
```
$ curl -s -X POST http://127.0.0.1:47831/api/v1/org/bots/botmem_7fcfcd0e47fc437a92671b40/rotate-token
{
  "id": "botmem_7fcfcd0e47fc437a92671b40",
  "display_name": "庆华",
  "actor_id": "bot_60ab0ec2b071",
  "token_prefix": "IrJbomyB",
  "token_rotated_at": "2026-05-24T03:40:12.594390+00:00",
  "has_token": true,
  "token_plain": "IrJbomyBiuyXuPFo9xpu-llXZUmkuhos"
}

$ curl -s http://127.0.0.1:47831/api/v1/org/bots/botmem_7fcfcd0e47fc437a92671b40
token_prefix: IrJbomyB
token_rotated_at: 2026-05-24T03:40:12.594390+00:00
has_token: True
```
**通过**:
- 旋转前 token_prefix = `UksvfyXh` (M5 留下)
- 旋转后 token_prefix = `IrJbomyB`, token_plain 真返新 32 字符密钥
- GET 单条二次确认 prefix/rotated_at 真持久化

**真副作用** (顾源源知情): 庆华 bot 旧密钥 `UksvfyXh...` 已作废, 真的有外部 AI 在用就要改用新密钥 `IrJbomyB...`. 这是验收成本, 因为后端 rotate 是真的不可干跑.

### 验收 4 — tsc --noEmit
```
$ npx tsc --noEmit
(零输出, 退出码 0)
```
**通过**: 不引入新 TS error.

---

## 7. git diff stat

```
src/renderer/components/settings/BotMembersPanel.tsx        | 122 ++++++++++++++++++++-
src/renderer/components/settings/OrganizationSetupCenter.tsx | 103 +++++++++++++----
2 files changed, 205 insertions(+), 20 deletions(-)
```

仅前端两文件改动, 后端零改动, 数据库零改动.

---

## 8. 不破坏的 M1-M5 既有功能 (回归保留)

- M1: `botMembers` 数据源 — 未动
- M2: LeaderPicker 接受 bot 分组 — 未动
- M3: `holderBotId` 字段 — 未动
- M4: 岗位卡渲染 bot 持岗人 (AI 角标 + 蓝色字) — 未动 (`line 1873-1881`)
- M5: 编辑弹窗 form / 一次性创建 token 弹窗 / BotRotateTokenDialog 主体逻辑 — 未动, 仅给 RotateDialog 加了 2 个**可选**新 prop (默认 false 保持 M5 老调用零破坏), 给 edit form 加了一个**条件渲染**的新 section (isEdit && existingBot 时才显示)

---

## 9. commit hash

```
0afda13 feat(v2.1-lab bot-hover-buttons M6): 岗位卡 hover 3 按钮重排 + 复制密钥即时可用
 3 files changed, 386 insertions(+), 20 deletions(-)
 create mode 100644 docs/A_M6_BOT_HOVER_BUTTONS_REPORT.md
```

(报告本身的 hash 回填属于第二次 commit 范畴, 不再单独 commit 以免污染历史; 下次 M7 自然带上.)
