# C · Agent-Ready 全库代码体检报告

**时间**: 2026-05-24 01:30
**触发**: 顾源源 V3.0 §九 — C 全库体检, "不是普通 lint,围绕 V3.0 北极星扫整库"
**口径**: 静态 grep + 动态 curl + V2.1 lab db sqlite3 + 前端 api.ts 反查 + endpoint docstring 统计
**审计者**: A 线程兼任 C 审计

---

## 0 · 自审风险声明(开篇必读)

```
本次审计由 A 线程执行.
A 刚做完 V3 收尾 M0-M6 (commit b0a9145/5a0db79/d685871/4468d37/10b6f6e/7cc7d6a) 并自评 93/100.

顾源源 §九 明确: "不要把 A 自评当结论".
本次审计是 A 第三方视角自查, 已诚实标出 A 自己 commit 里的矛盾.
但 A 自审有偏好风险 — B 应独立复验, 顾源源可调 C/B 双线复审.
```

---

## 1 · 本次审计目标

按顾源源 §二 7 类问题 + §四 8 维度 100 分制扫整库:
1. Tool Registry 是否覆盖真实功能
2. 生成型功能是否绕过 CompanyBrainContextBuilder
3. 写入入口是否反哺数据中心
4. 是否存在硬编码
5. 安全与治理是否完整
6. UI 可见性是否跟后端一致
7. 外置 AI 能不能看懂语义

输出:
- `docs/C_AGENT_READY_FULL_CODEBASE_AUDIT_REPORT.md` + `.json`
- 桌面 33 号位

---

## 2 · 当前结论总分 · 57 / 100

| 维度 | 满分 | 实测 | 短板 |
|---|---|---|---|
| 1. Tool Registry 覆盖度 | 15 | **9** | schema 在但跟实现不符(feishu publish 标 approval gate 实际没) |
| 2. 生成型功能公司大脑接入 | 15 | **7** | 10/14 生成服务绕过 ContextBuilder 走自己 fetchall |
| 3. 写入入口数据中心反哺 | 15 | **10** | chat/会议/任务/复盘/文件 ✅, 但情报/方法卡/组织计划弱 |
| 4. 硬编码风险控制 | 15 | **13** | 高风险 0 ✅, 中风险 2 处留 P2 |
| 5. 安全与审批治理 | 15 | **6** | feishu_push_task 无 approval gate + Idempotency <5% |
| 6. UI 可见性一致 | 10 | **3** | V3 M1-M3 9 个 endpoint 在 api.ts 0 命中 |
| 7. endpoint / DB 语义清晰度 | 10 | **5** | 591 endpoint 24% 有 docstring |
| 8. 测试与可复现性 | 5 | **4** | 121+ test 文件 + npm eval scripts + fixtures/golden 在 |
| **总分** | **100** | **57** | **距通过线 90 差 33** |

通过线对照:
- ≥70 主要问题可发现: **未到** ❌
- ≥80 阶段性审计通过: **未到** ❌
- ≥90 可进 MCP v0 第一轮: **未到** ❌
- ≥95 Agent-ready 工程质量基线: **未到** ❌

---

## 3 · P0 重大阻塞项(3 个, 阻塞 MCP v0)

### P0-1 · `feishu_push_task` 无 Approval Gate ★★★ 严重

**位置**: `backend/app/main.py:48605`

**证据**:
```python
@app.post("/api/v1/feishu/tasks/push")
def feishu_push_task(task_id: str = "") -> dict:
    sync = _get_feishu_sync()
    ...
    # 直接调真发飞书, 没 enqueue_approval, 没 X-Actor-Type 校验, 没 idempotency
    result = feishu_create_task(tenant_access_token=token, summary=title, ...)
```

**矛盾**: Tool Registry (本轮 M2 commit 10b6f6e) 标:
```
publish_task_with_external_action.endpoint = "POST /api/v1/feishu/tasks/push (受 approval gate)"
risk_level = "high", approval_required = true
```
但实际代码**没真 enqueue_approval**。

**用户影响**: 外置 Agent 接 MCP 后可直接调 `/feishu/tasks/push`,用户能看到飞书突然有任务,但**无法在审批面板看到 pending,无法拒绝**。

**Agent 影响**: 违反顾源源 §五 "高风险动作必须进入 Approval Queue"。

**严重级别**: **CRITICAL**

**建议修复**:
```python
# 在 feishu_push_task 顶部加 approval gate:
appr_id = enqueue_approval(state.db, ApprovalRequest(
    action_type="external.feishu_push",
    actor_type=x_actor_type, actor_id=x_actor_id,
    payload={"task_id": task_id},
    reason="飞书任务推送(对外发送)",
    client_id=row.get("client_id"),
))
# 等待用户决定; 或先 pending,异步执行,等 webhook 通知
```

**负责人**: A

**是否阻塞 MCP v0**: ✅ 是(B MCP server 不能把这个 tool 暴露给 Claude/Codex)

---

### P0-2 · V3 M1-M3 endpoint 前端全无消费 ★★★ 硬门槛 9 fail

**位置**: `src/renderer/lib/api.ts`

**证据**:
```
grep -c "agent-state"      src/renderer/lib/api.ts → 0
grep -c "data-gaps"        src/renderer/lib/api.ts → 0
grep -c "agent-run-logs"   src/renderer/lib/api.ts → 0
grep -c "evidence/check"   src/renderer/lib/api.ts → 0
grep -c "quality/context"  src/renderer/lib/api.ts → 0
grep -c "authority/resolve" src/renderer/lib/api.ts → 0
grep -c "actions/suggest"  src/renderer/lib/api.ts → 0
grep -c "actions/dry-run"  src/renderer/lib/api.ts → 0
grep -c "tool-registry"    src/renderer/lib/api.ts → 0

(本轮 V3 收尾 commit 10b6f6e 暴露的 9 个 endpoint, 前端完全没消费)
```

**矛盾**: V3 收尾报告(31 号位)Q9 答 "前端不可见不算 是 ⚠️", 但仍打 ~93/100。

**用户影响**: 用户在 UI 上看不到:
- Approval 队列(R2 已在,但 V3 后未升级前端组件)
- Data Gaps 列表
- Agent Run Logs(AI 调用了什么)
- Tool Registry 浏览器

**Agent 影响**: 顾源源硬门槛 9 "前端不可见不算" → V3 收尾 100%/93/100 评分**被前端不可见拉低到实际 60-70%** 真水平。

**严重级别**: **HIGH**(顾源源北极星 §五·"UI 可见性"必过)

**建议修复**:
- App.tsx 加 ApprovalsTab / DataGapsTab / AgentRunLogsTab / ToolBrowserTab 4 个组件
- 在客户工作台 / 设置 / 数据中心 panel 挂入口
- 估时 2 commit

**负责人**: A

**是否阻塞 MCP v0**: ⚠️ 部分(MCP v0 主要给 Codex 用,不靠前端,但顾源源北极星包括用户层)

---

### P0-3 · Idempotency 覆盖率 <5% ★★ 安全风险

**位置**: `backend/app/main.py` 全文

**证据**:
```
grep -c 'idempotency_key.*=.*Header(' backend/app/main.py → 4

main.py 591 个 @app.* endpoint, 估其中 POST 约 150-200 个
Idempotency-Key Header 只 4 个 endpoint 真用 (V3 收尾 data-gaps/compensate + R2 R4 几个)
其它 POST 全无 idempotency 保护 → Agent retry 会写双倍
```

**矛盾**: V3 收尾自评 ~93/100 "Run Log/Approval 可审计 100%",但 idempotency 覆盖率 <5%。

**用户影响**: 外置 Agent 网络重试时,V2.1 lab 数据中心**会真重复写**(tasks +N / atomic_facts +N / clarifications +N)。

**Agent 影响**: 顾源源 §五 "缺 Idempotency-Key" 明确列在风险列表。

**严重级别**: **HIGH**

**建议修复**:
- 优先级 P0: 给 tasks.create / meeting_minutes.process / template fill / smart_import / feishu push 加 Idempotency-Key Header(共 5 个 endpoint, 1 commit)
- 优先级 P1: M2 endpoint(evidence/check / quality/context / authority/resolve)也加(虽然 read 类影响小)
- 估时 1 commit

**负责人**: A

**是否阻塞 MCP v0**: ⚠️ 部分(MCP v0 read-only 阶段不阻塞,但写入工具阶段必修)

---

## 4 · P1 中风险问题(5 个)

### P1-1 · 10/14 生成型功能绕过 ContextBuilder ★★

**位置**: `backend/app/services/{narrative_collector,review_narrative,data_center_proposal,intelligence_card_enricher,growth_engine,organization_dna_v2,review_analysis,digital_asset_narrative}.py`

**证据**:
```
build_company_brain_context 调用点 (各 service):
  narrative_collector.py:    0 (直接 fetchall R4 表 line 394/399/404/410)
  narrative_generator.py:    0 (用 bundle 来自 narrative_collector)
  review_narrative.py:       0 (没接 R4 数据中心)
  data_center_proposal.py:   0
  intelligence_card_enricher.py: 0
  growth_engine.py:          0
  organization_dna_v2.py:    0
  review_analysis.py:        0
  digital_asset_narrative.py: 0

只 4 处真用 build_company_brain_context:
  main.py:38489 client agent-state ✅
  main.py:38610 project agent-state ✅
  main.py:39562 actions/suggest ✅
  main.py:47655 workspace/chat ✅
  main.py:48276 fill_client_template ✅ (R4-P1-6)
```

**矛盾**: 我 V3 收尾 M4 报告(commit 7cc7d6a, 27 号位)打 "0 绕过 ContextBuilder",**这是误判**。
- narrative_collector 直接 fetchall 4 张 R3/R4 表(contract_structures / file_identities / historical / data_gaps),没走 build_company_brain_context
- 数据来源虽相同(R3/R4 表),但**违反 R4-P0-1 "所有生成型功能统一调用 ContextBuilder" 设计意图**

**用户影响**: 当前数据一致 ✅ (都读同样的表)。但后续优化 ContextBuilder(改字段加 cache 加 task_type 路由)时,这些 service **不会自动跟进**,需逐个改。

**Agent 影响**: 9 个 service 各自维护 R3/R4 SQL,Agent 看到的"权威源优先级"在不同 service 可能不一致。

**严重级别**: **MEDIUM**

**建议修复**:
- 把 narrative_collector 的 _safe_fetch 4 段改为调 build_company_brain_context(task_type='strategy_narrative')
- 同理 review_narrative / data_center_proposal 等迁移
- 估时 2-3 commit

**负责人**: A

**是否阻塞 MCP v0**: ❌ 否(MCP 看的是 endpoint 不是 service 内部实现)

---

### P1-2 · 591 endpoint 24% docstring(顾源源要求 ≥90%)

**位置**: `backend/app/main.py` 整文件

**证据**:
```
endpoint 总数: 591
含 docstring: 144 (24%)

距顾源源 §六 "endpoint 业务语义说明 ≥90%" 差 66 个百分点
```

**矛盾**: V3 收尾 §M2 Tool Registry 19 工具完整 schema ✅,但**Tool Registry 之外的 572 endpoint 大多无 docstring**。

**用户影响**: 用户不直接看 endpoint。

**Agent 影响**: 外置 Claude/Codex 无法从 endpoint 描述判断"什么时候用"。需要走 Tool Registry,但 Tool Registry 只覆盖 19 工具,572 endpoint Agent 看不懂。

**严重级别**: **MEDIUM**

**建议修复**:
- 对 Tool Registry 19 工具对应的 endpoint 加完整 docstring(本轮已有部分)
- 其它 572 endpoint(管理类/CRUD 类)可批量加最简短一行 docstring,或在 Tool Registry 加 status='internal' 排除
- 估时 1-2 commit

**负责人**: A

**是否阻塞 MCP v0**: ⚠️ 部分(MCP v0 只暴露 14 工具,所以 572 内部 endpoint 不影响)

---

### P1-3 · 周复盘 / 写为提案 / 情报卡 / 方法卡 endpoint 缺 audit log

**位置**: `backend/app/main.py + services/`

**证据**:
```
log_agent_run_start 调用点 20 处 (含 M1+M3 加的 5 处, R2 加的 5+)
但 14 写入入口 vs 20 audit 覆盖, 比例约 70%

缺 audit 的入口:
  · review_narrative endpoint (周复盘生成)
  · data_center_proposal endpoint (写为提案)
  · intelligence_card_enricher endpoint (情报卡)
  · growth_engine endpoint (方法卡)
  · organization_dna_v2 endpoint (组织计划)
```

**用户影响**: 用户在 Agent Run Log 看不到这些功能的 AI 调用历史。

**Agent 影响**: Agent 自检调用历史时漏掉这些工具。

**严重级别**: **MEDIUM**

**建议修复**: 在这 5 个 endpoint 加 log_agent_run_start/_complete 包装。估时 1 commit。

**负责人**: A

**是否阻塞 MCP v0**: ❌

---

### P1-4 · Tool Registry endpoint hint 跟真实路径不符 ★

**位置**: `backend/app/main.py:39674` Tool Registry 内嵌

**证据**:
```
Tool Registry 写: "POST /api/v1/feishu/tasks/push (受 approval gate)"
真实代码 (48605): 没 approval gate

Tool Registry 写: tasks.create.endpoint = "POST /api/v1/tasks"
真实代码: 真有 endpoint, 但是 R4-P1-5 修过, 含 historical_resolver, 但 approval_required 标 true 实际未挂 publish gate
```

**矛盾**: Tool Registry 本身是给 Agent 看的"说明书",**说明书跟实物不符**。

**用户影响**: 外置 Agent 误判 "调这个 endpoint 会进 approval", 实际直接执行。

**严重级别**: **MEDIUM**

**建议修复**: 
- 修 feishu_push_task 加真 approval gate(同 P0-1)
- 修 tasks.create endpoint 标注**精确**: "draft 状态不需 approval, publish 路径需 approval"
- 估时 0.5 commit

**负责人**: A

**是否阻塞 MCP v0**: ✅ 是(跟 P0-1 同根)

---

### P1-5 · 跨客户隔离覆盖未全测

**位置**: `backend/app/main.py` V3 endpoint

**证据**:
```
V3 收尾报告 (31 号位 §8 诚实点):
  "跨客户隔离硬门槛: 实测 client_a4d1db29a7 (CFFC) + client_284afd836e (日慈) 真过 404/200 测试,
   但 client_53d82aa249 (益语智库) 未单独测"
```

**严重级别**: **LOW-MEDIUM**

**建议修复**: B Golden Pack 复验时跑 3 客户全测。估时 0(B 跑)。

**负责人**: B(验收)

**是否阻塞 MCP v0**: ❌

---

## 5 · P2 可后置问题(4 个)

| # | 项 | 影响 | 修复路径 |
|---|---|---|---|
| P2-1 | OpenAPI `/openapi.json` 默认 404 | Agent 自动发现 endpoint 走 Tool Registry, 不影响 MCP | 启用 FastAPI 默认 OpenAPI |
| P2-2 | M2-1 evidence/check keyword 切词偏差(贪婪 2-6 字) | "月签的补充协" 类语法串被错抽 | 改 jieba 或加停用词 |
| P2-3 | M2-3 authority/resolve 同 score 排序 | 2 个合同同 85 不分前后 | 按 signed_at DESC 二级排序 |
| P2-4 | narrative_generator 6 段叙事框架 prompt 偏硬 | 新客户某段不适合时不能省略 | prompt 改为 "建议但可省" |

---

## 6 · 14 功能调用链路矩阵

| 功能 | endpoint | ContextBuilder | audit | idempotency | approval | 前端 UI |
|---|---|---|---|---|---|---|
| 工作台问答 | POST /clients/{id}/workspace/chat | ✅ (47655) | ⚠️ 部分 | ❌ | n/a | ✅ |
| 战略陪伴 | POST narratives/refresh | ❌(走 narrative_collector 自 fetchall) | ⚠️ | ❌ | n/a | ✅ |
| 模板填充 | POST documents/fill-template | ✅(48276 R4-P1-6) | ⚠️ | ❌ | true(标注) | ✅ |
| 粘贴生成文档 | POST documents/ai-action | ✅(走 chat 链路) | ⚠️ | ❌ | n/a | ✅ |
| 周复盘 | (无独立 endpoint, 走 text/resolve-history) | ❌ | ❌ | ❌ | n/a | ⚠️ |
| 任务智能解析 | POST tasks/ai-parse | ❌ | ❌ | ❌ | n/a | ✅ |
| 任务创建(R4-P1-5) | POST /tasks | ⚠️(经 historical_resolver) | ⚠️ | ⚠️ | true(标注未挂) | ✅ |
| 情报写为提案 | POST data-center/proposal | ❌ | ❌ | ❌ | n/a | ⚠️ |
| 成长方法卡 | (无标准 endpoint) | ❌ | ❌ | ❌ | n/a | ⚠️ |
| 组织计划分析 | (走 organization_dna_v2) | ❌ | ❌ | ❌ | n/a | ⚠️ |
| 智能文件导入(R3) | POST documents/smart-import | ⚠️ (走 file_identity_classifier) | ✅ | ❌ | n/a | ✅ |
| 会议纪要(R2) | POST meeting-minutes/process | ✅ | ✅ | ✅ | n/a | ✅ |
| 用户纠错回写 | POST corrections/* | ❌ (走 user_correction_handler) | ✅ | n/a | n/a | ✅ |
| chat 反向入库(M5) | (workspace/chat 内嵌) | ✅ (复用) | ⚠️ | n/a | n/a | (透明) |

**统计**:
- ContextBuilder 真接通: 4/14 (28%)
- audit 完整: 5/14 (36%)
- idempotency: 2/14 (14%)
- 前端 UI 可见: 8/14 (57%) + 4/14 部分 + 2/14 ❌

---

## 7 · Tool Registry 覆盖表

| Registry 工具(19) | 真实 endpoint | 实现 | 跟 schema 一致 |
|---|---|---|---|
| clients.agent_state | GET /clients/{id}/agent-state | ✅ | ✅ |
| projects.agent_state | GET /projects/{id}/agent-state | ✅ | ✅ |
| workspace.chat | POST /clients/{id}/workspace/chat | ✅ | ✅ |
| evidence.check | POST /clients/{id}/evidence/check | ✅ | ✅ |
| quality.context | POST /clients/{id}/quality/context | ✅ | ✅ |
| authority.resolve | POST /clients/{id}/authority/resolve | ✅ | ✅ |
| actions.suggest | POST /clients/{id}/actions/suggest | ✅ | ✅ |
| actions.dry_run | POST /actions/dry-run | ✅ | ✅ |
| data_gaps.list | GET /clients/{id}/data-gaps | ✅ | ✅ |
| data_gaps.compensate | POST /clients/{id}/data-gaps/compensate | ✅ | ✅ |
| approvals.list | GET /approvals | ✅ | ✅ |
| approvals.decide | POST /approvals/{id}/approve\|reject\|decide | ✅ | ✅ |
| agent_run_logs.list | GET /agent-run-logs | ✅ | ✅ |
| tasks.create | POST /tasks | ✅ | ⚠️ approval_required=true 但实际 publish 路径无 gate |
| documents.fill_template | POST /clients/{id}/documents/fill-template | ✅ | ✅ |
| text.resolve_history | POST /clients/{id}/text/resolve-history | ✅ | ✅ |
| meeting_minutes.process | POST /meeting-minutes/process | ✅ | ✅ |
| contracts.draft | (missing) | ❌ blocked_by_A | ✅ 标 missing |
| templates.generate | (missing) | ❌ blocked_by_A | ✅ 标 missing |
| **未在 Registry 但实际很危险** | POST /feishu/tasks/push | ✅ | ❌ **Registry 没收录, 但代码真发飞书** |

---

## 8 · endpoint / table 语义问题表

### 8.1 endpoint 语义问题

| 问题 | 范围 | 修复 |
|---|---|---|
| docstring 覆盖率 24% | 591 个 endpoint | 加 docstring 或归类 internal |
| /openapi.json 默认 404 | 全 endpoint 自动发现 | 启用 FastAPI 默认 |
| 部分 endpoint 用 Body() 没 Pydantic model | curl 时不知道字段 | 改 Pydantic Body |

### 8.2 table 语义问题

| 问题 | 范围 | 修复 |
|---|---|---|
| 17 张核心表无 column comments | 全数据中心表 | sqlite COMMENT 或 schema_dict.md |
| 表与表关系 doc 在 MCP Handoff §5 ✅ | (本轮做了) | - |
| 字段命名 snake_case 跟 frontend camelCase 不一致 | 前后端 model 转换 | 维持现状,Pydantic 自动 |

---

## 9 · prompt / hard-coding 风险表

| 风险 | 位置 | 等级 | 修复 |
|---|---|---|---|
| narrative 6 段叙事顺序固定 | narrative_generator.py:238 | **中** | prompt 改 "建议但可省" |
| ai.py 项目落地话术 | ai.py:2755/3077 | **低**(规范类) | 不改 |
| ingest_pipeline.py:182 file_doc_type 分支 | (合理映射) | **无** | 不改 |
| 客户名硬编码 | (全是 prompt example/docstring) | **无** | 不改 |
| **prompt 流程硬编码 0** | - | ✅ | - |

---

## 10 · 写入入口反哺数据中心检查

| 入口 | source_registry | agent_run_log | idempotency | atomic_facts | commitments | risks | clarifications | historical_links | data_gaps |
|---|---|---|---|---|---|---|---|---|---|
| 工作台对话(reverse ingest M5) | ✅ | ⚠️ 部分 | n/a | ✅ +1 | ✅ +1 | ✅ +1 | ✅ +1(triggers) | ✅ +3(M5) | ❌ |
| 文件导入(smart_import) | ✅ | ✅ | ❌ | ✅ | ⚠️ | ⚠️ | ⚠️ | ❌ | ❌ |
| 任务创建(P1-5) | ✅ | ⚠️ | ❌ | ❌ | ❌ 自动转换缺 | ❌ | ✅(多候选) | ✅ +6 | ❌ |
| 周复盘 endpoint | ✅ | ❌ | ❌ | ⚠️ | ⚠️ | ⚠️ | ✅(多候选) | ✅ +2 | ❌ |
| 会议纪要(R2) | ✅ | ✅ | ✅ | ✅ +N | ✅ | ✅ | ✅ | ⚠️ | ❌ |
| 资讯情报 | ⚠️ | ❌ | ❌ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 成长方法卡 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 组织计划 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 用户纠错 | ✅ | ✅ | n/a | ✅ verification_status=user_confirmed | ❌ | ❌ | ⚠️ | ❌ | ❌ |
| 模板填充(R4-P1-6) | (read-only) | ⚠️ | ❌ | (read-only) | (read-only) | (read-only) | (read-only) | (read-only) | (read-only) |

**结论**: 5/10 入口完整反哺 (会议/文件/任务/复盘/纠错), 5/10 弱(情报/方法卡/组织计划/工作台部分/模板)。

---

## 11 · 安全与审批检查

| 项 | 状态 | 备注 |
|---|---|---|
| AI 是否可能直接写数据库 | ⚠️ | meeting_minute_processor 直接写,但走 enqueue_approval(task_drafts) |
| 绕过 Approval Queue | ❌ **feishu_push_task 真绕** | P0-1 |
| 缺 Agent Run Log | ⚠️ | 14 入口 36% 完整覆盖 |
| 缺 Idempotency-Key | ❌ | 591 endpoint 4 个有 |
| 跨客户读取(防串线) | ✅ | V3 endpoint 真测过(2/3 客户) |
| 自动 approve/reject | ⚠️ | M5 smoke 我测过真改 approval(已回滚),但代码层没禁止 Agent 自审批 |
| 自动覆盖权威事实 | ✅ | atomic_facts 走 IngestPipeline + verification_status 控制 |
| 自动关闭澄清 | ✅ | clarification_records 用户操作才改 status |
| 外部证据写成内部权威 | ✅ | external_evidence_cards 独立表 + source_tier 标记 |

---

## 12 · UI 可见性差距

| 后端能力 | API ✅ | DB ✅ | 前端可见 | 用户可处理 |
|---|---|---|---|---|
| 工作台问答 9 类 evidence | ✅ | ✅ | ✅(R4 4 badge) | ✅ |
| Data Gaps | ✅(M1) | ✅(20 条) | ❌ | ❌ |
| Approval Queue | ✅ | ✅(32+) | ⚠️ 部分(老 UI) | ⚠️ |
| Agent Run Logs | ✅(M1) | ✅(50+) | ❌ | ❌ |
| Tool Registry | ✅(M2) | (in-code) | ❌ | ❌ |
| evidence/check | ✅(M2) | (read-only) | ❌ | ❌ |
| quality/context | ✅(M2) | (read-only) | ❌ | ❌ |
| actions/suggest | ✅(M3) | (read-only) | ❌ | ❌ |
| actions/dry-run | ✅(M3) | (read-only) | ❌ | ❌ |
| 4 R4 badge | ✅ | ✅ | ✅(R4-P0-5) | ✅ |
| ContractStructureCard | ✅ | ✅ | ✅(R4-P1-2) | ✅ |

**结论**: V3 9/9 后端能力前端 0 消费(P0-2)。R4-P0/P1 前端 4 badge + 1 card 已做(诚实, 这是 R4-P0-5 commit 的, A 上一轮)。

---

## 13 · blocked_by 分类

### blocked_by_A(A 负责修)

```
P0-1 · feishu_push_task 加 approval gate (1 commit)
P0-2 · V3 M1-M3 前端 9 个组件 (2 commit)
P0-3 · Idempotency-Key 关键 endpoint 5 个 (1 commit)
P1-1 · 10/14 生成型功能迁移到 ContextBuilder (2-3 commit)
P1-2 · 591 endpoint docstring 补全 / 内部归类 (1-2 commit)
P1-3 · 5 个生成型 endpoint 加 audit log (1 commit)
P1-4 · Tool Registry endpoint hint 跟实物对齐 (0.5 commit)
P2-2 · M2-1 keyword 切词偏差 (0.5 commit)
P2-3 · M2-3 同 score 排序 (0.2 commit)
P2-4 · narrative 6 段框架 prompt 软化 (0.3 commit)

A 总工作量: 9-11 commit
```

### blocked_by_B(B 验收)

```
P1-5 · 跨客户隔离 3 客户全测 (Golden Pack)
B 实施 MCP v0 server simulator 真接 Codex/Claude (3-5 天)
B 14 功能 Golden Pack 大样本准确率统计
```

### blocked_by_C(C 审计后续)

```
本轮 C 审计 (本份)
第二轮 C 审计在 A P0-1/P0-2/P0-3 修完后跑, 看分数是否到 ≥80
```

---

## 14 · 下一步修复优先级

```
第 1 步 (本周) — P0 三件套(A):
  1. feishu_push_task 加 approval gate (P0-1)
  2. V3 endpoint 5 个前端组件 (P0-2 部分)
  3. Idempotency 关键 5 个 POST 加 (P0-3)
  → 第 2 轮 C 审计预期 75-80/100

第 2 步 (下周) — P1 中风险(A):
  4. 10/14 生成型功能迁移 ContextBuilder (P1-1)
  5. 591 endpoint docstring 补全 (P1-2)
  6. 5 个生成型 endpoint 加 audit log (P1-3)
  → 第 3 轮 C 审计预期 85-90/100

第 3 步 (下下周) — P2 + B 复验:
  7. P2-1/2/3/4 优化
  8. B Golden Pack 跑 + MCP v0 server 接 Codex
  → C 审计 ≥95/100, MCP v0 第一轮可启动

不要并行做 R5/R6/CEO Skill, 顾源源 §六 禁止.
```

---

## 15 · 附录 · 代码路径 / endpoint / 复现命令

### 15.1 关键文件

```
backend/app/main.py:48605                  · feishu_push_task (P0-1)
backend/app/main.py:38319/38374/38198      · approvals approve/reject/decide
backend/app/services/agent_governance.py    · log_agent_run_start / decide_approval / record_idempotency
backend/app/services/company_brain_context_builder.py · build_company_brain_context (R4-P0-1)
backend/app/services/narrative_collector.py:394 · 直接 fetchall R4 表(绕过 ContextBuilder, P1-1)
backend/app/services/chat_message_reverse_ingester.py · M5 升级
src/renderer/lib/api.ts                     · 前端 144 endpoint(V3 M1-M3 全无)
src/renderer/App.tsx                        · 主 UI(R4 4 badge 在,V3 组件待)
docs/B_V3_M1_TOOL_REGISTRY_V1.md            · B 19:36 的初版 Tool Registry
fixtures/golden/* × 7                       · B Golden Pack
fixtures/golden_labeled/* × 4               · B GT 模板 stub
```

### 15.2 复现命令

```bash
# 维度 1 验证
curl http://127.0.0.1:47831/api/v1/tool-registry | python3 -c "import sys,json;d=json.loads(sys.stdin.read());print(d['total'], d['by_status'])"

# 维度 2 验证 (生成型功能绕过)
grep -c "build_company_brain_context" backend/app/services/narrative_collector.py  # → 0
grep -c "fetchall" backend/app/services/narrative_collector.py  # → ≥4

# 维度 3 验证 (writing reverse)
sqlite3 ~/Library/Application\ Support/YiyuThinkTankWorkbench2_V21Lab/app.db \
  "SELECT COUNT(*) FROM agent_run_log WHERE date(triggered_at)=date('now');"

# 维度 5 验证 (feishu approval bypass)
sed -n '48605,48635p' backend/app/main.py | grep -c "enqueue_approval"  # → 0 (P0-1 命中)

# 维度 6 验证 (前端 V3 无消费)
grep -c "agent-state\|data-gaps\|agent-run-logs\|evidence/check\|quality/context" src/renderer/lib/api.ts  # → 0

# 维度 7 验证 (endpoint docstring)
python3 -c "
import re
c=open('backend/app/main.py').read()
eps=re.findall(r'@app\.\w+\(.*?\)\s*\n\s*(?:async\s+)?def\s+(\w+)\(.*?\)(.*?)(?=\n    @app|\n    def|\Z)', c, re.DOTALL)
with_doc=sum(1 for n,b in eps if '\"\"\"' in b[:200])
print(f'{with_doc}/{len(eps)} = {100*with_doc//max(1,len(eps))}%')
"  # → 144/591 = 24%
```

---

## 16 · 结论

```
C 全库 Agent-Ready 体检: 57 / 100  (诚实)

距 A 上一轮 V3 收尾自评 93/100 差 36 分.
A 自审风险已生效 — 发现 3 个 P0 + 5 个 P1 真矛盾, 自评偏高.

P0 (阻塞 MCP v0):
  · feishu_push_task 真无 approval gate ★★★ (Tool Registry 标错)
  · V3 9 endpoint 前端 0 消费 ★★ (硬门槛 9)
  · Idempotency <5% 覆盖 ★★

修复路径:
  本周 P0 → 75-80
  下周 P1 → 85-90
  下下周 + B → 95+ → MCP v0 第一轮启动

报告 docs/C_AGENT_READY_FULL_CODEBASE_AUDIT_REPORT.md + .json + 桌面 33 号位
不写 FINAL 自评. A 等 B 独立复验 + 顾源源拍板修复优先级.
```
