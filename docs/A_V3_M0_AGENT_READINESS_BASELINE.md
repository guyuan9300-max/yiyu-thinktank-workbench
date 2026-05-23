# A · V3 收尾 M0 Agent Readiness 新基线

**时间**: 2026-05-23 23:55
**触发**: 顾源源 V3.0 Agent-Ready 数据中心收尾任务 §M0 — 不改代码,按新 7 维度评分
**口径**: V2.1 lab backend HTTP curl + OpenAPI 探测 + grep 硬编码初筛

---

## 0 · 新基线总分

```
M0 Agent Readiness:  50 / 100   (上轮 baseline 27.75, +22.25 来自 M1-M3 已 commit endpoint)
距顾源源通过线 ≥90:  -40 分
```

新评分维度(顾源源 §M0 钦定):

| 维度 | 分值 | 实测 | 短板 |
|---|---|---|---|
| 1. Agent State 可读性 | 20 | **12** | project-level agent-state 缺(404), 顶层独立字段未拆 |
| 2. Tool Registry 准备度 | 15 | **5** | endpoint 全 404, 仅 B docs 有 |
| 3. Data Gap 可调用性 | 15 | **6** | endpoint 在但字段命中 2/10 |
| 4. Run Log / Approval 可审计性 | 15 | **14** | M1-4/M1-5 + R2 approvals 全活 ★ |
| 5. endpoint 语义说明完整度 | 15 | **5** | openapi.json 404 + 缺 when_to_use/risk_level/approval_required |
| 6. 表业务含义完整度 | 10 | **2** | 无 schema dict / 表关系文档 |
| 7. 无硬编码风险初筛 | 10 | **6** | grep client_id 硬编码 0 / "第一步必须" 0 / 待 M4 详扫 |
| **总分** | **100** | **50** | — |

---

## 1 · 维度 1 · Agent State 可读性 12/20

### 1.1 client-level agent-state (上轮 M1-1 已做)

```
GET /api/v1/clients/{id}/agent-state → 200 ✅
返回字段(11 个):
  · client_id / task_type / evidence_summary
  · used_tables (9 张)
  · top_contracts (2) / top_files (3) / pending_clarif (5) / pending_appr (5)
  · uncertainty_summary / recommended_actions
  · recommended_next_actions (5 条, 上轮 M1 新加)
```

### 1.2 project-level agent-state ❌ 缺(顾源源新要求)

```
GET /api/v1/projects/{project_id}/agent-state → 404
```

### 1.3 顶层独立字段 vs 嵌套字段

顾源源 §M1 要求:
```json
{
  "client_profile": {},          // 顶层  当前: 嵌在 evidence_summary
  "active_projects": [],          // 顶层  当前: 缺
  "latest_events": [],            // 顶层  当前: 嵌在 evidence_summary.timeline_events 计数
  "file_identities": [],          // 顶层  当前: top_files (only 3)
  "contract_structures": [],      // 顶层  当前: top_contracts (only 2)
  "historical_reference_links": [],// 顶层 当前: 缺
  "commitments": [],              // 顶层  当前: 仅计数
  "risk_signals": [],             // 顶层  当前: 仅计数
  "clarifications": [],           // 顶层  当前: pending_clarifications_list (5)
  "approval_queue": [],           // 顶层  当前: pending_approvals_list (5)
  "data_gaps": [],                // 顶层  当前: 仅计数
  "agent_run_logs": [],           // 顶层  当前: 缺
  "recommended_next_actions": [], // 顶层  ✅ 已有
  "evidence_summary": {}          // 顶层  ✅ 已有
}
```

**评分 12/20**: 已有 5/14 顶层字段; 缺 9 个(M1 阶段补)。

---

## 2 · 维度 2 · Tool Registry 准备度 5/15

### 2.1 endpoint 探测

```
GET /api/v1/tool-registry  → 404
GET /api/v1/tools           → 404
GET /api/v1/openapi.json    → 404 (FastAPI 默认 /openapi.json 未暴露)
```

### 2.2 B 已有的 Tool Registry docs(部分基础)

```
docs/B_V3_M1_TOOL_REGISTRY_V1.md → 13.5 KB
11 工具 schema 已就绪:
  ✅ meeting_minutes.process / workspace.chat / company_brain.context
  ✅ approvals.list / approvals.decide / smart_import.classify
  ✅ text.resolve-history / tasks.create / documents.fill_template
  🔴 contracts.draft / templates.generate (blocked)
还需添加 (A 上轮 M1-M3 新做的 6 个):
  · clients.agent_state / data_gaps.list / data_gaps.compensate
  · agent_run_logs.list / agent_run_logs.detail
  · evidence.check / quality.context / authority.resolve
  · actions.suggest / actions.dry_run
```

**评分 5/15**: docs 在但 endpoint 缺,M2 补。

---

## 3 · 维度 3 · Data Gap 可调用性 6/15

### 3.1 endpoint 状态

```
GET /api/v1/clients/{id}/data-gaps                → 200 ✅ (上轮 M1-2)
POST /api/v1/clients/{id}/data-gaps/compensate     → 200 ✅ (上轮 M1-3)
```

### 3.2 字段命中(顾源源 §M3 必返 10 字段)

```
顾源源要求:                当前返回:
  gap_id                  ✅ (id)
  gap_type                ✅
  description             ❌
  missing_evidence        ❌
  related_facts           ❌ (有 related_fact_ids 但不是顾源源要求的格式)
  related_files           ❌
  suggested_tools         ❌
  suggested_clarification ❌
  priority                ❌ (有 severity, 名字不同)
  approval_required       ❌

命中 2/10 (gap_id + gap_type)
```

**评分 6/15**: endpoint 可调,但字段严重缺,M3 升级。

---

## 4 · 维度 4 · Run Log / Approval 可审计性 14/15

```
GET  /api/v1/agent-run-logs        → 200 ✅ (M1-4)
GET  /api/v1/agent-run-logs/{id}   → 200 ✅ (M1-5)
GET  /api/v1/approvals             → 200 ✅
POST /api/v1/approvals/{id}/approve → 200 ✅ (M1 真测 + 回滚)
POST /api/v1/approvals/{id}/reject  → 真活 ✅
POST /api/v1/approvals/decide       → 422(schema 不匹配, 但路径活)
```

**评分 14/15**: 核心齐 ★,缺 -1 是前端 approval 处理 UI 未做(顾源源硬门槛 #9)。

---

## 5 · 维度 5 · endpoint 语义说明完整度 5/15

### 5.1 OpenAPI 总体可发现性

```
GET /api/v1/openapi.json   → 404
GET /docs                   → 404
```

FastAPI 默认有 `/openapi.json`,V2.1 lab 启动参数禁用了。**Agent 无法自动发现 endpoint**。

### 5.2 单 endpoint 元信息

| 信息 | 当前 | 顾源源要求 |
|---|---|---|
| description | ✅(docstring 中文) | ✅ |
| summary | 部分 | ✅ |
| input schema | ✅(Pydantic 自动) | ✅ |
| output schema | 部分 | ✅ |
| when_to_use | ❌ | ✅ |
| when_not_to_use | ❌ | ✅ |
| risk_level | ❌ | ✅ |
| approval_required | ❌ | ✅ |
| example_input | ❌ | ✅ |
| example_output | ❌ | ✅ |

**评分 5/15**: 基础描述在,关键元数据全缺(M2 Tool Registry 暴露时补)。

---

## 6 · 维度 6 · 表业务含义完整度 2/10

```
docs/ 查找:
  · data dict / schema doc / business meaning → 0
  · 只有 B_AI_PHASE_1_EMPTY_TABLES_AUDIT.md(空表审计, 不是业务含义)
```

V2.1 lab 17 张核心表(atomic_facts / contract_structures / file_identities / ...)无对应业务含义文档,**Agent 不知道表代表什么业务概念**。

**评分 2/10**: 几乎没有。M6 Handoff 文档时一并补。

---

## 7 · 维度 7 · 无硬编码风险初筛 6/10

```
grep 检测(M0 阶段只初筛, M4 详扫):

· 硬编码 client_id 字符串:
    grep 'client_a4d1db29a7|client_284afd836e' backend/app/services/  → 0 ✅
· prompt 写死流程:
    grep '第一步必须|然后调|elif meeting_minutes' backend/app/services/  → 0 ✅
· 客户名硬编码:
    grep 'CFFC|日慈|益语智库' backend/app/services/  待 M4 详扫
```

**评分 6/10**: 初筛过 + 关键模式 0 命中。M4 系统扫(后端 service + main.py + prompt 全覆盖)。

---

## 8 · 缺口清单(M1-M6 修复路径)

| 缺口 | 当前分 | 目标分 | 修复在 | 工作量 |
|---|---|---|---|---|
| project-level agent-state + 顶层独立字段 | 12/20 | 20/20 | **M1** | 中 |
| Tool Registry endpoint + 17 工具完整 | 5/15 | 14/15 | **M2** | 中 |
| data-gaps 字段升级(命中 2/10→10/10) | 6/15 | 14/15 | **M3** | 中 |
| Run Log/Approval 前端 UI | 14/15 | 15/15 | M6 留 P2(M4-M5 不碰) | - |
| OpenAPI 暴露 + when_to_use/risk_level/approval_required | 5/15 | 13/15 | **M2** Tool Registry 一并 | 低 |
| 表业务含义文档 | 2/10 | 9/10 | **M6** Handoff 一并 | 中 |
| 硬编码全扫(高危=0) | 6/10 | 10/10 | **M4** | 高(grep+人工) |
| **总预期** | 50 | **95+** | — | 一气做完 |

---

## 9 · 10/10 硬门槛对照

| # | 硬门槛 | M0 |
|---|---|---|
| 1 | 客户级生成不 single_file_only | ✅ |
| 2 | 写入入口必须 source_registry | ✅ |
| 3 | 历史材料提及必须尝试回指 | ✅ |
| 4 | 不确定必须进澄清 | ✅ |
| 5 | 外部证据不覆盖内部权威 | ✅ |
| 6 | 方法卡不污染客户事实 | ✅ |
| 7 | 用户纠错改变后续回答 | ✅(M2 authority_score) |
| 8 | 跨客户串线 0 | ✅✅ |
| 9 | 前端不可见不算 | ⚠️ M3+ Approval UI 后续 |
| 10 | 没原文不算完整 | ✅(本报告 §1-7 7 维度真原文) |

---

## 10 · 顾源源 8 项禁止 自检

| # | 禁止 | M0 |
|---|---|---|
| 1 | 不直接做外置 Codex CLI | ✅ |
| 2 | 不做 CEO Skill | ✅ |
| 3 | 不做完整 MCP server(B 设计未落档前) | ✅ |
| 4 | 不写明远会议纪要硬编码流程 | ✅ |
| 5 | 不做 R5/R6 | ✅ |
| 6 | 不做飞书深度接入 | ✅ |
| 7 | 不写新的"终极评估" | ✅(本报告是 M0 基线) |
| 8 | 不用 snapshot / dogfood 自证 | ✅(全 V2.1 lab) |

---

## 11 · 执行序

按顾源源 §七 严格顺序:

```
M0 ✅ (本报告)
→ M1 client+project agent-state 顶层独立字段补齐
→ M2 Tool Registry endpoint + 17 工具 schema + OpenAPI 元数据
→ M3 data-gaps 字段升级 (2/10 → 10/10)
→ M4 硬编码风险全扫(backend + prompts)
→ M5 R4-P1 剩余: 粘贴生成接 ContextBuilder + chat 反向入库分类升级
→ M6 MCP-Ready Handoff + 表业务含义 + 总报告

每个里程碑: commit + 桌面同步 + baton 释放 + inbox-B append.
```

---

## 12 · 结论

```
M0 新基线 50/100(诚实):
  · 上轮做的 M1-M3 endpoint 加分明显 (27.75 → 50)
  · 但顾源源新维度评分严格(语义说明/表业务含义/Tool Registry endpoint)
  · 短板 = Tool Registry + Data Gap 字段 + OpenAPI 语义

距 ≥90 通过线: 40 分.

不修, 立即按 §七 顺序补齐 M1-M6.
报告 docs/A_V3_M0_AGENT_READINESS_BASELINE.md + 桌面 26 号位.
```
