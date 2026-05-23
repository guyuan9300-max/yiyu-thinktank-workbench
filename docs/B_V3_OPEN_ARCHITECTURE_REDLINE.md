# V3.0 开放架构红线 (顾源源 5/23 钦定)

> **触发**: 顾源源 5/23 21:30 强烈拍板: "不为某个场景写死流程, 测试可以具体, 架构必须开放"
> **冻结**: 2026-05-23 V1 (不允许向下兼容, 后续修改改名 V2)
> **作用**: V3.0 架构红线第 0 条. 一切 V3.0 工程必须遵守.
> **关联**: 应该插进 `docs/V3_0_GOAL_DRIVEN_AI_COMPANY_OS.md` 顶部.

---

## 红线 0 条 (顾源源原话 + 升级版)

> **不为任何单一场景、单一客户、单一行业写死执行流程.**
> **不在代码或 system prompt 中硬编码 "X 输入必须先调 Y 再调 Z" 的固定路径.**
> **不把 Golden Test 样本变成业务流程模板.**
> **测试可以具体, 架构必须开放.**

---

## 5 条具体规则

### 规则 1 · 业务流程不写死

**禁止**:
```python
# ❌ 反例: 在 service 里写死
if input_type == "meeting_minutes":
    call_contract_draft()
    call_task_create()
    call_brand_proposition()
```

**允许**:
```python
# ✅ 正例: 工具自主选择
ai_planner.generate_plan(
    goal=user_input,
    tools=tool_registry.list_available(),
    state=agent_state.get(client_id),
    gaps=data_gap_api.list(client_id),
)
```

### 规则 2 · system prompt 不写流程

**禁止**:
```text
# ❌ system prompt 反例:
"第一步必须查合同, 第二步必须查任务, 第三步必须查情报."
"如果是会议纪要, 一定要生成合同草稿."
"对日慈用心理教育逻辑, 对 CFFC 用乡村教育逻辑."
```

**允许**:
```text
# ✅ system prompt 正例:
"你可以使用以下工具 (见 tool registry).
 请根据用户目标、数据缺口和证据情况选择最合适的工具组合.
 若证据不足, 先生成澄清或补证任务, 不得编造.
 危险动作必须进 Approval Queue."
```

可以举例, **但要标 "参考范例, 不是流程模板"**, 不能让 LLM 把例子当 fixed pipeline.

### 规则 3 · 客户逻辑不写死

**禁止**:
```python
# ❌
if client.name == "日慈基金会":
    use_psychology_template()
elif client.name == "CFFC":
    use_rural_education_template()
```

**允许**: 客户逻辑来自数据中心 (atomic_facts + file_identities + historical_links + ...), AI 自己从数据推断, 不在代码里写死.

### 规则 4 · 成果类型不写死

```
用户给一段话, 不一定都要生成合同 / 方案 / 任务.
AI 应该先判断这段话到底需要:
  - 做材料?
  - 生成任务?
  - 找风险?
  - 补证据?
  - 更新故事卡?
  - 做复盘?
  - 请求用户确认?
```

每次输入触发什么成果, **由 AI 看 agent_state + data_gap + tool_registry 自己定**, 不是 if input_type == X then output_type Y.

### 规则 5 · Golden Test 样本 ≠ 流程模板

```
明远会议纪要 = Golden Test 样本 (验证 AI 能否跨工具调度)
明远会议纪要 ≠ 业务流程模板 (不是"以后所有会议纪要都按这流程")

Golden Pack 跨领域必须 ≥ 10 类:
  公益基金会 / 商业咨询 / 应急救援 / 学术调研 /
  青少年行动 / 个人成长 / 中小企业 / 社区行动 /
  教育产品 / 跨领域混合
```

不到 10 类**不算证明架构开放**, 只算验证一个领域.

---

## 6 件必须"硬"下来 (不是什么都开放)

```
开放: 业务流程 / prompt / 客户逻辑 / 成果类型
硬化: 协议 + 安全边界
```

| 必须硬化 | 含义 |
|---|---|
| **数据结构** | 每条数据有 type/client_id/project_id/source/confidence/scope, schema 不漂移 |
| **Tool Registry** | 每个工具有 input_schema/output_schema/when_to_use/risk_level/approval_required, machine-readable |
| **Agent State API** | 一次 GET 拿到客户完整状态, schema 稳定 |
| **Data Gap API** | 主动暴露"缺什么证据", schema 稳定 |
| **Approval Queue** | 写权限分级审批, AI 不能绕过 |
| **Agent Run Log** | 所有 AI 动作可审计, schema 稳定 + 必填字段 |

→ **流程开放, 协议稳定. 判断交给模型, 边界交给系统.**

---

## 写进 prompt 的 3 类内容 (允许)

```
1. 工具说明 (Tool Registry 自动注入)
   "你有这些工具: { tool_name: ..., when_to_use: ..., approval_required: ... }"

2. 边界约束
   "证据不足不得编造. 危险动作必须进 Approval. 不跨客户读取."

3. 判断原则
   "根据目标 / 数据缺口 / 证据等级 / 用户要求选择工具.
    若多候选歧义, 先生成澄清."
```

→ 不允许写第 4 类: "X 输入 → Y 步骤" 的固定流程.

---

## B 自动验收官扫描规则

B 每次评估 A 的 commit, 自动扫:

```python
hardcoding_smell_checks = [
    "system prompt 里出现 '必须第一步 / 第二步 / 第三步'",
    "system prompt 里出现 '会议纪要一定要 ...'",
    "system prompt 里出现 '某类客户一定 ...'",
    "代码里出现 'if input_type == X: call_Y()'",
    "代码里出现 'if client.name == ...'",
    "成果类型固定 if/else 分支",
]

# B 报告里凡是命中 → 标 "hardcoding_risk_high"
```

A 看到 hardcoding_risk_high → 立刻修, 不能合 PR.

---

## 唯一例外: "preferred path" 缓存 (学到的流程, 不是写死的流程)

```
开放架构 + plan_cache 学习:
  第 1 次跑明远 → AI 自主拆 plan (慢, 30s, 但学到了)
  plan 跑通后 → 存 agent_plan_cache (按 goal_signature + client_profile)
  第 2 次类似目标 → 优先 fetch 缓存 plan, AI 验证 "适用吗?" → 5s
  不同场景 → cache miss → 重新拆 → 慢但学新

特征:
  ✅ 架构开放 (工具是 registry, AI 自主)
  ✅ 用户体验稳 (第 1 次慢, 后续快)
  ✅ 可扩新场景 (cache miss 就重学)
  ✅ 可审计 (cache 里每个 plan 可看可调)

不算硬编码. 因为:
  - cache 是 LLM 生成的 plan, 不是工程师写的
  - cache 可以被 LLM verify 是否仍适用
  - cache 失效后自动重学
```

→ V3.0 P3 路线图: plan_cache 是必备组件, 不是反 pattern.

---

## 红线如何执行

| 阶段 | 责任 |
|---|---|
| A 写代码 / prompt | **A 必须自查**, 不命中 5 条禁止规则 |
| B 评估 commit | **B 每次跑扫描**, 自动标 hardcoding_risk |
| 顾源源 review | **顾源源最终拍板**, 命中 risk_high 的不合 |
| 跨领域 Golden Pack | ≥ 10 类才算证明开放 |
| 真测 | B Golden Pack × 14 功能, AI 在新场景能跨工具调度 = 真开放 |

---

## 顾源源原话归档

```
"我们不是要训练一个会走固定流程的 AI,
 而是要建一个足够清楚的数据中心和工具系统,
 让任何强模型都能读懂现状、理解工具、自己规划、自己执行,
 并在关键处让人确认."

"测试可以具体, 架构必须开放."

"硬编码流程能让 demo 快速成功, 开放架构才能让平台真正长大."
```

→ 写进 V3.0 架构文档**首页第 0 条**.

---

**Author**: AI B (落档 顾源源 5/23 钦定) · 2026-05-23 21:30
**冻结**: V1
**关联**:
- 顾源源 5/23 21:30 强烈拍板原话 (本对话)
- `docs/V3_0_GOAL_DRIVEN_AI_COMPANY_OS.md` (应在此文件顶部插入红线第 0 条)
- B 23 综合评估报告 (架构红线讨论起点)
