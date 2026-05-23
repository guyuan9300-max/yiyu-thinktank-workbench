# B AI · V3.0 CLI 命令规范设计 (B-1)

> **触发**: 顾源源 5/23 批 V3.0 全量执行, B 同步准备 (不阻塞 A)
> **作用**: 给外置 agent (Codex/Claude/Cursor) 提供 "像 CEO 一样调度益语" 的 CLI 入口
> **设计原则**: §V3_0_GOAL_DRIVEN_AI_COMPANY_OS.md 4 原则
> **执行人**: AI B
> **日期**: 2026-05-23

---

## 1 · CLI 命令总览

```bash
yiyu auth login                                                          # OAuth 授权
yiyu auth status                                                         # 查授权
yiyu auth logout

yiyu tools list                                                          # 列 Tool Registry 所有工具
yiyu tools describe <tool_name>                                          # 查工具详情 (input/output/permissions)

yiyu agent goal create --text "<目标>" [--client-id X] [--project-id Y]   # 创建 goal
yiyu agent plan generate --goal-id <id> [--skill <skill_name>]            # 生成 plan
yiyu agent plan show --plan-id <id>                                       # 查 plan
yiyu agent run execute --plan-id <id> --mode <dry-run|draft|live>         # 执行
yiyu agent run status --run-id <id>                                       # 查状态
yiyu agent run diff --run-id <id>                                         # 数据库前后对比
yiyu agent run rollback --run-id <id>                                     # 回滚
yiyu agent runs list [--limit 20]                                        # 列历史 run

yiyu approvals list [--status pending]                                    # 列待审批
yiyu approvals show --id <approval_id>                                    # 查审批详情
yiyu approvals approve --id <approval_id> [--note "<原因>"]               # 批准
yiyu approvals reject --id <approval_id> [--note "<原因>"]                # 拒绝

yiyu datacenter gaps --client <name|id>                                   # 列客户数据缺口
yiyu datacenter diff --run-id <id>                                        # 前后对比
yiyu datacenter facts --client <name|id> [--query "<keyword>"]            # 查 atomic_facts

yiyu storycard show --client <name|id>                                    # 看故事卡
yiyu storycard refresh --client <name|id>                                 # 刷新

yiyu skills list                                                         # 列 CEO skills
yiyu skills describe <skill_name>                                        # 查 skill 决策协议
```

---

## 2 · 核心命令详细规范

### 2.1 `yiyu agent goal create`

```
USAGE:
  yiyu agent goal create --text "<目标>" [OPTIONS]

OPTIONS:
  --text TEXT                 目标描述 (必填)
  --client-id ID              客户 ID (可选, 不填时 AI 自动识别)
  --project-id ID             项目 ID (可选)
  --skill NAME                指定 CEO skill (product_visionary_ceo / operational_efficiency_ceo / risk_control_coo)
  --constraint KEY=VAL        约束 (重复): do_not_send_external=true / only_create_drafts=true 等
  --success-criteria LIST     成功标准 (JSON list)
  --json                      JSON 输出

EXAMPLE:
  yiyu agent goal create \
    --text "处理今天和日慈的会议纪要, 并判断下一步最该推进什么" \
    --client-id rici \
    --skill product_visionary_ceo \
    --constraint do_not_send_external=true \
    --constraint only_create_drafts=true

OUTPUT (json):
  {
    "goal_id": "goal_xxx",
    "text": "...",
    "client_id": "rici",
    "constraints": {...},
    "success_criteria": [...],
    "created_at": "2026-05-23T..."
  }
```

### 2.2 `yiyu agent plan generate`

```
USAGE:
  yiyu agent plan generate --goal-id <id> [--skill <name>]

OUTPUT (json):
  {
    "plan_id": "plan_xxx",
    "goal_id": "goal_xxx",
    "skill_used": "product_visionary_ceo",
    "steps": [
      {"step": 1, "tool": "workbench.ingest_meeting_minutes", "purpose": "..."},
      {"step": 2, "tool": "facts.extract_from_note", "purpose": "..."},
      {"step": 3, "tool": "data_gap.analyze", "purpose": "..."},
      {"step": 4, "tool": "intel.search", "purpose": "...", "depends_on_gap": true},
      {"step": 5, "tool": "clarification.create", "purpose": "..."},
      {"step": 6, "tool": "task.create_draft", "purpose": "...", "requires_approval": true},
      {"step": 7, "tool": "strategy.refresh", "purpose": "..."}
    ],
    "estimated_duration": "60-120s",
    "estimated_writes": {"atomic_facts": "+5-15", "risk_signals": "+1-3", ...}
  }
```

### 2.3 `yiyu agent run execute`

```
USAGE:
  yiyu agent run execute --plan-id <id> --mode <dry-run|draft|live>

MODES:
  dry-run    模拟执行, 不写任何数据, 返回 "如果跑会写什么" 预览
  draft      真跑, 写候选/草稿状态, requires_approval=true 的动作进 Approval Queue
  live       真跑 + 自动批准所有 requires_approval (危险, 通常不用)

REQUIRED HEADERS (HTTP equivalent):
  X-Actor-Type: external_ai_agent
  X-Actor-Id: codex / claude / cursor / ...
  X-Agent-Run-Id: <run_id>
  Idempotency-Key: <unique key per step>

OUTPUT (json):
  {
    "run_id": "run_xxx",
    "plan_id": "plan_xxx",
    "mode": "draft",
    "status": "running" / "completed" / "failed" / "pending_approval",
    "started_at": "...",
    "completed_at": "...",
    "steps_completed": 5,
    "steps_total": 7,
    "steps_pending_approval": 1,
    "writes_summary": {
      "atomic_facts": 8,
      "event_line_activities": 1,
      "risk_signals": 1,
      "clarification_records": 2,
      "tasks (draft)": 1
    },
    "errors": [],
    "next_action": "yiyu approvals list  # 1 个动作待批准"
  }
```

### 2.4 `yiyu datacenter gaps`

```
USAGE:
  yiyu datacenter gaps --client <name|id> [--priority high]

OUTPUT (json):
  [
    {
      "gap_type": "missing_authoritative_value",
      "client_id": "rici",
      "description": "项目预算: 内部资料显示 30 万, 旧版方案显示 50 万, 无 user_confirmed",
      "suggested_tools": ["workbench.ask_user", "clarification.create"],
      "priority": "high",
      "impact": "影响对外材料和客户沟通口径",
      "evidence_fact_ids": ["af_xxx", "af_yyy"]
    },
    {
      "gap_type": "missing_external_evidence",
      "client_id": "rici",
      "description": "客户内部说'心灵魔法学院', 录音 1 处误为'心理魔法学院', 官网无 internet_official 印证",
      "suggested_tools": ["intel.search"],
      "priority": "medium",
      ...
    }
  ]
```

### 2.5 `yiyu approvals approve`

```
USAGE:
  yiyu approvals approve --id <approval_id> [--note "<reason>"]

EFFECT:
  · 解锁阻塞的 run 步骤
  · 执行真写入 (从草稿 → 正式)
  · 写 approval_queue 表 + agent_run_log
  · 触发 broadcast (跟 V2.5 一致)

OUTPUT (json):
  {
    "approval_id": "appr_xxx",
    "status": "approved",
    "approved_by": "user_yyy",
    "approved_at": "...",
    "executed_action": "task.publish",
    "result": {"task_id": "task_zzz", "status": "active"}
  }
```

---

## 3 · 外置 agent 调用样例 (CEO 模式)

### 样例 1 · Codex 像 CEO 调度

```bash
# Step 1: 创建目标
goal_id=$(yiyu agent goal create \
  --text "处理日慈 5/19 会议纪要, 检查数据缺口, 生成下一步" \
  --client-id rici \
  --skill product_visionary_ceo \
  --json | jq -r '.goal_id')

# Step 2: 生成计划
plan_id=$(yiyu agent plan generate --goal-id $goal_id --json | jq -r '.plan_id')

# Step 3: dry-run 预览
yiyu agent run execute --plan-id $plan_id --mode dry-run

# Step 4: 用户看了, 同意, 真跑 draft
run_id=$(yiyu agent run execute --plan-id $plan_id --mode draft --json | jq -r '.run_id')

# Step 5: 看 run 状态
yiyu agent run status --run-id $run_id

# Step 6: 看哪些动作要批准
yiyu approvals list --status pending

# Step 7: 用户批准一个
yiyu approvals approve --id appr_xxx --note "确认这个任务发给客户"

# Step 8: 看数据库前后对比
yiyu datacenter diff --run-id $run_id

# Step 9: 看新故事卡
yiyu storycard show --client rici
```

### 样例 2 · "AI 主动补缺口" 测试场景 (R2 验收用)

```bash
# 输入: 一段会议纪要
INPUT_TEXT="今天和某客户开会, 客户提到下个月想先做教师端试点, 预算还没有最终确认..."

# CEO 模式: 让 AI 自己判断要调用哪些工具
yiyu agent goal create \
  --text "处理这段会议纪要, 主动调用工具补缺口, 生成行动包" \
  --client-id rici \
  --skill operational_efficiency_ceo \
  --constraint require_human_approval=true

yiyu agent plan generate --goal-id $goal_id
# 预期 plan 至少 7 步, 含: ingest → extract → data_gap.analyze →
#                       intel.search (针对 gap) → clarification.create →
#                       task.create_draft (requires_approval) → strategy.refresh

yiyu agent run execute --plan-id $plan_id --mode draft

# B 跑 R2 评估
yiyu datacenter diff --run-id $run_id
# 验收 R2 指标:
#  · 调用模块 ≥ 4 ✅
#  · 根据数据缺口调用非固定模块 ≥ 1 次 ✅
#  · 新增澄清问题 ≥ 1 条 ✅
#  · 新增任务草稿 ≥ 1 条 ✅
```

---

## 4 · CLI 实现技术栈

### 4.1 推荐栈

```
语言: Python (跟主仓库 backend 同栈, 直接复用 pydantic models)
框架: Typer (类型注释自动转 CLI, 类似 click 但更现代)
HTTP: httpx (异步 + 同步双支持)
JSON 解析: 内置 + rich (彩色输出)
auth: keyring (Mac/Linux 系统级凭据存储, 跟 ollama / git 一致)

包名: yiyu-cli (pip install -e backend/cli/ 本地开发)
入口: yiyu = yiyu.cli:app
```

### 4.2 文件结构

```
backend/cli/
├── pyproject.toml
├── yiyu/
│   ├── __init__.py
│   ├── cli.py              # Typer app 入口
│   ├── auth.py             # auth login/status/logout
│   ├── tools.py            # tools list/describe
│   ├── agent.py            # agent goal/plan/run
│   ├── approvals.py        # approvals list/approve/reject
│   ├── datacenter.py       # datacenter gaps/diff/facts
│   ├── storycard.py        # storycard show/refresh
│   ├── skills.py           # skills list/describe
│   ├── http_client.py      # httpx 封装 + actor headers
│   └── output.py           # rich 输出 + JSON 模式
```

### 4.3 actor headers 自动注入

```python
# yiyu/http_client.py
class YiyuClient:
    def __init__(self, agent_name: str = "external_ai_agent"):
        self.client = httpx.Client(
            base_url=load_config().api_url,
            headers={
                "X-Actor-Type": "external_ai_agent",
                "X-Actor-Id": agent_name or get_agent_id_from_env(),
                "Authorization": f"Bearer {load_token()}",
            },
        )

    def request(self, method, url, *, run_id=None, idempotency_key=None, **kwargs):
        headers = kwargs.pop("headers", {})
        if run_id:
            headers["X-Agent-Run-Id"] = run_id
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return self.client.request(method, url, headers=headers, **kwargs)
```

---

## 5 · MCP-like 工具接口 (未来扩展, 不在 R2)

CLI 之外, 还可以暴露 MCP-like JSON-RPC 接口给 Claude/Codex 直接调:

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "yiyu.agent.run.execute",
    "arguments": {
      "plan_id": "plan_xxx",
      "mode": "draft"
    }
  },
  "id": 1
}
```

这部分 V3.0 不做, V3.1 考虑.

---

## 6 · 安全 / 权限 / 边界

| 边界 | 实现 |
|---|---|
| 不能直接写数据库 | CLI 只调 HTTP endpoint, 不直接连 sqlite |
| 必须有 actor context | YiyuClient 强制注入 X-Actor-Type + X-Actor-Id |
| 不能跨客户读 | 后端 endpoint 已有 client_id 隔离 (ClientFactView 设计) |
| 危险动作进 approval | live mode 默认禁用 (除非 --force, 给警告) |
| 幂等 | 每个 step idempotency_key 自动生成 |
| 回滚 | yiyu agent run rollback 调后端 endpoint |
| 审计 | 所有 CLI 调用通过 actor headers + Agent Run Log 留痕 |

---

## 7 · 给 A 的接口契约

A 在 V3.0 P1 实现 backend endpoint 时, 请确保:

| Endpoint | Method | Path | A 是否做 |
|---|---|---|---|
| 1 | POST | /api/v1/agent/goals | T+3-4 |
| 2 | POST | /api/v1/agent/goals/{id}/plan | T+3-4 |
| 3 | POST | /api/v1/agent/runs | T+3-4 |
| 4 | GET | /api/v1/agent/runs/{id} | T+3-4 |
| 5 | GET | /api/v1/agent/runs/{id}/diff | T+3-4 |
| 6 | POST | /api/v1/agent/runs/{id}/rollback | T+3-4 |
| 7 | GET | /api/v1/agent/tools | T+4 |
| 8 | GET | /api/v1/agent/tools/{name} | T+4 |
| 9 | POST | /api/v1/approvals/{id}/approve | T+5 |
| 10 | POST | /api/v1/approvals/{id}/reject | T+5 |
| 11 | GET | /api/v1/approvals | T+5 |
| 12 | GET | /api/v1/clients/{id}/data-gaps | T+1 (P0a) |
| 13 | GET | /api/v1/agent/skills | T+5 |
| 14 | GET | /api/v1/agent/skills/{name} | T+5 |

→ **14 endpoint** 给 CLI 用. A 实现完后 B 写 CLI 实际代码 (V3.0 P3, R2 之后).

---

**Author**: AI B · 2026-05-23
**实现时机**: 等 A V3.0 P1+P2 完成 (T+5-6), B 写 CLI Python 实现 (1-2 天)
**R2 测试**: CLI 暂用 curl 模拟 (脚本里直接调 HTTP endpoint + headers), 不需要 CLI 实现就能跑
