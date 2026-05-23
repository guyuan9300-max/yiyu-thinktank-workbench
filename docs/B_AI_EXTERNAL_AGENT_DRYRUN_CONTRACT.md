# 外置 Agent 最小接入契约 · Dry-run 版

> **冻结**: 2026-05-23 19:45 V1
> **作用**: 定义将来 Codex / Claude Code / Cursor 等外置 Agent 接入益语的最小契约.
> **重要**: **dry-run only**. 不做真实写入版本 (顾源源 5/23 19:00 钦定 "不要 2").
> **原因**: 现在内部模块还不完整, 外置 Agent 直接写会放大问题.

---

## 1 · 北极星

```
外置 Agent (Codex/Claude/Cursor) 通过统一底座调用益语:
  Agent Gateway → Tool Registry → Domain Services → Data Center → Approval/Audit

不应该自己亲自分析所有资料.
不应该直接写数据库.
不应该绕过 Approval Queue.

它应该是 "CEO 调度官", 不是 "另写一套".
```

---

## 2 · 6 个最小命令

### 2.1 `yiyu agent tools`

**用途**: 列出所有可调用工具 (Tool Registry).

| 字段 | 说明 |
|---|---|
| **输入** | 无 |
| **输出** | `{ tools: [ { name, version, scope, risk_level, requires_approval, schema } ] }` |
| **只读/可写** | 只读 |
| **需 approval** | 否 |
| **调内部 endpoint** | `GET /api/v1/tool-registry` (待 A 暴露) |
| **当前实现** | ❌ 缺 (blocked_by_A) |
| **风险等级** | low |

---

### 2.2 `yiyu agent plan`

**用途**: 给一个目标, 让益语 AI 拆解出执行计划.

| 字段 | 说明 |
|---|---|
| **输入** | `--goal "处理 XX 会议纪要, 生成合同+任务+品牌方案"` + `--client <id>` |
| **输出** | `{ plan_id, steps: [{ tool, input, expected_output, requires_approval }] }` |
| **只读/可写** | 只读 (生成 plan, 不执行) |
| **需 approval** | 否 |
| **调内部 endpoint** | `POST /api/v1/agent/plan` (待 A 暴露, V3.0 P1) |
| **当前实现** | ❌ 缺 (blocked_by_A) |
| **风险等级** | low |

---

### 2.3 `yiyu agent run --dry-run`

**用途**: 执行 plan 但**只生成 draft**, 不真写权威数据.

| 字段 | 说明 |
|---|---|
| **输入** | `--plan-id <id>` + `--mode dry-run` (默认) |
| **输出** | `{ run_id, draft_outputs: {...}, would_have_modified: [...], approval_queue_ids: [...] }` |
| **只读/可写** | dry-run (写 draft 表, 不动权威) |
| **需 approval** | 是 (后续 commit 进权威数据要走 Approval Queue) |
| **调内部 endpoint** | `POST /api/v1/agent/run` (待 A 暴露, V3.0 P1) |
| **当前实现** | ❌ 缺 (blocked_by_A) |
| **风险等级** | medium (dry-run 状态 low, 但 plan 内含 commit 步骤要标识清晰) |

---

### 2.4 `yiyu agent status`

**用途**: 查 agent run 当前状态 + 进度.

| 字段 | 说明 |
|---|---|
| **输入** | `--run-id <id>` |
| **输出** | `{ run_id, status, started_at, finished_at, steps: [{name, status, output_ref}], errors: [...] }` |
| **只读/可写** | 只读 |
| **需 approval** | 否 |
| **调内部 endpoint** | `GET /api/v1/agent-runs/{run_id}` (待 A 暴露) |
| **当前实现** | ❌ 缺 (blocked_by_A) |
| **风险等级** | low |

---

### 2.5 `yiyu approvals list`

**用途**: 列待审批动作 (Approval Queue).

| 字段 | 说明 |
|---|---|
| **输入** | `--client <id>` 可选 + `--status pending` 可选 |
| **输出** | `{ approvals: [{ id, action_type, client_id, payload, reason, created_at }] }` |
| **只读/可写** | 只读 |
| **需 approval** | 否 |
| **调内部 endpoint** | `GET /api/v1/approvals` ✅ (A 已暴露) |
| **当前实现** | ✅ **已通** (R2 fix-2 commit 28a7fb9) |
| **风险等级** | low |

---

### 2.6 `yiyu datacenter diff`

**用途**: 看一次 agent run 写了/将要写什么数据 (审计用).

| 字段 | 说明 |
|---|---|
| **输入** | `--run-id <id>` |
| **输出** | `{ run_id, db_diff: { table: { rows_added, rows_modified, samples: [...] } } }` |
| **只读/可写** | 只读 |
| **需 approval** | 否 |
| **调内部 endpoint** | `GET /api/v1/agent-runs/{run_id}/diff` (待 A 暴露) |
| **当前实现** | ❌ 缺 (blocked_by_A) |
| **风险等级** | low |

---

## 3 · CLI Skeleton (B 给参考, 不实现)

```bash
yiyu agent tools
# → 列出可调用工具 + schema

yiyu agent plan --goal-file meeting.txt --client client_a4d1db29a7
# → { plan_id: 'pln_xxx', steps: [...] }

yiyu agent run --plan-id pln_xxx --dry-run
# → { run_id: 'run_xxx', draft_outputs: { contract: '...', task_drafts: [...] } }

yiyu agent status --run-id run_xxx
# → { status: 'completed', steps: [{name, status, output_ref}] }

yiyu approvals list --client client_a4d1db29a7
# → [ { id: 'appr_xxx', action_type: 'task.publish', reason: '...' } ]

yiyu datacenter diff --run-id run_xxx
# → { db_diff: { atomic_facts: { rows_added: 5 }, ... } }
```

---

## 4 · 4 个安全保证 (顾源源原则)

```
1 外置 Agent dry-run 状态下不允许写权威数据 (atomic_facts/source_registry/...)
2 commit 进权威数据必须走 Approval Queue (用户拍板)
3 危险动作 (发对外材料/发布任务) 必须 approval_required=true
4 所有 agent run 必有 agent_run_log 记录 (idempotency_key + actor_type=external_ai_agent)
```

---

## 5 · B 不做的事 (顾源源 5/23 19:00 钦定)

```
B 不做真实写入版外置 Agent
B 不做 yiyu CLI 真实现 (只设计契约)
B 不做 Tool Registry 真实现 (A 做)
B 不做 Goal-Plan-Run 内部实现 (A 做, V3.0 P1)

B 做:
  · 本文档 (契约定义)
  · dry-run 评估脚本 (scripts/run_v3_ai_driven_dryrun_eval.py L4)
  · 等 A 暴露 endpoint 后用 httpx 测一遍 (模拟外置 Agent)
```

---

## 6 · 当前状态汇总

| 命令 | 内部 endpoint | 当前 | 阻塞 |
|---|---|---|---|
| `agent tools` | `GET /tool-registry` | ❌ | blocked_by_A |
| `agent plan` | `POST /agent/plan` | ❌ | blocked_by_A (V3.0 P1) |
| `agent run --dry-run` | `POST /agent/run` | ❌ | blocked_by_A (V3.0 P1) |
| `agent status` | `GET /agent-runs/{id}` | ❌ | blocked_by_A |
| `approvals list` | `GET /approvals` | ✅ | (R2 fix-2 已通) |
| `datacenter diff` | `GET /agent-runs/{id}/diff` | ❌ | blocked_by_A |

→ **6 命令 1/6 真通**. 距离外置 Agent 接入还需 A 暴露 5 个 endpoint.

---

## 7 · 双驱动一致性测试 (R3 后做)

待 V3.0 P1 (Goal-Plan-Run) 完成后, B 跑双驱动一致性测试:

```python
# scripts/run_v3_dual_driver_consistency.py (待写)

输入: 同一个 goal (明远会议纪要标准输入)
驱动 1 (内置): POST /api/v1/agent/plan (X-Actor-Type=internal_ai)
驱动 2 (外置): POST /api/v1/agent/plan (X-Actor-Type=external_ai_agent)

对比指标 (顾源源 V3.0 七钦定):
- 核心工具调用重合度 ≥ 70%
- 生成成果包项目重合度 ≥ 80%
- 合同草稿关键条款重合度 ≥ 80%
- 任务草稿重合度 ≥ 80%
- 澄清问题重合度 ≥ 70%
- 外部情报检索方向重合度 ≥ 60%
- 两组都不直接写数据库 100%
- 两组危险动作都进 Approval Queue 100%
```

→ 这个测试不在本阶段做, 等 A 暴露 Goal-Plan-Run 后接力.

---

**Author**: AI B · 2026-05-23 19:45
**关联**:
- 设计基础: `docs/B_AI_V3_0_CLI_DESIGN.md` (B-1, V3.0 早期设计)
- 评估标准: `docs/B_AI_EVAL_STANDARD_V1.md`
- 北极星方案: `docs/V3_0_GOAL_DRIVEN_AI_COMPANY_OS.md`
