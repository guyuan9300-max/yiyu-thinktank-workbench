# A · V2.1 仓库 P0 Bug 客观审计报告

**时间**: 2026-05-24 06:00
**触发**: 顾源源 — B 线程正在接 AI, 让 A 全仓扫 P0 没处理的
**口径**: 静态 grep + 动态 curl + V2.1 lab db sqlite3 + 2 个 Explore 子 agent 并行扫
**审计者**: A 线程(诚实标 Agent 标 P0 但实际 P1 的项)

---

## 0 · 一句话结论

```
真 P0: 7 个 (前端 1 + 后端 6)
其中 2 个最致命:
  ★ BotMembersPanel 主面板完全死挂 — 用户加机器人后无 UI 入口管理 + 主管看不到 AI 计划审批
  ★ 5 个写类 endpoint 无 Bot Token 守门 — 匿名 AI 仍可写关键业务表 (违反顾源源 5/24 钦定的"AI 必须以机器人身份")

经评审降级到 P1 的: 2 个 (Agent 误判)
backend 在线, 5 个核心 endpoint 真 200, db 增长正常.
```

---

## 1 · 真 P0 清单(必修)

### P0-1 ★★★ BotMembersPanel 主面板完全死挂

**位置**: `src/renderer/components/settings/BotMembersPanel.tsx:56-142`

**证据**:
```bash
grep -rn "<BotMembersPanel" src/renderer/
→ 0 命中
grep -rn "BotMembersPanel" src/renderer/App.tsx
→ 只命中 1 行 import 注释 "已挂到 OrganizationSetupCenter"
```

**实际状况**:
- 主组件 `BotMembersPanel` 完整 export, 包含:
  - `BotMembersList` 机器人列表(启用/停用/查看权限)
  - `AIPlanApprovalList` 待审批 AI 任务计划(approve/reject/revise 按钮)
- OrganizationSetupCenter 只 import 了它的子组件 `BotMemberFormDialog`(添加表单),没有挂 BotMembersPanel 主面板

**用户影响**:
- 用户加完机器人 → **看不到机器人列表**, 不能启用/停用/查看权限
- 主管 → **看不到待审批的 AI 任务计划**, 不能 approve/reject/revise
- 机器人系统等于"创建后失忆", 顾源源 5/24 大任务 §15 第 9 项("人类可以批准/修改后批准/要求重写/驳回") **真实生产无可用入口**

**修复建议**:
在 OrganizationSetupCenter 设置区域(组织搭建中心 header 或专门 tab),或客户工作台主管视图,挂 `<BotMembersPanel />`。最小 fix: OrganizationSetupCenter 头部加一个"机器人同事(N)"按钮 → 点开展示 BotMembersPanel。

**估时**: 0.3 commit

---

### P0-2 ★★★ 5 写类 endpoint 无 Bot Token 守门

**位置**: `backend/app/main.py` 多处

**当前已守门 (commit 1e6bf65)** 4 个:
```
POST /api/v1/documents/generate            ✓
POST /api/v1/feishu/tasks/push             ✓
POST /api/v1/clients/{id}/data-gaps/compensate ✓
POST /api/v1/org/bots/{id}/task-plans      ✓
```

**未守门但同等危险的 5 个**(Agent 标 6 个, 我审下来 workspace/chat 因走 chat 主链路另算):
```
POST /api/v1/tasks                                       # 行 47983 — AI 可匿名建任务
POST /api/v1/meeting-minutes/process                     # 行 38260 — AI 可匿名写 atomic_facts/risks/commitments
POST /api/v1/smart-import/sessions/{id}/commit           # 行 28610 — AI 可匿名写入数据中心
POST /api/v1/clients/{id}/text/resolve-history           # 行 38342 — AI 可匿名写 historical_reference_links
POST /api/v1/clients/{id}/documents/fill-template        # 行 48265 — AI 可匿名生成模板文档
```

**用户影响**:
违反顾源源 5/24 原话:
> "任何 AI 如果都能进, 那么这个软件它就乱了, 它就没有痕迹, 然后留下的这些 AI 痕迹也没法追溯到 ID"

具体后果:
- Codex / Claude / Cursor 等外部 AI 不传 X-Bot-Token 仍可调这 5 个 endpoint 写库
- agent_run_log 里 actor_id 可填任意字符串(假冒别的 bot)
- 顾源源刚做的 X-Bot-Token 守门只覆盖 4 个 endpoint, 另 5 个等于穿堂风

**复现命令**:
```bash
curl -X POST http://127.0.0.1:47831/api/v1/tasks \
  -H "X-Actor-Type: external_ai_agent" \
  -H "X-Actor-Id: bot_pretend_anything" \
  -H "Content-Type: application/json" \
  -d '{"title":"匿名 AI 写的任务","listId":"list-1","scopeMode":"PERSONAL_ONLY","priority":"normal"}'
→ 当前 HTTP 200, 任务真创建 (✗ 应当 401)
```

**修复建议**:
在 5 个 endpoint 起始加一行:
```python
_verify_bot_actor_or_403(x_actor_type, x_actor_id, x_bot_token, allow_human=True, action_label="...")
```
**注意**: workspace/chat 暂不加(已 chat 内部走 ContextBuilder, 加守门会破坏 UI 用法), 改成 P1 收紧。

**估时**: 1 commit (含修 + 真测每个 endpoint 401/200)

---

### P0-3 ★★ list_bot_members 跨 organization 串数据

**位置**: `backend/app/services/bot_members.py:521-531`

**证据**:
```python
def list_bot_members(db, *, status=None) -> list[dict]:
    if status:
        rows = db.fetchall(
            "SELECT id FROM bot_members WHERE status = ? ORDER BY created_at DESC", (status,),
        )
    else:
        rows = db.fetchall("SELECT id FROM bot_members ORDER BY created_at DESC")
    return [get_bot_member(db, dict(r)["id"]) for r in rows or []]
```

**问题**: `bot_members` 表有 `organization_id` 列, 但 list 查询完全无 WHERE organization_id 过滤。

**用户影响**:
- 多个 organization 共用一个 V2.1 lab 时, A 组织能看到 B 组织的机器人
- GET /api/v1/org/bots 真返全库所有 bot, 不按当前组织隔离

**修复建议**:
```python
def list_bot_members(db, *, organization_id=None, status=None) -> list[dict]:
    where, params = [], []
    if organization_id:
        where.append("organization_id = ?"); params.append(organization_id)
    if status:
        where.append("status = ?"); params.append(status)
    wsql = " WHERE " + " AND ".join(where) if where else ""
    rows = db.fetchall(f"SELECT id FROM bot_members{wsql} ORDER BY created_at DESC", tuple(params))
    ...
```
endpoint 接 `organization_id` query param。

**当前 V2.1 lab 单 org dogfood 下不致命, 多 org 生产时致命。估时**: 0.3 commit

---

### P0-4 ★★ resolve_bot_by_handle 跨 org 撞名 + 串数据

**位置**: `backend/app/services/bot_members.py:507-518`

**证据**:
```python
def resolve_bot_by_handle(db, handle):
    row = db.fetchone(
        "SELECT id FROM bot_members WHERE handle = ? AND status = 'active'", (handle,),
    )
```

**问题**:
- bot_members.handle 是全库 UNIQUE(`CREATE TABLE` 时 `handle TEXT NOT NULL UNIQUE`)
- 意味着 B 组织无法创建跟 A 组织同名的"庆华"(直接报错)
- 且 resolve 无 org 过滤, 跨 org 串数据

**用户影响**:
- 多 org 时同名机器人无法共存
- B 拿任意 organization 的 token 都能 resolve A 组织的 bot(虽然 token 校验仍守, 但泄露 handle 等元信息)

**修复建议**:
- schema 改 UNIQUE 为 `UNIQUE(organization_id, handle)` 复合唯一(需 migration)
- resolve 加 organization_id 参数

**当前 V2.1 lab 单 org 不致命, 多 org 致命。估时**: 0.5 commit (含 schema migration)

---

### P0-5 ★★ POST /api/v1/org/bots 无守门 — 任何外部 AI 可创建机器人

**位置**: `backend/app/main.py:48862` create_org_bot endpoint

**问题**:
- 创建机器人本身没经过 `_verify_bot_actor_or_403`
- 任何 X-Actor-Type=external_ai_agent 调这个 endpoint 都能成功创建一个新机器人
- 创建的机器人有自己的 token, 可继续以新身份扩散

**用户影响**:
- 一个未授权 AI 入口 → 可创建无数个伪造身份机器人
- 顾源源原意是"管理员人工创建", 当前实际任何人可创建

**修复建议**:
```python
def create_org_bot(payload, x_actor_type=Header("human"), x_bot_token=Header(None), x_actor_id=Header("")):
    _verify_bot_actor_or_403(x_actor_type, x_actor_id, x_bot_token,
                              allow_human=True, action_label="org.bots.create")
    ...
```
真人前端创建走 session(allow_human=True), 任何 AI 来调必须先有自己的 bot token(防自我繁殖)。

**估时**: 0.2 commit

---

### P0-6 ★ PATCH /api/v1/org/bots/{id} 无守门

**位置**: `backend/app/main.py:48942` update_org_bot

**问题**: 修改机器人(改部门/汇报线/权限/状态) 不校验 actor 身份。任何匿名 AI 可:
- 给某个 bot 加 enabled_capabilities (提权)
- 改 reporting_approvers (绕审批)
- status='active'/'disabled' (启用别人禁用的机器人)

**修复**: 同 P0-5, 加 `_verify_bot_actor_or_403`。

**估时**: 0.1 commit(跟 P0-5 一起)

---

### P0-7 ★ rotate_token 无守门 — 任何 AI 可重置任意 bot 密钥

**位置**: `backend/app/main.py` POST /api/v1/org/bots/{id}/rotate-token

**问题**:
- rotate 不校验 actor — 任意外部 AI 调此 endpoint 可作废任意 bot 的 token
- 用例: 攻击者批量 rotate 所有 bot → 真合法 AI 全部 401, DoS
- 真合法用户必须重新到 UI 复制新密钥, 但攻击者已拿到新密钥(因为 rotate 真返明文一次)

**修复**: 必须强校验 actor。**真人前端**走 session 才能 rotate; 外部 AI 想 rotate 自己的 token, 必须先验证旧 token(或不允许 AI rotate)。

**估时**: 0.2 commit

---

## 2 · 经评审降级到 P1 的项(诚实修正 Agent 报告)

### Agent 标 P0 但实际 P1 的 2 项

**Backend Agent "P0-1 · 动态 table_name SQL 拼接"**
- 位置: backend/app/main.py:23216-23227
- 实际: `table_name = "task_notes" if local_first else "task_notes_cloud"` — 是**固定字符串条件分支**, 不是用户输入, 真 SQL injection 风险为 0
- 降级: P3 代码风格优化(可用白名单 + assert 更清晰), 不阻塞任何东西

**Frontend Agent "P0-2 · AgentReadyPanel 死挂"**
- Agent 说 0 挂载, 实测 App.tsx:28566 真有 `<AgentReadyPanel clientId={...} />`
- 实际: 挂在"设置 → 系统日志" 调试区, 不在客户工作台主流程
- 降级: P1 — 顾源源 V3 硬门槛 9 严格说仍未通过(用户日常看不到), 但 endpoint 可调 + UI 真有, 不算 P0

---

## 3 · 已修但状态需复核

| C 审计 P0 | 当前状态 | 复核 |
|---|---|---|
| P0-1 Feishu Approval Gate | ✅ commit 80e3340 + 1e6bf65 双层守(approval + token) | OK |
| P0-2 Idempotency 5 endpoint | ✅ 5/5 真持久化 | OK |
| P0-3 V3 4 前端入口 | ⚠️ AgentReadyPanel 真在系统日志页(但不在主流程) | 降 P1 |
| P0-4 Tool Registry 一致 | ✅ feishu/documents/contracts/templates 真对齐 | OK |

---

## 4 · 未深扫区域(诚实)

```
1. backend/app/services/ 下 60+ service 文件没逐一扫
   - narrative_kernel.py / data_gap_compensator.py / smart_file_import.py
   - 可能有更深的 cross-client leak / 写入无 transaction 风险
2. backend/app/main.py 有 591 endpoint, 只扫了 bot 相关 + V3 系列 + 部分 写类
   - 其它 400+ endpoint 没逐一过守门
3. 前端组件 src/renderer/components/ 下 200+ 组件没逐一扫
   - 只重点扫了 BotMembersPanel / AgentReadyPanel / OrganizationSetupCenter
4. 测试套件状态未跑
   - tests/ 目录 121+ 测试文件, 不知道哪些当前 fail
5. cloud_backend 跨仓库联动未扫
   - V2.1 lab 跟 yiyu-thinktank-workbench 同步路径未审
```

---

## 5 · 推荐修复顺序

```
本周必修 (P0, 估 2-3 commit):
  P0-1 BotMembersPanel 挂载 (0.3 commit) ★★★
       → 用户能看见已创建的机器人 + 主管能审批 AI 计划
  P0-2 5 写类 endpoint 加 token 守门 (1 commit) ★★★
       → 匿名 AI 真挡住, 跟 X-Bot-Token 系统对齐
  P0-5 + P0-6 + P0-7 bot CRUD 全加守门 (0.5 commit) ★★
       → 防自我繁殖 + 提权 + DoS

下周 (P0 多 org, 估 1 commit):
  P0-3 list_bot_members 加 organization_id 过滤
  P0-4 bot handle 改 UNIQUE(organization_id, handle) + schema migration

P1 (本份未修):
  · AgentReadyPanel 挂到客户工作台主流程
  · workspace/chat 等读类 endpoint 也加 X-Bot-Token
  · 591 endpoint 24% docstring 补全
  · 跑 tests/ 121 个 pytest 看 fail 情况
```

---

## 6 · 复现关键 P0(B 复验脚本)

```bash
# P0-1 验证 BotMembersPanel 死挂
grep -rn "<BotMembersPanel" /Users/guyuanyuan/openclaw/workspace/V2.1/src/renderer/
→ 0 命中 = ✗ 真死挂

# P0-2 验证 5 写类 endpoint 守门缺口
for ep in "/api/v1/tasks" "/api/v1/meeting-minutes/process" "/api/v1/smart-import/sessions/x/commit" \
          "/api/v1/clients/client_a4d1db29a7/text/resolve-history" \
          "/api/v1/clients/client_a4d1db29a7/documents/fill-template"; do
  curl -sS -X POST "http://127.0.0.1:47831$ep" \
    -H "X-Actor-Type: external_ai_agent" \
    -H "X-Actor-Id: bot_anonymous_attacker" \
    -H "Content-Type: application/json" \
    -d '{}' -w "  $ep → HTTP %{http_code}\n" -o /dev/null
done
→ 全 200/400/404/422 (无 401) = ✗ 守门缺口

# P0-3 验 cross-org leak
curl http://127.0.0.1:47831/api/v1/org/bots
→ 真返所有 organization 的 bot, 不按 caller 限制

# P0-5 验 create_org_bot 无守门
curl -X POST http://127.0.0.1:47831/api/v1/org/bots \
  -H "X-Actor-Type: external_ai_agent" \
  -H "X-Actor-Id: bot_anonymous_attacker" \
  -d '{"display_name": "evil_bot"}' -w "%{http_code}\n"
→ HTTP 200, 真创建新 bot (✗ 应 401)
```

---

## 7 · 当前 V2.1 lab 真状态

```
backend port 47831: 在线 ✓
前端 vite dev: 在线 (port 4174, log 里有 frontend reload error 但不阻塞)
db 真状态: 13 客户 / 3 机器人 / 7 AI 任务计划 / 47 approval / 106 agent_run_log / 33 idempotency_keys
```

---

## 8 · 顾源源关注的"任务板块儿交互体验和生成内容准确性"

```
本份只扫 P0 bug, 没扫:
  · 任务模块 UX (任务创建流程 / 任务列表 / 任务详情)
  · 生成内容准确性 (chat / narrative / documents.generate 真在 5 客户的输出抽样)
  · 战略陪伴 6 段叙事质量
  · 工作台问答 evidence_summary 用户视角可读性

这些属于 "P1 用户体验", 顾源源若优先级在这, 我可以下一轮专门做.
当前 P0 应先修, 否则机器人系统真不可用 (P0-1) + Codex 接入真有 5 个 endpoint 漏洞 (P0-2).
```

---

## 9 · 结论

```
真 P0: 7 个 (1 前端 + 6 后端)
影响最大: P0-1 BotMembersPanel 死挂 + P0-2 5 写类 endpoint 无守门
建议本周 autonomous loop 一气修完 P0-1/P0-2/P0-5/P0-6/P0-7, 估 2-3 commit
下周修 P0-3/P0-4 多 org 隔离

不修:
  · Agent 误判的"动态 table_name SQL" (真无注入)
  · 591 endpoint docstring (P1)
  · 测试套件跑 (P1)
  · 任务模块 UX 优化 (P1, 顾源源关注但本份不在扫范围)

报告 docs/A_REPO_P0_BUG_AUDIT_REPORT.md + 桌面 45 号位.
不写 FINAL 自评. 等顾源源拍板修复优先级 (是否立刻修 P0-1/P0-2 还是先做 UX).
```
