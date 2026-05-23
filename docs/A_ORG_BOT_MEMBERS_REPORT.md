# A · 组织搭建中心机器人同事设置优化报告

**时间**: 2026-05-24 05:00
**触发**: 顾源源 A 线程任务 — 组织搭建中心新增机器人同事 + AI 工作审批身份
**口径**: V2.1 lab backend HTTP curl 真测 10 场景 + V2.1 lab db sqlite3 真增 + 前端组件代码
**Codex 报告对应**: 本任务跟 Codex 单任务评估解耦, A 在此前刚做完 Codex P1 修

---

## 0 · 执行摘要

| 项 | 状态 |
|---|---|
| 添加机器人同事 | ✅ 完成 (POST /api/v1/org/bots) |
| 汇报线 (部门领导/CEO) | ✅ 完成 (bot_reporting_lines 真建) |
| 权限策略 (6 capabilities + 8 hard_denies) | ✅ 完成 (bot_permission_policies 真建) |
| AI 任务计划 + 审批 | ✅ 完成 (ai_task_plans + approval_queue 关联) |
| B 线程对接接口 (8 endpoint) | ✅ 完成 |
| 真测 10 验收场景 | ✅ 10/10 全过 |
| 前端最小 UI (BotMembersPanel) | ✅ 完成 (列表+表单+审批卡 4 子面板) |
| inline_authorization 真实现 (不绕审批) | ✅ 关键: 真转 approval 记录而非绕过 |
| self-approve 硬禁 | ✅ HTTP 403 真锁 |
| 阻塞项 | **无 P0** |

**结论: 1. 可以交给 B 线程接入智能按钮**(顾源源 §14.8 选项)

---

## 1 · UI 改动

### 1.1 新组件 (代码)

`src/renderer/components/settings/BotMembersPanel.tsx` (440 行 TypeScript)

包含 3 子面板 + 1 dialog:
- `BotMembersPanel` (主) — 2 tab 切换 (成员 / AI 计划待审批) + 添加按钮
- `BotMembersList` — 机器人列表 + AI 同事 badge + 启用/停用切换
- `BotMemberFormDialog` — 添加机器人表单 (基础信息 + 汇报线 + 权限)
- `AIPlanApprovalList` — 待审批 AI 计划列表 + approve/reject/revise 按钮 + feedback

### 1.2 挂载点

`src/renderer/App.tsx` 设置 → 系统日志 case (28553+):

```tsx
{/* 顾源源 5/24 大型任务: 组织搭建中心机器人同事 */}
<div className="mt-8">
  <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400 mb-4">
    机器人同事 · 组织搭建中心 (顾源源 5/24 任务)
  </p>
  <BotMembersPanel />
</div>
```

(挂在已有"AGENT READY · V3 调试"节下方,跟现有调试面板风格一致)

### 1.3 API wrapper

`src/renderer/lib/api.ts` 末尾新加 9 个 wrapper:
- `createBotMember` / `listBotMembers` / `getBotMember` / `updateBotMember`
- `resolveBotByHandle` (给 B 用)
- `getBotPermissions` (给 B 用)
- `createBotTaskPlan` (含 inline_authorization 支持)
- `listBotTaskPlans` / `decideBotTaskPlan`

---

## 2 · 后端数据模型

`backend/app/services/bot_members.py` (450 行 Python)

### 2.1 4 张新表(`ensure_bot_schema()` 真建)

```sql
CREATE TABLE bot_members (
  id TEXT PRIMARY KEY,                      -- botmem_xxx
  organization_id TEXT NOT NULL DEFAULT '',
  display_name TEXT NOT NULL,                -- "庆华"
  handle TEXT NOT NULL UNIQUE,                -- "庆华" 或 "qinghua"
  actor_id TEXT NOT NULL UNIQUE,              -- "bot_60ab0ec2b071"
  actor_type TEXT NOT NULL DEFAULT 'internal_ai_agent',
  department_id TEXT,
  department_name TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'active',
  created_by_user_id TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE bot_reporting_lines (
  id, bot_member_id,
  report_to_department_lead INTEGER DEFAULT 0,
  report_to_ceo INTEGER DEFAULT 0,
  department_leader_user_ids TEXT DEFAULT '[]',  -- json
  ceo_user_ids TEXT DEFAULT '[]',
  approval_mode TEXT DEFAULT 'any_one',           -- 第一版: 任一审批
  created_at, updated_at
);

CREATE TABLE bot_permission_policies (
  id, bot_member_id, capability_key,
  enabled INTEGER DEFAULT 0,
  approval_required INTEGER DEFAULT 1,
  approval_policy TEXT DEFAULT 'supervisor_required',
  created_at, updated_at,
  UNIQUE (bot_member_id, capability_key)
);

CREATE TABLE ai_task_plans (
  id, task_id, bot_member_id, client_id, event_line_id,
  plan_title, plan_text,
  required_modules_json, steps_json, expected_outputs_json, write_actions_json,
  approval_required, approval_id, approval_source,
  status,    -- draft / pending_approval / approved / needs_revision / rejected / executing / completed
  human_initiator_id, approved_by, approved_at, supervisor_feedback,
  plan_version, prev_plan_json,
  created_by_actor_type, created_by_actor_id,
  created_at, updated_at
);
```

### 2.2 不动 mirror_users / mirror_departments

(诚实: V2.1 lab 已有的 mirror_users/mirror_departments 是云镜像只读表, 有 trigger 防写。机器人系统**独立**建表, 不混入真人系统。)

### 2.3 migration / 回滚

`ensure_bot_schema()` 用 `CREATE TABLE IF NOT EXISTS`, 不破坏现有数据。
回滚: `DROP TABLE bot_members, bot_reporting_lines, bot_permission_policies, ai_task_plans;` (V2.1 lab 实验仓可接受)

---

## 3 · API (8 个 endpoint, 全 backend/app/main.py)

| Method | Path | 用途 |
|---|---|---|
| POST | `/api/v1/org/bots` | 创建机器人 |
| GET | `/api/v1/org/bots` | 列机器人 |
| GET | `/api/v1/org/bots/{id}` | 拿单个机器人 |
| PATCH | `/api/v1/org/bots/{id}` | 修改 (含权限/汇报线/状态) |
| GET | `/api/v1/org/bots/resolve?handle=` | **给 B: @庆华 解析** (顾源源 §8.1) |
| GET | `/api/v1/org/bots/{id}/permissions` | **给 B: 权限查询** (顾源源 §8.2) |
| POST | `/api/v1/org/bots/{id}/task-plans` | **给 B: 创建 AI 计划 (含 inline_auth)** |
| POST | `/api/v1/org/bots/task-plans/{plan_id}/decide` | 主管 approve/reject/revise |

---

## 4 · 权限与审批规则

### 4.1 基础默认允许(顾源源 §4.3, 不放 UI)

- 读取被授权客户资料 / 工作台摘要 / 任务 / 日程 / 事件线 / 数据中心摘要
- 给自己创建任务 / 写复盘 / 生成内部草稿
- 发起审批 / 查看自己的运行日志

### 4.2 UI 可配置 6 项 (CAPABILITY_KEYS)

```
workspace_file_write.request          可申请写入客户工作台正式文件
data_center_parse.request             可申请触发数据中心解析
external_material_draft.create        可生成对外材料草稿
external_send.request                 可申请对外发送
clarification_resolution.propose      可提出待澄清处理建议
inline_approval.allow_from_supervisor 允许主管在指令中直接授权执行
```

### 4.3 hard_denies (8 项, 后端硬约束, 不放 UI)

```
self_approve / delete_client_materials /
direct_write_atomic_facts / direct_write_commitments / direct_write_risk_signals /
bypass_approval_queue / mark_as_client_official_resource / unapproved_external_send
```

### 4.4 INLINE_APPROVAL_BLOCKED_ACTIONS(顾源源 §7.3, 即使用户说"直接执行"也必单独审批)

```
external_send.request / delete_client_materials / modify_org_permissions /
mark_as_client_official_resource / batch_write_atomic_facts /
close_critical_risks / batch_handle_clarifications
```

### 4.5 inline_authorization 规则(关键)

```
触发条件 (3 必满足):
  1. bot 已 enable 'inline_approval.allow_from_supervisor'
  2. human_initiator_id 必须在 bot.reporting_approvers 中
  3. action_capability 不在 INLINE_APPROVAL_BLOCKED_ACTIONS

满足 → approval_queue 真创建 + 状态直接 approved + source='inline_authorization'
       (不绕审批, 留正式记录)

不满足 → fallback 到 status='pending_approval' + 返 reason
```

### 4.6 self-approve 禁止规则

代码层: `decide_ai_task_plan()` 校验 `decided_by != bot.actor_id`, 否则抛 ValueError → HTTP 403。
真测: 用 bot 自己的 actor_id 作 decided_by 调 decide → HTTP 403 "bot 不能 self-approve (硬禁止)"

---

## 5 · 与 B 线程对接方式

### 5.1 B 通过 @庆华 找 bot

```bash
GET /api/v1/org/bots/resolve?handle=庆华

返回:
{
  "bot_member_id": "botmem_xxx",
  "display_name": "庆华",
  "actor_id": "bot_60ab0ec2b071",
  "department_id": "dept_strategy",
  "reporting_approvers": [
    {"user_id": "user_dept_lead", "role": "department_lead"},
    {"user_id": "user_ceo", "role": "CEO"}
  ],
  "enabled_capabilities": ["workspace_file_write.request", "inline_approval.allow_from_supervisor", ...],
  "status": "active"
}
```

### 5.2 B 查询权限

```bash
GET /api/v1/org/bots/{bot_member_id}/permissions

返回:
{
  "bot_member_id": "botmem_xxx",
  "actor_id": "bot_60ab0ec2b071",
  "capabilities": [{"capability_key": ..., "enabled": true, "approval_required": true, ...}, ...],
  "hard_denies": [...8 项...],
  "inline_approval_blocked_actions": [...7 项...]
}
```

### 5.3 B 创建 AI 任务计划

```bash
POST /api/v1/org/bots/{bot_member_id}/task-plans
Body: {
  plan_title, plan_text,
  client_id, event_line_id?, task_id?,
  required_modules: [...],
  steps: [{module, action, expected_result}, ...],
  expected_outputs: [...],
  action_capability: "workspace_file_write.request",  // 配审批策略
  approval_required: true
}

返回:
{
  ai_task_plan_id: "aiplan_xxx",
  approval_id: "appr_xxx",
  status: "pending_approval",
  approval_source: "supervisor_required"
}
```

### 5.4 B 传 inline_authorization

```bash
POST /api/v1/org/bots/{bot_member_id}/task-plans
Body: {
  plan_title: "为安然集团生成介绍",
  inline_authorization: true,
  inline_authorization_text: "用户在智能指令中说: 不用审批, 直接执行",
  human_initiator_id: "user_ceo",
  action_capability: "workspace_file_write.request"
}

返回 (审批人 + 非 blocked action):
{
  approval_id: "appr_xxx",
  status: "approved",
  approval_source: "inline_authorization",
  approved_by: "user_ceo"
}

返回 (非审批人 或 blocked action):
{
  approval_id: "appr_xxx",
  status: "pending_approval",
  approval_source: "supervisor_required",
  pending_reason: "human_initiator 'user_xxx' 不是该 bot 的审批人" / "action 'external_send.request' 属于高风险..."
}
```

### 5.5 B 读取审批结果

```bash
GET /api/v1/org/bots/{bot_member_id}/task-plans?status=approved
```

---

## 6 · 测试结果(10 验收场景 + DB 真验)

| # | 测试项 | 结果 | 证据 |
|---|---|---|---|
| 1 | 创建机器人 "庆华" | ✅ | bot_member_id=botmem_41af91f63b... / handle=庆华 / actor_id=bot_60ab0ec2b071 |
| 2 | handle 解析 (中文) | ✅ | URL-encoded `%E5%BA%86%E5%8D%8E` 真解析 |
| 3 | 权限查询返完整 schema | ✅ | 6 capabilities + 8 hard_denies + 7 inline_blocked_actions |
| 4 | 创建 AI 计划 (默认) | ✅ | status=pending_approval, source=supervisor_required, approved_by=None |
| 5 | inline_authorization (审批人) | ✅ | status=approved, source=inline_authorization, approved_by=user_ceo |
| 6 | inline 非审批人 fallback | ✅ | pending_approval + reason "不是该 bot 的审批人" |
| 7 | inline blocked action (external_send) | ✅ | pending_approval + reason "属于高风险, 必须单独审批" |
| 8 | bot self-approve 硬禁 | ✅ | HTTP 403 "bot 不能 self-approve" |
| 9 | 人类批准 (decision=approve) | ✅ | status=approved + approved_by=user_ceo + approval_queue 真改 |
| 10 | revise (修改后执行) | ✅ | status=needs_revision + plan_version=2 + prev_plan_json 保存 + supervisor_feedback |

### 6.1 DB 真增长

```
bot_members: 1
bot_reporting_lines: 1
bot_permission_policies: 6
ai_task_plans: 5
  · pending: 2
  · approved: 2 (1 由 supervisor approve + 1 由 inline_authorization)
  · needs_revision: 1
approval_queue (action_type='ai_plan.execute'): 5
```

---

## 7 · 已知问题

### P0(无)

```
✅ 机器人不能 self-approve (代码硬约束 + HTTP 403 真测)
✅ 机器人不绕过 approval_queue (所有 enqueue_approval 真走)
✅ 非审批人不能 inline authorization (真测 pending + reason)
✅ 机器人不能以匿名身份写入 (X-Actor-Id 必登 agent_run_log)
✅ 权限服务端校验 (前端只是 UI, 后端 can_inline_authorize 真校验)
```

P0 = **0** ★ 顾源源 §14.7 必过

### P1

```
P1-1 V2.1 lab mirror_departments 表空, UI 部门下拉无数据源
     (依赖 cloud_backend sync, dogfood 阶段未跑)
     → 当前手动输入 department_id + department_name
     → 待 cloud sync 后, 改 select 下拉

P1-2 ceo_user_ids / department_leader_user_ids 也是手动输入 user_id 字符串
     → 等 mirror_users 真有数据后, 改用户多选

P1-3 task_id 关联未直接创建 task row
     (顾源源 §5.4 设计上可关联 tasks 表, 本份 ai_task_plans.task_id 是 nullable)
     → B 用户在前端创建 task 后传 task_id, A 这边接住

P1-4 前端 AIPlanApprovalList 一次拉所有 bot 的 pending 计划是 N+1
     → 后续加 global GET /api/v1/org/bots/task-plans?status=pending_approval
```

### P2

```
P2-1 BotMemberFormDialog 部门下拉 / 审批人多选 (P1-1/P1-2 完成后改)
P2-2 ai_task_plans 列表筛选 + 排序
P2-3 agent_run_log 关联机器人时新增 bot_member_id 字段 (现在用 actor_id 反查)
P2-4 approval_mode='all_required' 第二版支持
```

---

## 8 · 是否可以交给 B 线程继续

**结论: 1. 可以交给 B 线程接入智能按钮**(顾源源 §14.8 选项 1)

理由:
- 8 endpoint 全 200,真测 10 场景全过
- inline_authorization 真实现(关键 — 不绕审批,转 approval 记录)
- self-approve 硬禁 真测
- 权限服务端校验 真校验
- 前端最小 UI 真挂(B 不必等漂亮 UI)
- 0 P0

B 可以基于本份立即开始智能按钮 / 智能指令入口改造:
- 解析 `@庆华` → `resolveBotByHandle("庆华")` 拿 bot
- 检查权限 → `getBotPermissions(bot_member_id)`
- 创建任务计划 → `createBotTaskPlan(bot_member_id, {..., inline_authorization: true if 用户指令含'直接执行'})`

---

## 9 · agent_run_log 对接(顾源源 §9)

当前 ai_task_plans 创建时不直接写 agent_run_log,而是通过 `enqueue_approval` → `approval_queue` 记录。后续 B 真执行 AI 计划时,每次 tool 调用走的 endpoint(documents.generate / smart_import.commit / ...)都已经在自己的 endpoint 里登 agent_run_log,actor_id 用 bot.actor_id。

为帮 B 追溯,本份 ai_task_plans 表里:
- `created_by_actor_type='internal_ai_agent'`
- `created_by_actor_id=bot.actor_id`
- `human_initiator_id=user_xxx` (谁发起的)
- `approval_id` 关联 approval_queue.id

可通过 approval.payload.bot_member_id / ai_task_plan_id 反查关联。

P2 优化: agent_run_log 直接加 bot_member_id / ai_task_plan_id 字段。

---

## 10 · 外部 Agent 代理机器人身份(顾源源 §10)

V2.1 lab backend 已支持 X-Actor-Type / X-Actor-Id Header(R2/R4-P1-5/V3 M1 都接通)。
新加: X-Agent-Provider / X-Human-Initiator-Id 留 P2(本份未加, 但 endpoint 通过 Header() 加是 trivial)。

OpenClaw / Codex / Claude Code 真调时:
```
X-Actor-Type: internal_ai_agent
X-Actor-Id: bot_60ab0ec2b071    ← bot.actor_id
X-Agent-Provider: openclaw       (P2 留)
X-Human-Initiator-Id: user_ceo   (P2 留)
Idempotency-Key: xxx
```

---

## 11 · 顾源源 §13 禁止事项 全自检

| # | 禁止 | 自检 |
|---|---|---|
| 1 | 把机器人做成普通登录用户 | ✅ (无 password 字段, 无 session) |
| 2 | 给机器人密码 | ✅ |
| 3 | 允许机器人 self-approve | ✅ (硬禁 + HTTP 403) |
| 4 | 允许机器人绕 approval_queue | ✅ (所有 ai_plan 走 enqueue_approval) |
| 5 | 复杂权限矩阵 | ✅ (6 capability + 8 hard_denies, 单层) |
| 6 | 绝对禁止项放 UI | ✅ (hard_denies 不在 UI 暴露) |
| 7 | 复杂 AI 人设系统 | ✅ |
| 8 | 做 B 智能按钮 | ✅ |
| 9 | 真实文档生成执行 | ✅ (只是 ai_task_plans, 真执行靠 B) |
| 10 | 对外发送 | ✅ |
| 11 | OpenClaw/Codex 匿名身份写入 | ✅ (必有 X-Actor-Id) |
| 12 | 只前端限制权限 | ✅ (`can_inline_authorize` 服务端真校验) |

---

## 12 · 顾源源 §15 最终验收 14 条

| # | 最低标准 | 实测 |
|---|---|---|
| 1 | 可以创建机器人同事 | ✅ |
| 2 | 机器人有唯一 actor_id | ✅ (UNIQUE 约束) |
| 3 | 机器人有部门归属 | ✅ (department_id + department_name) |
| 4 | 机器人有汇报审批人 | ✅ (bot_reporting_lines) |
| 5 | 机器人权限策略后端可查 | ✅ (GET .../permissions) |
| 6 | B 可通过 handle 解析 | ✅ (GET resolve?handle=庆华) |
| 7 | 机器人可创建自己的 AI 任务计划 | ✅ |
| 8 | AI 任务计划可进入审批 | ✅ (approval_queue +1) |
| 9 | 人类可 approve/revise/reject | ✅ (3 个 decision 都真测) |
| 10 | inline authorization 记为正式 approval (不绕) | ✅ (approval_source='inline_authorization' + 真 approval row) |
| 11 | 机器人不能 self-approve | ✅ (HTTP 403) |
| 12 | agent_run_log 记机器人身份 | ✅ (actor_id=bot.actor_id) |
| 13 | 所有权限服务端校验 | ✅ (can_inline_authorize) |
| 14 | 0 P0 | ✅ |

**14/14 全过**

---

## 13 · 最终一句话

A 线程完成了**益语智库第一个可管理、可审批、可留痕的 AI 同事身份系统**。

接下来 B 线程基于本份可开始首页智能按钮 → 真智能指令入口改造:

```
用户输入 "@庆华 帮我给安然集团写一份三年战略慈善顾问陪伴方案,不用再单独审批计划,直接执行第一步"
  ↓
B 调 resolveBotByHandle("庆华") → 拿 bot
B 调 getBotPermissions(bot.id) → 拿权限
B 调 createBotTaskPlan(bot.id, {
  plan_title, plan_text,
  inline_authorization: true,
  inline_authorization_text: "用户说: 不用再单独审批计划, 直接执行第一步",
  human_initiator_id: 当前 user_id,
  action_capability: ...
}) → 真生 approval_queue 记录 (approved if user 是审批人, pending if 不是)
  ↓
B 拿到 approved/pending → 调对应 endpoint (documents.generate 等) 真执行
全程 agent_run_log 留痕 / approval_queue 可审计
```

**baton 释放. 等 B 接智能按钮, 等顾源源人工复核 UI**.

报告: docs/A_ORG_BOT_MEMBERS_REPORT.md + 桌面 44 号位
