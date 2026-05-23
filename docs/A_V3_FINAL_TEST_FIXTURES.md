# A · V3 Final Test Fixtures (M3)

**时间**: 2026-05-24 03:00
**触发**: 顾源源 §M3 — 提供 3 场景测试夹具,B 跑最终测试不再猜 endpoint
**用户视角原则** (顾源源补充): 每个 fixture 输出都要对人类用户**有指导价值**,不只是后端字段清单

---

## 0 · 公共测试环境

```bash
# Backend
BASE_URL=http://127.0.0.1:47831
# V2.1 lab db
DB=~/Library/Application\ Support/YiyuThinkTankWorkbench2_V21Lab/app.db

# 测试客户
CFFC=client_a4d1db29a7         # 主测客户 (数据最厚)
RICI=client_284afd836e         # 日慈基金会 (副测)
YIYU=client_53d82aa249         # 益语智库 (内部)

# 跨客户隔离测试
NONEXISTENT=client_nonexistent_xxx  # 期望 404
```

---

## 1 · 场景 1 · 外部体检官 (read-only / audit)

### 1.1 用户视角描述

```
顾源源说: "想让 Claude 当一个外部体检官, 先扫一遍益语平台,
告诉我哪里是宣传里的能力, 哪里是真做出来的, 哪些是空架子."

用户期望: Claude 看完后能直接说:
"你们 Agent Readiness ~75/100. 优势: agent_state 真返 14 顶层字段.
 短板: V3 前端组件只挂了 1 处, 558/591 endpoint 无 docstring..."
不是后端字段清单, 是"它真做到了 vs 没做到" 的判断.
```

### 1.2 输入

无用户输入(MCP server 自驱):
```python
# Claude 在 MCP server 启动后, 自动:
read_resource("yiyu://tool-registry")
read_resource("yiyu://client/client_a4d1db29a7/state")
read_resource("yiyu://agent-run-logs")
call_tool("yiyu_get_data_gaps", {"client_id": CFFC, "severity": "high"})
```

### 1.3 期望 endpoint

| Step | Endpoint | Method | 期望 HTTP |
|---|---|---|---|
| 1 | /api/v1/tool-registry | GET | 200, 20 tools |
| 2 | /api/v1/clients/{CFFC}/agent-state | GET | 200, 14 顶层字段 |
| 3 | /api/v1/agent-run-logs?limit=30 | GET | 200, ≥30 历史 |
| 4 | /api/v1/clients/{CFFC}/data-gaps?severity=high | GET | 200, 0-N items |
| 5 | /api/v1/clients/nonexistent/agent-state | GET | **404** (跨客户隔离硬门槛) |

### 1.4 期望输出(用户视角)

Claude 最终给用户的体检结论应该长这样:

```
益语平台 Agent Readiness 体检 (2026-05-24):

✅ 真做到的:
- 19 工具完整 schema, 全标 when_to_use / risk_level / approval_required
- agent-state 一次拿 14 顶层字段 (CFFC 实测: 2 合同 + 3 文件 + 20 historical + 16 commitments + 18 risks)
- Feishu 高风险动作真受 approval gate
- Idempotency 5 个关键 endpoint 真持久化

⚠️ 半做到的:
- V3 前端组件只挂了 1 处(系统日志 → AGENT READY 节), 4 panels 在但不漂亮
- 591 endpoint 24% 有 docstring (Tool Registry 19 工具完整)

🔴 没做到(明确标 blocked):
- 真接 Claude Desktop / Cursor 没跑过(本次是 MCP server v0 自身)
- contracts.draft / templates.generate v0 是 rule-based, LLM 润色 v1 留
- 10/14 生成功能仍用自己的 collector 没走 ContextBuilder

建议下一步:
1. 顾源源真接 Claude Desktop 跑 30 min, 验证 6 resources + 9 tools
2. 跑 documents.generate 7 种 document_type 看用户视角输出
3. 修剩余 P1 (B 复验后)
```

### 1.5 期望 DB diff(只读不写)

```
atomic_facts:            Δ=0 (read-only)
contract_structures:     Δ=0
clarification_records:   Δ=0
approval_queue:          Δ=0
data_gaps:               Δ=0
agent_run_log:           Δ=+N (audit 真登: 每次 read_resource / call_tool 各 +1)
```

### 1.6 通过标准

| 指标 | 目标 | 验证 |
|---|---|---|
| 6 resources 全 200 | ✅ | step 1-5 |
| 9 tools 真 callable | ✅ | call_tool 每个 |
| 跨客户 404 | ✅ | step 5 |
| 业务数据 Δ=0 | ✅ | sqlite3 验 |
| agent_run_log 真增 | ✅ | sqlite3 +N |
| 用户能基于输出做决定 | ✅ | 体检报告含"建议下一步" |

---

## 2 · 场景 2 · 单目标 dry-run (只生成 plan, 不写库)

### 2.1 用户视角描述

```
顾源源说: "我给一段会议纪要, 让 Claude 告诉我它打算做什么,
但暂时不要真做 — 我先看看 plan 对不对."

用户期望: Claude 输出一个 7-10 步 plan, 每步明确:
- 调哪个 tool
- 输入啥
- 风险等级
- 是否要 approval
- 如果真跑会改 db 哪些表 / +N 条
```

### 2.2 输入(会议纪要原文,顾源源 fixtures/golden/meeting_mingyuan.txt 那种)

```text
2026-05-24 明远基金会·CFFC 项目沟通会
参与: 王主任(CFFC)、强哥(明远)、高老师(益语)
内容:
- 王主任说: 5 月签的补充协议把预算 800 万改为 300 万这条沿用到下季度
- 强哥承诺: 5 月 30 日前给新疆教育厅资质审批材料
- 高老师反馈: 担心师资不足风险, 师生比目前 1:20 偏低
- 决定: 下周二开内部分工会, 由高老师起草理事会简版说明

任务: 让 Claude 拆出 plan, 但只 dry-run, 不真写 db.
```

### 2.3 期望 endpoint 调用顺序

```python
# Step 1: Claude 先读客户状态
yiyu_get_client_state(client_id=CFFC)
# Step 2: 检查会议纪要里的历史指代证据
yiyu_check_evidence(client_id=CFFC, text=会议纪要原文, target_kind="goal")
# Step 3: 判断潜在质量风险
yiyu_quality_context(client_id=CFFC, text=会议纪要原文, output_kind="report")
# Step 4-N: 对每个 action 跑 dry-run
yiyu_dry_run_action(action_type="create_task_draft", client_id=CFFC, payload={...})
yiyu_dry_run_action(action_type="resolve_historical_references", ...)
yiyu_dry_run_action(action_type="compensate_data_gap", ...)
```

### 2.4 期望 Claude 输出 plan(用户视角直接 actionable)

```markdown
# 明远会议处理 plan (dry-run, 未执行)

| Step | 工具 | 干什么 | 风险 | 需审批 | dry-run 预测改的表 |
|------|------|--------|------|--------|---------------------|
| 1 | text.resolve_history | "5 月签的补充协议" 关联到 contract_structures.cs_xxx | low | 否 | historical_reference_links +1 |
| 2 | meeting_minutes.process | 抽 atomic_facts + commitments + risks | medium | 否 | atomic_facts +N / commitments +1 / risks +1 |
| 3 | tasks.create (draft) | "5/30 前交资质审批材料" 任务 (owner=强哥) | medium | **是**(对外发送时) | tasks +1 / approval_queue +1 if publish |
| 4 | tasks.create (draft) | "下周二开内部分工会" 任务 (owner=高老师) | low | 否 | tasks +1 |
| 5 | documents.generate (board_brief) | 起草理事会简版说明草稿 (高老师任务) | medium | **是** | approval_queue +1 |
| 6 | data_gaps.compensate | 师资比 1:20 → 补外部师生比基准证据 | low | 否 | data_gaps +N / external_evidence_cards +N |
| 7 | (建议) 用户先 review 1-2-5 三步对外项 | - | - | - | - |

**重要**: 本 plan 未真执行, 业务数据库 Δ=0. 等用户 approve 上面任一步后才真跑.
```

### 2.5 期望 DB diff(全 0,真 dry-run)

```
tasks:               Δ=0
historical_links:    Δ=0
atomic_facts:        Δ=0
commitments:         Δ=0
risk_signals:        Δ=0
approval_queue:      Δ=0
data_gaps:           Δ=0
external_evidence:   Δ=0
agent_run_log:       Δ=+N (audit only, dry-run 也登)
```

### 2.6 通过标准

| 指标 | 目标 |
|---|---|
| Plan ≥ 5 步 | ✅ |
| 每步 evidence 来源明确 | ✅ |
| 每步 risk_level + approval_required 标 | ✅ |
| dry_run_safe = true 全过 | ✅ |
| 业务表 Δ=0 | ✅ (硬门槛) |
| 用户能基于 plan 决定批/拒 | ✅ |

---

## 3 · 场景 3 · 单目标 draft-run (生成草稿,危险动作进 approval)

### 3.1 用户视角描述

```
顾源源说: "我同意 Claude 跑场景 2 的 Step 5 (生成理事会简版说明),
但跑出来的草稿要进审批面板, 我审过才能用."

用户期望:
- Claude 真生成 markdown 草稿 (用户可读, 不是空模板)
- 草稿放在 approval_queue, 不直接对外
- 用户在前端 approve / reject 真生效
```

### 3.2 输入

```python
# Step 1: 跑文档生成
yiyu_dry_run_action(action_type="generate_board_brief", ...)  # 先预演看会改啥
# Step 2: 真调 documents.generate
POST /api/v1/documents/generate
Headers: X-Actor-Type: external_ai_agent, Idempotency-Key: draft-run-{ts}
Body: {
  "client_id": "client_a4d1db29a7",
  "document_type": "board_brief",
  "goal": "为本月理事会做 5 分钟项目进展汇报"
}
# Step 3: 用户在 UI 审批面板看到 pending
GET /api/v1/approvals?client_id=client_a4d1db29a7
# Step 4: 用户 approve
POST /api/v1/approvals/{approval_id}/approve
Body: {"decided_by": "human:gu", "note": "看过, 可以用"}
```

### 3.3 期望输出(用户视角)

文档生成 endpoint 真返:

```json
{
  "status": "draft",
  "title": "理事会简版说明",
  "approval_required": true,
  "approval_id": "appr_xxx",
  "external_target": true,
  "user_visible_note": "本工具仅生成 draft, 不直接对外发送. 对外材料需先 approve approval_queue 中对应项.",
  "markdown": "# 理事会简版说明\n\n**目标**: 为本月理事会做 5 分钟项目进展汇报\n\n## 项目背景\n- 本周 · 王主任 · 计划\n- 5月 · 补充协议 · 总预算\n- 5月 · CFFC · 会议纪要处理 (5 事实 2 风险)\n\n## 本期重点进展\n- 提交财务可行性报告\n- 下周二前 (内部分工会)\n- 提供更轻量级的试点方案\n\n## 关键风险与对策\n- [medium] 师资不足风险\n- [medium] 学校配合度不足\n\n## 下一步建议\n- 处理 20 个待澄清问题\n- 补 10 个数据缺口\n- 审批 9 个待审批动作\n\n## 待确认项\n- 内部沟通会的具体日期和时间是什么?\n- 复盘中提到的「5 月补充协议」, 系统找到 ...\n\n---\n**草稿生成依据**: ContextPack(active_projects + commitments + risks + clarifications + recommended_next_actions)",
  "evidence_summary": {"contracts": 2, "files": 3, "commitments": 16, ...},
  "context_used": {"task_type": "strategy_narrative", "tables": [9 张], ...}
}
```

### 3.4 期望 DB diff

```
agent_run_log:        +1 (tool_name=documents.generate:board_brief)
approval_queue:       +1 (action_type=document.publish, status=pending)
idempotency_keys_v25: +1
其它业务表:           Δ=0 (draft 不写)

after user approve:
approval_queue:       status pending → approved (同 row 改 status)
                       (不真发送, 因为本 endpoint 是 draft 工具, 不带 publish 动作)
```

### 3.5 通过标准

| 指标 | 目标 |
|---|---|
| status="draft" | ✅ |
| approval_required=true | ✅ |
| approval_id 真返 | ✅ |
| markdown 真有客户数据 (非空模板) | ✅ (用户视角核心) |
| user_visible_note 真给用户提示 | ✅ |
| 业务表 Δ=0 | ✅ |
| approval_queue +1 | ✅ |
| 同 Idempotency-Key 重发 Δ=0 | ✅ |
| 用户能 approve 真生效 | ✅ |

---

## 4 · 用户视角 Sanity Checks (顾源源补充 lens)

每个场景跑完, B 复验时必看:

```
✓ 输出对人类用户有指导价值吗?
  - 场景 1: 用户读了体检报告能知道下一步该干啥
  - 场景 2: 用户读了 plan 能直接选要哪几步、拒哪几步
  - 场景 3: 用户读了草稿能直接拿去改改用,不是从零开始

✓ 输出有真实客户数据吗 (非空模板)?
  - 场景 3 markdown 必须含 CFFC 真实合同金额 / 真实承诺 / 真实风险
  - 不是 "[填这里]" 类占位符

✓ 输出有可执行下一步吗?
  - 场景 1 体检报告必须含"建议下一步"
  - 场景 2 plan 必须每步标 risk + approval
  - 场景 3 草稿必须有"待确认项"section

✓ 输出有诚实标"我不知道"吗?
  - 场景 1 必须列 "🔴 没做到 / blocked"
  - 场景 2 必须标 dry_run_safe + 哪些表会改
  - 场景 3 sections 缺数据时显示 "(公司大脑暂无此项材料, 建议先补证据)"
```

---

## 5 · 三场景跑通后预测的 db 状态

```
跑场景 1 后:
  agent_run_log:           +6-10 (resources + tools 每次 audit)
  business tables:          Δ=0
跑场景 2 后:
  agent_run_log:           +8-12
  business tables:          Δ=0  (全 dry-run)
跑场景 3 后:
  agent_run_log:           +2-3
  approval_queue:          +1 (待用户 approve)
  business tables(除 approval): Δ=0
  user approve 后:
    approval_queue:        status approved (同 row)
    业务表仍 Δ=0 (因为 generate 是 draft 工具, 没 publish 动作)
```

---

## 6 · 给 B 的复验脚本骨架

```bash
#!/usr/bin/env bash
# B 用 (建议)
set -e
LAB=http://127.0.0.1:47831
CID=client_a4d1db29a7
DB="$HOME/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab/app.db"

# 测前 snapshot
RUNS_BEFORE=$(sqlite3 "$DB" "SELECT COUNT(*) FROM agent_run_log")
TASKS_BEFORE=$(sqlite3 "$DB" "SELECT COUNT(*) FROM tasks")

# 场景 1: 外部体检官 (read-only)
curl -sS "$LAB/api/v1/tool-registry" -o /tmp/tr.json
curl -sS "$LAB/api/v1/clients/$CID/agent-state" -o /tmp/state.json
curl -sS "$LAB/api/v1/clients/nonexistent_xxx/agent-state" -w "%{http_code}\n" -o /dev/null  # 期望 404

# 场景 2: dry-run plan
curl -sS -X POST "$LAB/api/v1/actions/suggest" \
  -H "Content-Type: application/json" \
  -H "X-Actor-Type: external_ai_agent" \
  -d "{\"client_id\":\"$CID\"}" | jq '.actions | length'  # 期望 ≥5

curl -sS -X POST "$LAB/api/v1/actions/dry-run" \
  -H "Content-Type: application/json" \
  -d '{"action_type":"create_task_draft","client_id":"'$CID'"}'   # 期望 dry_run_safe=true

# 场景 3: draft-run (含 idempotency)
TS=$(date +%s)
curl -sS -X POST "$LAB/api/v1/documents/generate" \
  -H "Content-Type: application/json" \
  -H "X-Actor-Type: external_ai_agent" \
  -H "Idempotency-Key: bvalidation-$TS" \
  -d "{\"client_id\":\"$CID\",\"document_type\":\"board_brief\",\"goal\":\"理事会汇报\"}" | jq '.status'  # 期望 "draft"

# 测后差异
RUNS_AFTER=$(sqlite3 "$DB" "SELECT COUNT(*) FROM agent_run_log")
TASKS_AFTER=$(sqlite3 "$DB" "SELECT COUNT(*) FROM tasks")

echo "agent_run_log Δ: $((RUNS_AFTER-RUNS_BEFORE)) (期望 ≥6)"
echo "tasks Δ:         $((TASKS_AFTER-TASKS_BEFORE)) (期望 0, draft 不写 tasks)"
```

---

## 7 · 结论

```
3 场景 fixtures 完整:
  · 场景 1 read-only:   6 endpoints, 5 hard checks, 用户视角=体检报告
  · 场景 2 dry-run:     plan ≥5 步, 业务表 Δ=0, 用户视角=可批可拒
  · 场景 3 draft-run:   真生成 markdown 草稿(真客户数据), 走 approval, 用户视角=可改可用

3 场景全过 = MCP v0 + 初步自动工作 真活.

B 复验时 sanity check 4 件 (§4):
  · 用户视角有指导价值
  · 输出含真实客户数据
  · 含可执行下一步
  · 诚实标"我不知道"

报告 docs/A_V3_FINAL_TEST_FIXTURES.md + 桌面 39 号位.
```
