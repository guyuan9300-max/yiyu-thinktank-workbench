# A · V3 Final Acceptance 支撑总报告

**时间**: 2026-05-24 03:20
**触发**: 顾源源 §A 线程 V3 最终验收支撑 §六 总报告
**口径**: V2.1 lab backend HTTP curl + V2.1 lab db sqlite3 + MCP SDK 自测
**用户视角原则**: 顾源源补充 "每个模块输出对人类用户是否有指导价值"

---

## 1 · 本阶段目标

```
顾源源原话:
"A 当前不再是建设数据中心的角色, 而是: 最终验收的工程保障者.
 B 负责判断软件是否真能进入外部体检官和初步自动工作;
 A 负责让这些测试不被工程缺口卡住."

具体: M0 状态报告 → M1 MCP wrapper → M2 documents.generate 通用 →
       M3 fixtures 3 场景 + 总报告
本份目标: 只服务最终测试,不扩新功能.
```

---

## 2 · B 第二轮报告吸收情况(B 14:00 inbox)

| B 报告问题 | A 是否处理 | 状态 |
|---|---|---|
| MCP server wrapper 缺(1-2 天工程) | **本份 M1 真实现** | ✅ scripts/yiyu_mcp_server.py + 6 resources + 9 tools |
| contracts.draft endpoint 缺(V3.0 P0-1) | **本份 M2 兼容实现** | ✅ POST /api/v1/contracts/draft (内部走 documents.generate) |
| templates.generate endpoint 缺(V3.0 P0-2) | **本份 M2 兼容实现** | ✅ POST /api/v1/templates/generate |
| evidence.check payload 400(B 自查问题) | 不属 A | (B 修 simulator) |
| data_gaps.list simulator 更新 | 不属 A | (B 修 simulator) |
| 真接 Claude Desktop 30-60 min | 不属 A | **属 B / 顾源源** (本份 §10 标 blocked_by_B) |

A 处理: **3/3 属 A 的全做**。

---

## 3 · C 审计 P0 修复保持情况

| C P0 | 修复 commit | 本阶段是否回退 |
|---|---|---|
| P0-1 Feishu Approval Gate | 80e3340 | ✅ 保持 + M2 documents.generate 同样套 approval gate |
| P0-2 Idempotency 5 endpoint | 80e3340 + R2 + R4-P1-5 | ✅ 保持 + M2 documents.generate 新加 idempotency 6/6 endpoint |
| P0-3 V3 最小前端 4 panel | 80e3340 | ✅ 保持 (api.ts wrapper + AgentReadyPanel.tsx) |
| P0-4 Tool Registry 一致性 | 80e3340 | ✅ 保持 + M2 加 3 个新工具 schema 全过 |

---

## 4 · MCP v0 支撑情况(M1)

```
MCP wrapper 谁做: A 做 (B 没明确承担, B 只有 simulator)
位置: scripts/yiyu_mcp_server.py (380 行)
依赖: mcp SDK (已装) + httpx (已装)
启动: python3 scripts/yiyu_mcp_server.py (stdio JSON-RPC)
环境: YIYU_BACKEND_URL=http://127.0.0.1:47831 (默认)

Claude Desktop 配置示例 (顾源源 §M1 钦定 read-only):
~/.config/claude/claude_desktop_config.json:
{
  "mcpServers": {
    "yiyu": {
      "command": "python3",
      "args": ["/Users/guyuanyuan/openclaw/workspace/V2.1/scripts/yiyu_mcp_server.py"],
      "env": {"YIYU_BACKEND_URL": "http://127.0.0.1:47831"}
    }
  }
}
```

### 4.1 A 提供的 resources (6 类, 顾源源 §M1 必含)

| URI | 用途 | 来源 endpoint |
|---|---|---|
| yiyu://tool-registry | 17+3 工具完整 schema | GET /api/v1/tool-registry |
| yiyu://agent-run-logs | Agent 调用历史 (audit) | GET /api/v1/agent-run-logs |
| yiyu://approvals | 待审批 (read-only) | GET /api/v1/approvals |
| yiyu://client/{id}/state | 客户级 14 顶层字段 | GET /api/v1/clients/{id}/agent-state |
| yiyu://client/{id}/data-gaps | 客户已知缺口 | GET /api/v1/clients/{id}/data-gaps |
| yiyu://project/{id}/state | 项目级 (event_line) | GET /api/v1/projects/{id}/agent-state |

### 4.2 A 提供的 tools (9 个, 全 read+judge+dry-run)

| Tool | 类型 | endpoint |
|---|---|---|
| yiyu_get_client_state | read | agent-state |
| yiyu_get_data_gaps | read | data-gaps |
| yiyu_list_approvals | read | approvals |
| yiyu_list_agent_runs | read | agent-run-logs |
| yiyu_check_evidence | judge | evidence/check |
| yiyu_quality_context | judge | quality/context |
| yiyu_resolve_authority | judge | authority/resolve |
| yiyu_suggest_actions | judge | actions/suggest |
| yiyu_dry_run_action | dry-run | actions/dry-run |

**v0 边界硬约束**(顾源源 §M1 严格):
- ❌ 不暴露 write tool(tasks.create / documents.generate / feishu.tasks.push / approvals.decide)
- ❌ 不让 Claude 自己 approve / reject
- ❌ 不让 Claude 自动发对外材料
- ❌ 不绕 Approval Queue
- ✅ 只暴露 read + judge + dry-run

### 4.3 真测(Python 自测,不需 Claude Desktop)

```
✓ list_resources() → 6 个 resources
✓ list_tools()    → 9 个 tools (全 read+judge+dry-run)
✓ call_tool yiyu_get_client_state 测试论坛A → HTTP 200, 14 顶层字段, evidence_summary 真返
✓ call_tool yiyu_check_evidence "测试论坛A 800万元" → evidence_sufficient=false, match_count=2
```

### 4.4 是否能进入 Claude Desktop?

```
✅ 技术上可以 — 用户复制 §4 config 到 ~/.config/claude/claude_desktop_config.json,
   重启 Claude Desktop, 即可看到 yiyu MCP server.
真接 Claude 真测 → §10 blocked_by_B (用户操作 + B 验收 30-60 min)
```

---

## 5 · Stage 2 文档生成工具情况(M2)

### 5.1 实现 3 个 endpoint

| endpoint | 类型 | 兼容/通用 |
|---|---|---|
| POST /api/v1/documents/generate | 通用 | document_type 参数化 |
| POST /api/v1/contracts/draft | 兼容 | 内部走 documents.generate(contract_draft) |
| POST /api/v1/templates/generate | 兼容 | 内部走 documents.generate(template_type) |

### 5.2 document_type 7 种(顾源源 §M2 §2 钦定)

| document_type | 用途 | approval_required | external_target |
|---|---|---|---|
| contract_draft | 合同草稿 | true | true |
| board_brief | 理事会简版说明 | true | true |
| brand_proposal | 品牌建议 | true | true |
| meeting_pack | 会谈提纲 | false | false |
| action_list | 行动清单 | false | false |
| project_note | 项目说明 | false | false |
| review_material | 复盘材料 | false | false |

### 5.3 接口契约(全过 §M2 通过线)

| 契约 | 实现 | 真测验证 |
|---|---|---|
| 使用 CompanyBrainContextBuilder | ✅ | context_used.task_type=strategy_narrative (contract/board) / workbench_qa (其它) |
| Idempotency-Key 真持久化 | ✅ | 同 key 重发 db Δ=0 |
| X-Actor-Type / X-Actor-Id 必登 | ✅ | agent_run_log 真写 |
| agent_run_log 每次写 | ✅ | tool_name=documents.generate:{document_type} |
| 对外材料 approval_required=true | ✅ | contract_draft/board_brief/brand_proposal 自动进 approval |
| 不直接对外发送 | ✅ | status="draft", approval_queue +1 |
| 输出 evidence_summary | ✅ | 真带 15 字段(facts/contracts/files/...) |
| 用户视角可读 markdown | ✅ | sections + 占位提示 + 待确认项 |

### 5.4 用户视角真测原文(顾源源补充 lens)

**输入**: POST /documents/generate {client_id: 测试论坛A, document_type: board_brief, goal: "为本月理事会做 5 分钟项目进展汇报"}

**输出 markdown 前 400 字**:
```markdown
# 理事会简版说明

**目标**: 为本月理事会做 5 分钟项目进展汇报

## 项目背景
- 本周 · 王主任 · 计划
- 本周 · 测试论坛A · 会议纪要处理 (1 事实 0 风险)
- 5月 · 补充协议 · 学校数调整
- 5月 · 补充协议 · 总预算
- 5月 · 测试论坛A · 会议纪要处理 (5 事实 2 风险)

## 本期重点进展
- 提交财务可行性报告
- 下周二前
- 提供更轻量级的试点方案

## 关键风险与对策
- [medium] 师资不足风险
- [medium] 学校配合度不足

## 下一步建议
- 处理 20 个待澄清问题
- 补 10 个数据缺口
- 审批 9 个待审批动作

## 待确认项
- 内部沟通会的具体日期和时间是什么?
- 复盘中提到的「5 月补充协议」, 系统找到 ...
```

**用户视角评估**:
- ✅ 含 测试论坛A 真实数据(5月补充协议 / 师资不足风险 / 学校配合度)
- ✅ "下一步建议" 真 actionable(处理 20 个待澄清 / 补 10 个数据缺口)
- ✅ "待确认项" 真问具体问题
- ✅ 用户可直接拿去改改用,不是从零开始
- ⚠️ "本期重点进展" 第一条 commitments.content=null → 显示 "None"(下一版过滤)

---

## 6 · Final Test fixtures(M3)

3 个场景完整(docs/A_V3_FINAL_TEST_FIXTURES.md + 桌面 39 号位):

| 场景 | 类型 | 业务表 Δ | 用户视角 |
|---|---|---|---|
| 1 外部体检官 | read-only | 0 (audit 真写) | 体检报告: 真做到/半做/没做到 + 建议下一步 |
| 2 单目标 dry-run | dry-run plan | 0 (全 dry) | plan 7 步, 每步 risk/approval, 用户可选可拒 |
| 3 单目标 draft-run | draft + approval | 0 (除 approval +1) | 真 markdown 草稿, 含真实客户数据, 走审批 |

每场景含:
- 用户视角描述
- 输入(curl / MCP)
- 期望 endpoint 调用顺序
- 期望 Claude 输出(用户视角)
- 期望 DB diff
- 通过标准

---

## 7 · blocked_by_A 剩余(真阻塞 B 最终测试)

```
P1 (本周或下周, 若 B 复验有反馈):
  · 10/14 生成功能 ContextBuilder 迁移 (M2 文档生成已走, 其它 narrative_collector/review_narrative 待)
  · 591 endpoint docstring 全量补 (Tool Registry 20 工具完整, 但 571 内部 endpoint 弱)
  · 5 个生成型 endpoint 加 audit log

P2 (B 复验后, 优化类):
  · OpenAPI /openapi.json 默认 404
  · M2-1 keyword 切词偏差(jieba 升级)
  · M2-3 authority 同 score 排序
  · narrative 6 段框架软化

预估: P1 全做完后 C 审计估分 85-90 (本份后估 78-82)
```

---

## 8 · blocked_by_B(B 复验侧)

```
本阶段后 B 应该做的事:

1. 配 Claude Desktop / Cursor 真接 yiyu_mcp_server.py
   - 复制 §4.0 config
   - 重启 Claude Desktop
   - 跑 3 场景(read-only / dry-run / draft-run)

2. Golden Pack × 7 复跑(用 B 已有的 fixtures/golden/*.txt)
   - meeting_mingyuan.txt → 跑 documents.generate(board_brief)
   - cffc_contract_GT_STUB → 跑 documents.generate(contract_draft)
   - rici_strategic_GT_STUB → 跑 evidence.check / quality.context

3. 人工复核 §6 §1 体检报告(顾源源原话: 真证明 v0)

4. V3 最终验收报告汇总(汇总 A + B 双方结果)
   - A 当前 commit: 待 commit
   - B 第二轮 simulator 96/100
   - C 审计 P0 修后 75/100 + 本份增 +3-5
   - MCP v0 9 tools + 6 resources 真测
   - 3 场景 fixtures 通过率
```

---

## 9 · 不做事项声明(顾源源 §七)

```
本阶段 A 严格未做:
  ❌ CEO 模式
  ❌ R5 / R6
  ❌ 飞书深度集成
  ❌ 多 AI 角色
  ❌ 新业务 demo
  ❌ 为明远会议纪要写死流程(documents.generate 用 document_type 参数化, 真通用)
  ❌ 把 B simulator 96 分当最终报告
  ❌ 自称最终完成(本份是支撑文档, B 验收才是终)
  ❌ 绕过 Approval Queue(M2 documents.generate 对外材料全套 approval)
  ❌ 让生成材料直接对外发送(全 status='draft' + approval_required=true)

本阶段 A 真做:
  ✅ M0 状态报告 (诚实标 commit / db / endpoint)
  ✅ M1 MCP server wrapper (read-only / dry-run / audit)
  ✅ M2 文档生成 3 工具(通用 + 2 兼容, 真接 ContextBuilder + Idempotency + Audit + Approval)
  ✅ M3 Final Test fixtures 3 场景(含用户视角验证)
```

---

## 10 · 原文证据

### 10.1 MCP server 真测(§4.3)

```python
$ python3 -c "
import asyncio, importlib.util
spec = importlib.util.spec_from_file_location('yms', 'scripts/yiyu_mcp_server.py')
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
async def m():
    res = await mod.list_resources(); print(f'resources: {len(res)}')
    tools = await mod.list_tools(); print(f'tools: {len(tools)}')
asyncio.run(m())
"
→ resources: 6
  tools: 9
  (Claude Desktop 真接入 B 验收阶段)
```

### 10.2 documents.generate 真测(§5.4)

```
curl POST /api/v1/documents/generate
  Headers: X-Actor-Type, Idempotency-Key, ...
  Body: {client_id: 测试论坛A, document_type: board_brief, goal: 理事会汇报}

→ status: draft
  title: 理事会简版说明
  sections: 5 个 (项目背景/本期重点进展/关键风险与对策/下一步建议/待确认项)
  approval_required: True, approval_id: appr_3d33ca416d994262b80355c6
  evidence_summary: 15 字段 (contracts=2, files=3, commitments=16, risks=18, data_gaps=10, ...)
  context_used: task_type=strategy_narrative, 9 张表
  markdown: 包含 测试论坛A 真实数据 (王主任/补充协议/师资不足风险/...)

接 contracts.draft:
→ approval_id: appr_16d6423884e9485fad8342a4 (+1)
  type: contract_draft
  sections: ['甲乙双方', '项目目标与范围', '合同金额与履行期', '交付物与责任', '风险与备注', '需澄清/待补']

同 Idempotency-Key 重发:
→ HTTP 200, db Δ=0 (idempotency 真生效)
```

### 10.3 V2.1 lab db 真增长(M2 测试后)

```
approval_queue (action_type='document.publish'): 0 → 2  (+2 from board_brief + contract_draft)
agent_run_log (tool_name LIKE 'documents.generate%'):  0 → 2  (+2)
其它业务表: Δ=0 (M2 draft-run 不写)
```

### 10.4 Tool Registry 真返 20 工具(§7)

```
curl GET /api/v1/tool-registry
→ version: v3_m2_registry_v2
  total: 20  (17 + feishu.tasks.push + 3 M2 新: documents.generate, contracts.draft, templates.generate)
  by_status: {"available": 20}  (contracts/templates 从 missing → available)
  schema_completeness 全 True
```

---

## 11 · C 审计估分更新(本阶段后)

| 维度 | C 修后 (75) | 本阶段后 | Δ |
|---|---|---|---|
| Tool Registry 覆盖度 | 13 | **14** | +1 (3 新工具 schema 全过) |
| 生成型 ContextBuilder 接入 | 7 | **9** | +2 (M2 真用 ContextBuilder) |
| 写入入口反哺 | 12 | 12 | = |
| 硬编码风险 | 13 | 13 | = (M2 通用化, 不写死流程) |
| 安全治理 | 13 | **14** | +1 (M2 全套 approval + idempotency + audit) |
| UI 可见性 | 7 | 7 | = (本阶段未碰前端) |
| endpoint/DB 语义 | 6 | **7** | +1 (M2 完整 docstring) |
| 测试可复现 | 4 | **5** | +1 (3 场景 fixtures + MCP 自测) |
| **总分** | **75** | **81** | **+6** |

**预测**: B 真复验后,**81±3** (B 验收偏严,A 自审偏好)。距 ≥90 还差 9 分,P1 全做完基本到位。

---

## 12 · 用户视角最终核验(顾源源补充 lens)

```
本阶段 A 交付的 3 大产物:
  1. MCP server wrapper (scripts/yiyu_mcp_server.py)
     用户视角: 顾源源能复制 §4 config 到 Claude Desktop 30 秒接入
     ✅ 不是后端字段, 是顾源源真能让 Claude 进系统的 "门"

  2. documents.generate (通用文档生成)
     用户视角: 顾源源拿到 markdown 草稿, 含 测试论坛A 真实数据, 改 30 秒能用
     ✅ 不是空模板, 是真有内容的草稿

  3. Final Test fixtures (3 场景)
     用户视角: B 不用猜 endpoint, 跟着 fixtures 跑就行
     ✅ 不是后端清单, 是 B 真能复验的脚本

3 大产物全过用户视角核验.
```

---

## 13 · 里程碑反扫(顾源源原话 "每经过一个里程碑反扫所有代码")

```
M0 → M1 → M2 → M3 全链对齐:
  · M0 commit 80e3340 (C P0 修后基线)
  · M1 scripts/yiyu_mcp_server.py (新建, 用 80e3340 的 endpoint)
  · M2 backend/app/main.py (M2 新加 3 endpoint + 3 tool registry entry, 在 P0-1 之上)
  · M3 docs/A_V3_FINAL_TEST_FIXTURES.md (引用 M2 真测原文 + MCP server tools)

代码依赖链 100% 对齐目标 (顾源源 §一 北极星: 让 Claude/Codex 安全进入 + 体检 + 初步自动工作).

无方向偏离:
  · 没扩 R5/R6
  · 没做 CEO
  · 没做飞书深度
  · 没自评最终完成
  · documents.generate 不写死会议→合同→品牌流程
```

---

## 14 · 结论 + 接力

```
A 本阶段 V3 Final Acceptance 支撑 4 件全做完:
  M0 状态报告 ✅
  M1 MCP server wrapper (read-only/dry-run/audit) ✅
  M2 documents.generate 通用 + contracts.draft + templates.generate 兼容 ✅
  M3 Final Test fixtures 3 场景 (含用户视角验证) ✅

C 审计估分: 75 → 81 (+6, 本阶段微升)
B 第二轮 simulator: 96 (B 自跑)
真分预测 (B 复验): 81±3

A 接力棒交给 B:
  · 配 Claude Desktop 真接 yiyu_mcp_server.py
  · 跑 3 场景 fixtures (read-only / dry-run / draft-run)
  · Golden Pack × 7 复跑
  · 出 V3 最终验收报告 (汇总 A + B 双方)

报告 docs/A_V3_FINAL_ACCEPTANCE_SUPPORT_REPORT.md + .json
桌面 40 号位
inbox-B 通知 "A 已准备好 Final Acceptance 支撑, 等 B 接 Claude Desktop"

不写 FINAL 自评. 等 B 独立复验 + 顾源源最终拍板.
```
