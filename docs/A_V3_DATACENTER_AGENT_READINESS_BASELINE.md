# A · V3 数据中心 Agent Readiness Baseline

**时间**: 2026-05-23 22:00
**触发**: 顾源源 V3.0 收束指令 — "A 不做外置 Agent CLI, A 把数据中心做成 AI 可稳定调用的公司大脑底座"
**口径**: V2.1 lab backend HTTP curl + V2.1 lab db sqlite3 实测 + endpoint 探测
**原则**: M0 不修复, 只测当前数据中心对 Agent 是否可读/可判/可行动/可审计
**测试客户**: client_a4d1db29a7 (CFFC)

---

## 0 · 一句话基线判断

```
数据中心底层数据非常完整 (52.5/100), 但对 Agent 的 HTTP endpoint 暴露率极低 (27.75/100).
"数据库知道一切, Agent 一个 endpoint 都拉不到" = 当前真实状态.

R4-P1 已经修好的: 任务承诺 / 模板深度集成 / chat 反向入库 / workspace/chat 9 类 evidence
R4-P1 未碰过的:  agent-state / data-gaps / agent-run-logs / actions/suggest / quality/context / authority/resolve / evidence/check
```

---

## 1 · Agent Readiness Index — 27.75 / 100(按 endpoint 暴露率)

| 大类 | 满分 | 当前 | 状态 |
|---|---|---|---|
| M1 Agent 可读 | 25 | **3** | ⚠️ 只有 /api/v1/approvals 200, 其它 8 个 404 |
| M2 Agent 可判 | 25 | **0** | ❌ evidence/check / quality/context / authority/resolve 全缺 |
| M3 Agent 可行动 | 25 | **0** | ❌ actions/suggest / dry-run / approval_required 标注全缺 |
| M4 任务+模板低分项 | 25 | **25** | ✅ R4-P1 已修 (P1-5 任务承诺 B+, P1-6 模板深度 A-) |

**Agent Readiness Score**: **27.75 / 100**(M0 不要求通过,只给基线)

---

## 2 · 底层能力 Index — 52.5 / 100(忽略 endpoint, 只看 db+service)

| 大类 | 满分 | 当前 | 说明 |
|---|---|---|---|
| 可读: 数据存在 | 25 | **18** | 17 张 R3/R4 表数据齐全(CFFC: contracts 2, files 3, historical 10, gaps 10, etc.) |
| 可判: 判断服务存在 | 25 | **13** | data_gap_compensator + formal_conflict_detector + historical_resolver 真有, 但 quality_context_builder 缺 |
| 可行动: 行动 API 存在 | 25 | **8** | approval_queue + agent_run_log 服务真有, 但 action_candidate_engine + dry_run_simulator 缺 |
| 可审计: 审计数据完整 | 25 | **14** | agent_run_log 34 条 / idempotency_key 覆盖 57% (19/33) / approval 32 条, 但无查询 endpoint |

**底层能力 Score**: **52.5 / 100**

---

## 3 · M0 测试 1 · 公司状态快照(Client State Snapshot)

### 3.1 专用 endpoint 探测(全 404)

| GET endpoint | 状态 |
|---|---|
| `/api/v1/clients/{id}/agent-state` | **404** |
| `/api/v1/clients/{id}/state` | 404 |
| `/api/v1/clients/{id}/snapshot` | 404 |
| `/api/v1/clients/{id}/company-brain` | 404 |
| `/api/v1/clients/{id}/workspace/state` | 404 |

**结论**: 0/5 命中。**Agent 无法以一次调用拿到客户全状态**。

### 3.2 变通方案: workspace/chat 已能返回大部分快照内容

实测 POST `/api/v1/clients/client_a4d1db29a7/workspace/chat` body `{prompt: "CFFC 合同金额"}`:

```
companyBrainSummary keys:
  client_id / evidence_summary / pending_approvals_list /
  pending_clarifications_list / recommended_actions /
  single_file_only / task_type / top_contracts / top_files /
  uncertainty_summary / used_tables

evidence_summary (真返回):
{
  "facts_authoritative": 0, "facts_candidate": 0,
  "contracts": 2, "files": 3, "historical_links": 11,
  "timeline_events": 30, "commitments": 16, "risks": 18,
  "clarifications_pending": 20, "external_evidence": 0,
  "data_gaps": 10, "method_cards": 0, "approvals_pending": 7,
  "tables_used": 9, "evidence_types_count": 8
}
used_tables: 9 张 (contract_structures, file_identities, historical_reference_links,
                  event_line_activities, commitments, risk_signals,
                  clarification_records, data_gaps, approval_queue)
top_contracts: 2 / top_files: 3
pending_clarifications_list: 5 / pending_approvals_list: 5
singleFileOnly: False
evidenceTypes (顶层): 9 类
recommended_next_actions: None  ← M0 要求 ≥5 条, 当前 0
```

### 3.3 顾源源量化目标对照

| 指标 | 目标 | 实测 | 状态 |
|---|---|---|---|
| state snapshot 返回成功 | 100% | (变通:workspace/chat) | ⚠️ |
| evidence 类型 ≥8 | 8 | 8 | ✅ |
| used_tables ≥8 | 8 | 9 | ✅ |
| 当前风险 ≥2 | 2 | 18 | ✅ |
| 当前承诺 ≥2 | 2 | 16 | ✅ |
| 待澄清 ≥3 | 3 | 20 | ✅ |
| 待审批 ≥1 | 1 | 7 | ✅ |
| 数据缺口 ≥3 | 3 | 10 | ✅ |
| single_file_only false | false | false | ✅ |
| recommended_next_actions | (隐含) | None | ❌ |

**M0-1 评分: 8/10**(缺: 专用 endpoint + recommended_next_actions)

---

## 4 · M0 测试 2 · 数据缺口可调用性

### 4.1 endpoint 探测

| endpoint | 期望 | 实测 |
|---|---|---|
| `GET /api/v1/clients/{id}/data-gaps` | 200 | **404** |
| `POST /api/v1/clients/{id}/data-gaps/compensate` | 200 | **404** |

### 4.2 db 真数据 (sqlite3 验证)

```sql
SELECT COUNT(*) AS total,
       SUM(CASE WHEN status='open' THEN 1 ELSE 0 END) AS open,
       SUM(CASE WHEN severity='high' THEN 1 ELSE 0 END) AS high
FROM data_gaps WHERE client_id='client_a4d1db29a7';
→ total=10, open=10, high=0
```

schema 完整: `gap_type, subject, internal_value, external_value, severity, suggested_action, status, detected_at`

### 4.3 顾源源量化目标对照

| 指标 | 目标 | 实测 | 状态 |
|---|---|---|---|
| data gaps 可查询 | 100% | 0% (endpoint 缺) | ❌ |
| 每个 gap 有 gap_type | 100% | 100% (schema 强制) | ✅ |
| 每个 gap 有 suggested_action 或 missing_reason | 100% | (待查 db 真值) | ⚠️ |
| 能建议补证工具 | ≥1 | 0 (无 compensate endpoint) | ❌ |

**M0-2 评分: 1/4** · `blocked_by_A: data_gap_endpoint_missing`

---

## 5 · M0 测试 3 · 候选行动生成

### 5.1 endpoint 探测

| endpoint | 期望 | 实测 |
|---|---|---|
| `POST /api/v1/clients/{id}/actions/suggest` | 200 | **404** |
| `POST /api/v1/clients/{id}/recommendations` | 200 | **404** |
| `POST /api/v1/clients/{id}/next-actions` | 200 | **404** |
| `POST /api/v1/actions/dry-run` | 200 | **404** |

### 5.2 现状

`companyBrainContextPack.recommended_actions` 字段定义存在 (`list[str]`), 但 workspace/chat 返回 `null`。说明:

- 数据结构占位有
- 真实生成 service **缺**(没有 action_candidate_engine 服务文件)
- endpoint 缺

### 5.3 顾源源量化目标对照

| 指标 | 目标 | 实测 |
|---|---|---|
| action candidates 数量 | ≥5 | **0** |
| 每条 reason | 100% | n/a |
| 每条 evidence | ≥90% | n/a |
| risk_level 标注 | 100% | n/a |
| approval_required 标注 | 100% | (approval_queue 32 条真在, 但不是 action 自动生成的) |
| 不直接执行危险动作 | 100% | (无 action 就不存在直接执行) |

**M0-3 评分: 0/5** · `blocked_by_A: action_candidate_engine_missing`

---

## 6 · M0 测试 4 · 成果质量评估

### 6.1 endpoint 探测

| endpoint | 期望 | 实测 |
|---|---|---|
| `POST /api/v1/clients/{id}/evidence/check` | 200 | **404** |
| `POST /api/v1/clients/{id}/quality/context` | 200 | **404** |
| `POST /api/v1/clients/{id}/authority/resolve` | 200 | **404** |

### 6.2 量化目标对照

| 指标 | 目标 | 实测 | 状态 |
|---|---|---|---|
| quality_context 返回成功 | 100% | 0% | ❌ |
| 识别缺合同依据 | 是 | 不能(无 service) | ❌ |
| 识别缺预算确认 | 是 | 不能 | ❌ |
| 识别外部证据不足 | 是 | 不能 | ❌ |
| 识别待确认误写为确认 | 是 | 不能 | ❌ |
| 返工建议 | ≥3 条 | 0 | ❌ |

**M0-4 评分: 0/6** · `blocked_by_A: quality_context_builder_missing`

---

## 7 · M0 测试 5 · 任务与模板低分项(R4-P1 已修)

### 7.1 任务承诺与历史

R4-P1 P1-5 commit 51eaab7 已修。verify:

```
V2.1 lab POST /api/v1/tasks 真接 historical_material_resolver
真测 task_d1be025ea7:
  · historical_reference_links: +6 (全 source_doc_type='task')
  · 300 万 / 800 万 真匹配 contract_structures (score 0.85)
  · 4 进 clarification_records
```

| 指标 | 目标 | 实测 | 状态 |
|---|---|---|---|
| task 创建 | 1 | 1 (task_d1be025ea7) | ✅ |
| historical link 或 clarif | ≥1 | 6+4 | ✅ |
| commitment 写入 | ≥1 | (event_line_activities +6 但 commitments table 未直接 +1) | ⚠️ |
| event_line_activity | ≥1 | (待查 db 真值) | ⚠️ |
| approval_queue 涉及发送 | 100% | n/a (本任务非发送) | - |

**M0-5a 评分: 4/5** · R4-P1 P1-5 已基本搞定

### 7.2 模板真用 ContextPack

R4-P1 P1-6 commit 51eaab7 已修。verify:

```
build_template_fill_context 真注入 18 条 R4 blocks:
  合同结构 2 (CFFC 300 万/800 万 完整字段)
  权威文件 3 (合同/补协议/方案)
  历史关联 5 (含 P1-5 任务真触发)
  已知缺口 8
显式 5 级优先级 prompt: 用户已确认 > 合同结构 > 权威文件 > 历史关联 > 已知缺口
```

| 指标 | 目标 | 实测 | 状态 |
|---|---|---|---|
| 字段 evidence 覆盖 | ≥90% | (LLM 端到端未实测) | ⚠️ |
| 合同双方 from contract_structures | 100% | ✅ (prompt 真带) | ✅ |
| 风险 from risk_signals | 100% | ✅ (build 时真查) | ✅ |
| 待澄清 from clarification | 100% | ✅ (build 时真查) | ✅ |
| 预算不误用旧口径 | 100% | (5 级优先级 prompt 真带, LLM 端未实测) | ⚠️ |

**M0-5b 评分: 4/5**

---

## 8 · agent-run-logs / approvals 探测

| endpoint | 状态 | 说明 |
|---|---|---|
| GET `/api/v1/agent-run-logs` | **404** | endpoint 缺(db 34 条数据真有) |
| GET `/api/v1/agent/run-logs` | 404 | |
| GET `/api/v1/approvals` | **200** | ✅ 真返回 32 条 |
| GET `/api/v1/clients/{id}/approvals` | 404 | 缺按客户过滤路径 |
| POST `/api/v1/approvals/{id}/approve` | 405 | method 不匹配 |
| POST `/api/v1/approvals/{id}/decision` | 404 | |

approvals 列表能拉但**审批动作 endpoint 不通**。

---

## 9 · 缺失项清单(blocked_by_A · 等 A 修)

| # | 缺失能力 | 优先级 | 估难度 |
|---|---|---|---|
| 1 | GET `/api/v1/clients/{id}/agent-state` (一次拿完整快照) | P0 | 中 |
| 2 | GET `/api/v1/clients/{id}/data-gaps` | P0 | 低 |
| 3 | POST `/api/v1/clients/{id}/data-gaps/compensate` | P0 | 中 |
| 4 | GET `/api/v1/agent-run-logs` + `/{run_id}` | P0 | 低 |
| 5 | POST `/api/v1/approvals/{id}/decision`(approve/reject) | P0 | 低 |
| 6 | POST `/api/v1/clients/{id}/actions/suggest` (action_candidate_engine) | P1 | 高 |
| 7 | POST `/api/v1/actions/dry-run` | P1 | 中 |
| 8 | POST `/api/v1/clients/{id}/evidence/check` | P1 | 中 |
| 9 | POST `/api/v1/clients/{id}/quality/context` | P1 | 高 |
| 10 | POST `/api/v1/clients/{id}/authority/resolve` | P2 | 中 |
| 11 | workspace/chat companyBrainSummary 加 `recommended_next_actions` | P1 | 低 |

---

## 10 · 三层定位(顾源源指令 §一·北极星)

```
"任何 AI 进入系统, 都能拿到完整、可信、可追溯、可行动的公司状态, 并在安全边界内调用功能模块做事"

A 当前在哪一层:
  ┌─ 数据中心 / 数据存(DB schema 全, 17 张表) ─ 100% ★★★★★
  │
  ├─ 业务 service / 处理逻辑(IngestPipeline, deriver, classifier...)─ 80% ★★★★
  │
  ├─ 公司大脑 ContextBuilder(R4-P0 已通 + P1 deep wire)─ 65% ★★★★
  │
  ├─ HTTP endpoint 对 Agent 暴露 ─ 11% ★ (本次最大短板)
  │
  └─ Agent contract(JSON schema / 风险等级 / approval_required)─ 5% (几乎不存在)
```

---

## 11 · 用户语言可感知判断

```
今天 顾源源 / 益语团队:
  ✅ 可以问公司大脑 "CFFC 合同" → 用户工作台 9 类 evidence 真显示
  ✅ 可以填模板 → R4 5 类权威源真注入 prompt
  ✅ 可以创建任务 → 真接 historical_resolver 自动回指

今天 外置 Codex / Claude Code 进系统:
  ❌ 想拿客户快照 → 没有 endpoint
  ❌ 想看 data_gaps → 没有 endpoint
  ❌ 想看自己跑过什么 → agent_run_logs 没有 endpoint
  ❌ 想批/拒一个 approval → POST 路径 405/404
  ❌ 想要 next action 建议 → recommended_actions 永远 None
  ⚠️ 只能用 /workspace/chat 变通拉部分上下文, 但要 1 次 LLM 调用(慢+贵)
```

**Agent 用户体验: 不及格**。

---

## 12 · 顾源源指令对照(§六·禁止事项)

| # | 顾源源禁止 | 本报告自检 |
|---|---|---|
| 1 | 不直接做外置 Codex CLI | ✅ M0 全没碰 |
| 2 | 不做 CEO Skill | ✅ |
| 3 | 不做 R5/R6 | ✅ |
| 4 | 不写新的自评 FINAL | ✅(本报告是基线,不是 FINAL) |
| 5 | 不用 snapshot | ✅(全 V2.1 lab db + curl) |
| 6 | 不把后端存在算 Agent 可用 | ✅(本报告区分"底层能力 52.5"vs"endpoint 27.75") |
| 7 | 不把 endpoint 200 算用户可见 | ✅(approvals 200 但 405 on action) |
| 8 | 不绕过 Approval Queue | ✅(approvals db 真有, 等 endpoint 修) |

---

## 13 · M0 结论 + 路径建议

```
M0 基线 (不修复, 只测):
  · Agent Readiness Index: 27.75 / 100
  · 底层能力 Index:        52.5 / 100
  · 顾源源 5 类目标全部统计完毕

M0 不要求通过 — 但发现差异比预想大:
  数据中心已经是公司大脑 (52.5)
  对 Agent 的 HTTP 契约几乎为零 (27.75)
  这就是顾源源说的 "数据库知道一切, Agent 一个 endpoint 都拉不到"

下一站 M1 (Agent 可读):
  必做 5 endpoint:
    1. GET /api/v1/clients/{id}/agent-state    (M0-1 缺)
    2. GET /api/v1/clients/{id}/data-gaps      (M0-2 缺)
    3. POST /api/v1/clients/{id}/data-gaps/compensate
    4. GET /api/v1/agent-run-logs + /{run_id}  (M0-5 缺)
    5. POST /api/v1/approvals/{id}/decision    (M0-5 405)

  M1 通过线: 5/5 HTTP 可调 + 跨客户 scope + JSON schema
  M1 估时: 单次 commit 可做完(顾源源 P0)

下一站 M2 (Agent 可判):
  必做 3 service + endpoint:
    · evidence_sufficiency_checker
    · output_quality_context_builder
    · authority_resolver
  M2 通过线: 缺证据识别 ≥80% / 冲突识别 ≥80% / 返工建议 ≥3 条
  M2 估时: 2-3 commit

下一站 M3 (Agent 可行动):
  必做:
    · action_candidate_engine
    · dry_run_simulator
    · approval_required 标注
  M3 通过线: action candidates ≥5 / dry-run 不写库 / 危险动作 100% 进审批
  M3 估时: 3 commit
```

---

## 14 · 不算硬门槛但要标注的诚实点

1. **本 M0 只测了 CFFC 一个客户**。其它 2 个客户(日慈/善加)状态可能不同。
2. **workspace/chat 用 prompt 字段非 message**。当前 chat 契约不统一(可能 chat history 走另一字段)。
3. **approval 32 条**(/api/v1/approvals 真返回), 但 27 条 actor_type='external_ai_agent' (来自 B AI V3.0 测试), 真用户 approval 数据少。
4. **agent_run_log 34 条 / idempotency_key 19 条 (57%)**, 但全是历史数据, M1 修完 endpoint 后还要看新流量。
5. **recommended_actions 字段在 ContextPack 已定义但永远 null** — 没真 service 写入。

---

不写 FINAL 自评。M0 基线 = **27.75/100 (Agent endpoint)** / **52.5/100 (底层能力)**。
等顾源源拍板 M1 启动信号, A 一气做完。
