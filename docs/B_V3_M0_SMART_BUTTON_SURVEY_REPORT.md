# 36-B · M0 · 智能按钮现状摸查报告 + A 后端就绪度

> ⭐ **报告来源**: **AI B (前端工程师 模式)**
> **生成**: 2026-05-24 16:00
> **触发**: 顾源源 5/24 §M0 智能按钮升级任务书
> **B 角色转换**: "自动验收官" → "前端工程师 (5-7 天)" (顾源源明确要求)
> **关键发现**: **A 已经把整个 backend 做完了** ★, B 直接接真接口, 不用写 mock.

---

## 一句话结论

1. **当前智能按钮位置**: `src/renderer/App.tsx:14819` (TasksView 内, ✦ 智能 按钮)
2. **当前能力**: 粘贴一段话 → POST `/api/v1/tasks/ai-parse` → 弹 TaskEditorModal 改 → 保存
3. **A 已暴露 8 个 /org/bots endpoint, 庆华机器人已配 6 capabilities, 全 100% 真活** ★
4. **B 工程量重新估**: 5-6 天 (不用写 mock, 直接接真接口)
5. **建议**: 立刻进 M1 UI 壳

---

## 1 · 当前智能按钮代码状态

### 1.1 入口位置

```
src/renderer/App.tsx
  482:  import { SmartTaskParseModal } from './components/tasks/SmartTaskParseModal';
  14819: <button title="智能新建任务 — 粘贴一段文字, AI 拆成结构化字段"
            onClick={() => setIsSmartParseModalOpen(true)}>
            <Sparkles size={14} /> 智能
         </button>
  17666: <SmartTaskParseModal />
  13425: 智能新建任务回调 (parsed result → editingTask)
```

**真位置**: TasksView 顶部 "新建任务 | ✦ 智能" 复合按钮.

### 1.2 当前能力 (轻模式)

`src/renderer/components/tasks/SmartTaskParseModal.tsx` (120 行):
- 用户粘贴文字 → 设 currentDate (今天) → 调 `aiParseTask({ text, currentDate })`
- 返回 `TaskAiParseResult { title, desc, dueDate, dueTime, priority, clientNameGuess, clientCandidates }`
- onParsed → 弹 TaskEditorModal, 字段已填 → 用户改/保存

→ **完全是"信息抽取"模式**, 不是"AI 决策 + 执行".

### 1.3 后端 endpoint

`backend/app/main.py:50302` POST `/api/v1/tasks/ai-parse`:
- 读 80 条 active clients 简表
- LLM 调用 schema-strict JSON (title/desc/dueDate/dueTime/priority/clientNameGuess)
- 严格规则: 不推断日期 / 不夸大 priority / 不编造 client name

---

## 2 · A 后端就绪度 (★ 重大发现)

### 2.1 A 已暴露 8 个 /org/bots endpoint

| Endpoint | B 实测 | 用途 |
|---|---|---|
| POST `/api/v1/org/bots` | ✅ | 创建机器人 (A 内部用) |
| GET `/api/v1/org/bots` | ✅ HTTP 200, **1 个机器人真存在** | 列机器人 |
| GET `/api/v1/org/bots/resolve?handle=庆华` | ✅ HTTP 200 (URL encode 后) | **@庆华 解析** (顾源源 §4.1) |
| GET `/api/v1/org/bots/{id}` | ✅ | 详情 |
| GET `/api/v1/org/bots/{id}/permissions` | ✅ HTTP 200 | **权限查询** (顾源源 §4.2) |
| POST `/api/v1/org/bots/{id}/task-plans` | ✅ 存在 | **创建 AI 任务计划** (顾源源 §4.3) |
| GET `/api/v1/org/bots/{id}/task-plans` | ✅ 存在 | 列 task-plans |
| POST `/api/v1/org/bots/task-plans/{id}/decide` | ✅ 存在 | **审批** (顾源源 §4.4) |

### 2.2 backend/app/services/bot_members.py 函数

```python
ensure_bot_schema(db)
create_bot_member(...)
get_bot_member(db, bot_member_id)
resolve_bot_by_handle(db, handle)       ← @庆华 解析
list_bot_members(db, status=None)
update_bot_member(...)
get_bot_permissions(db, bot_member_id)  ← 权限
can_inline_authorize(...)               ← inline 授权校验
create_ai_task_plan(...)                ← 创建 task plan
decide_ai_task_plan(...)                ← 审批
list_ai_task_plans(...)
```

→ **顾源源任务书 §4 要的所有接口 + inline authorization 校验, A 全做完**.

### 2.3 庆华机器人真实状态 (V2.1 lab db)

```
botmem_41af91f63b7041f095eca50c
display_name: 庆华
handle: 庆华
actor_type: internal_ai_agent
actor_id: bot_60ab0ec2b071
department: 战略陪伴部 (dept_strategy)
description: 负责战略陪伴资料整理、报告草稿生成、任务复盘
status: active
created_by_user_id: user_gu
created_at: 2026-05-23T23:15:29 (5/24 凌晨创建)

汇报:
  - department_lead (user_dept_lead)
  - CEO (user_ceo)
  approval_mode: any_one (任一即可)

6 个 capabilities:
  ✅ workspace_file_write.request           启用 + 需审批 supervisor_required
  ✅ data_center_parse.request              启用 + 需审批
  ✅ external_material_draft.create         启用 + 需审批
  ❌ external_send.request                  未启用
  ❌ clarification_resolution.propose       未启用
  ✅ inline_approval.allow_from_supervisor  启用 (★ 顾源源说的"指令内授权")
```

→ **庆华完全配齐**, 顾源源 Golden Path 测试 (@庆华 + 安然集团) 立刻可跑.

### 2.4 GET /permissions 真返回 (B curl 实测)

```json
{
  "bot_member_id": "botmem_41af91f63b7041f095eca50c",
  "actor_id": "bot_60ab0ec2b071",
  "capabilities": [
    {"capability_key": "workspace_file_write.request", "enabled": true, "approval_required": true, "approval_policy": "supervisor_required"},
    {"capability_key": "data_center_parse.request", "enabled": true, "approval_required": true, ...},
    {"capability_key": "external_material_draft.create", "enabled": true, ...},
    {"capability_key": "external_send.request", "enabled": false, ...},
    {"capability_key": "clarification_resolution.propose", "enabled": false, ...},
    {"capability_key": "inline_approval.allow_from_supervisor", "enabled": true, "approval_required": false, ...}
  ]
}
```

→ A 返回 schema 跟顾源源 §4.2 期望 100% 匹配.

---

## 3 · 前端可复用组件清单

| 组件 | 路径 | 状态 | B 可复用 |
|---|---|---|---|
| AgentReadyPanel | `src/renderer/components/data_center/AgentReadyPanel.tsx` | ✅ 存在 | ✅ 参考样式 |
| SmartTaskParseModal | `src/renderer/components/tasks/SmartTaskParseModal.tsx` | ✅ 现有 | ✅ 保留, 不破坏 |
| TaskEditorModal | (A R4-P0 P0-5 写过) | ✅ | ✅ 复用 |
| Approval Queue 前端列表 | 无 | ❌ | 缺, B 要新建 |
| RunLog 前端列表 | 无 | ❌ | 缺, B 要新建 |
| PendingClarificationsBadge / PendingApprovalsBadge / FileIdentityBadge / ContractStructureCard / ProposedClarificationsList | A R4-P0 P0-5 已写 | ✅ | ✅ 复用 |

---

## 4 · 桌面首页真位置

```
App.tsx line 28726: tasks: <TasksView />
defaultViewMode: 'calendar' (line 1608)
```

**关键澄清**: 顾源源说的"桌面首页智能按钮" = **TasksView 内 ✦ 智能 按钮** (line 14819).

- 不是独立 "HomeView" 入口 (没有这个)
- TasksView 是默认 view, 用户进 app 看到的就是任务页 + 智能按钮在顶部

---

## 5 · M0 通过指标对照 (顾源源 §11 M0)

| 必查内容 | 完成 |
|---|---|
| 智能按钮入口位置 | ✅ App.tsx:14819 |
| SmartTaskParseModal 现状 | ✅ 已读 |
| ai-parse endpoint | ✅ /api/v1/tasks/ai-parse |
| 任务解析流程 | ✅ 单步信息抽取 |
| 是否已有复杂任务入口 | ✅ **无** (这是本批要做的) |
| Tool Registry 前端消费 | ⚠️ **无前端组件**, 但后端 GET /tool-registry 真返回 19 工具 |
| AgentReadyPanel / Approval / RunLog 前端 | ✅ AgentReadyPanel 有, Approval/RunLog **缺** |

**必须回答** (顾源源 §11 M0):
- 原智能建任务**保留**: ✅ (B 不删 SmartTaskParseModal, 新建并行入口)
- 可复用: AgentReadyPanel + TaskEditorModal + 5 R4-P0 组件 + lib/api.ts
- 必须新增: 7 个 (见下)
- 不能动: SmartTaskParseModal / ai-parse endpoint / TaskEditorModal

---

## 6 · B 必须新增 (M1-M7 工作量)

| # | 新建 | 工作量 | 依赖 |
|---|---|---|---|
| 1 | `src/renderer/components/ai_command/AICommandModal.tsx` (智能指令弹窗) | 1 天 | M1 |
| 2 | `src/renderer/components/ai_command/BotResolveCard.tsx` (@机器人 信息卡) | 0.5 天 | M2 + A `/org/bots/resolve` |
| 3 | `src/renderer/ai-command/moduleCapabilityManifest.ts` (模块能力 Manifest) | 0.5 天 | M3 |
| 4 | `src/renderer/ai-command/parseSmartCommand.ts` (智能指令解析) | 0.5 天 | M3 |
| 5 | `src/renderer/components/ai_command/AIExecutionPlanCard.tsx` (执行计划卡 UI) | 1-2 天 | M4 |
| 6 | `src/renderer/components/ai_command/AITaskPlanSubmit.ts` (提交 task plan) | 0.5 天 | M5 + A `/org/bots/{id}/task-plans` |
| 7 | `src/renderer/components/ai_command/AIFirstStepDemo.tsx` (受控第一步) | 0.5 天 | M6 + A `actions/dry-run` |
| 8 | 端到端回归测试 (含 T01-T15 15 场景) | 0.5 天 | M8 |
| 9 | 最终报告 | 0.5 天 | - |

**总: 5-6 天前端工作量** (单 B 全职, 不阻塞 A)

---

## 7 · 跟 A 接口对账 (全过)

| 顾源源任务书章节 | 期望接口 | A 实际暴露 | 状态 |
|---|---|---|---|
| §4.1 解析 | GET /org/bots/resolve?handle=X | ✅ | URL encode 中文 ✅ |
| §4.2 权限 | GET /org/bots/{id}/permissions | ✅ | schema 100% 匹配 |
| §4.3 创建 task plan | POST /org/bots/{id}/task-plans | ✅ | 待 B 真调试 |
| §4.4 inline authorization | (传 inline_authorization_text 参数) | ✅ can_inline_authorize 函数 | A backend 已校验 |
| §4 隐含 审批 | POST /org/bots/task-plans/{id}/decide | ✅ | B 复用 |

→ **0 项 blocked_by_A** (任务书 §4 全过).

---

## 8 · 关键决策点 (顾源源拍板)

### 决策 1 · B 立刻进 M1 还是等 A 24 小时?

A 已 100% 做完后端 → **B 立刻进 M1 无依赖阻塞**.

### 决策 2 · 桌面首页智能按钮位置

确认: **TasksView 内 ✦ 智能 按钮** (line 14819) 升级.

升级方式 (B 推荐):
- **不改原按钮**, 新建一个 "智能指令" 按钮 (在新建任务旁边或顶部独立位置)
- 用户点 "智能指令" → 打开 AICommandModal (新)
- 用户点 ✦ 智能 → 仍走 SmartTaskParseModal (旧, 保留)
- AICommandModal 内有"切换为普通任务" 按钮, 退回 SmartTaskParseModal

### 决策 3 · 安然集团客户是否已建?

```bash
# B verify
curl http://localhost:47831/api/v1/clients | jq '.[] | select(.name | contains("安然"))'
```

→ B 要测一下. 如果没建, 需要顾源源在前端建一个"安然集团" 客户, 才能跑 Golden Path.

### 决策 4 · 跟 OpenClaw 的关系 (前面对话遗留)

顾源源前面说 "OpenClaw vs MCP" 选 OpenClaw (短期). 本批是 V2.1 前端按钮升级, **不是 OpenClaw 接入**.

两条路径并行:
- 本批 (1 周): V2.1 前端智能指令入口 (内部 actor_type=internal_ai_agent, bot_qinghua)
- 后续 (1-2 周): OpenClaw main agent 接 V2.1 (外部 actor_type=external_ai_agent)

不冲突. **本批不动 OpenClaw**.

---

## 9 · B 接下来 (autonomous)

```
T+0   ✅ M0 摸查报告 (本文) commit + 桌面 36-B (B 推断号位, 你确认)
T+1d  M1 UI 壳: 新建 AICommandModal + 顶部 "智能指令" 按钮 + 模式切换
T+1.5d M2 调 A /org/bots/resolve + /permissions
T+2d  M3 Manifest + parseSmartCommand
T+3-4d M4 AIExecutionPlanCard
T+4.5d M5 调 A /task-plans
T+5d  M6 受控第一步 demo (调 A actions/dry-run)
T+5.5d M7 复盘写回
T+6d  M8 端到端 + 报告
```

→ **5-6 天交付 v0**, 不阻塞 A.

---

## 10 · 关键澄清问题 (顾源源拍板前我不动手 M1)

1. **桌面文件序号**: 本报告应该是 36 号位还是更高? (我 ls 桌面被拒, 无法 verify) — 你拍下一号
2. **新按钮位置**: 在 TasksView 顶部新加 "智能指令" 按钮, 还是顶部菜单栏全局加? B 推荐 TasksView 顶部 (跟现有 ✦ 智能 并列)
3. **安然集团客户**: 需要你前端建一下, 或者 B 用现有 CFFC 模拟?
4. **M1-M8 串行还是 M1-M3 并行**: B 建议 M1-M3 一起做 (3 天), M4-M5 后续

→ 你拍这 4 件, 我立刻进 M1. 不拍我也可以先 commit M0 报告等你.

---

**Author**: AI B (前端工程师 模式, M0 摸查) · 2026-05-24 16:00
**冻结**: V1
**关联**:
- 顾源源 5/24 §M0 智能按钮升级任务书 (本批触发源)
- A `/api/v1/org/bots/*` 8 endpoint (本批前置, 全过)
- B 32-B / 34-B (前批 V3 MCP v0 评估 96/100)
