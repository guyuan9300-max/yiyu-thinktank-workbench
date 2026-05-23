# B AI · V3.0 AI 公司操作层 · 辅助理解 + 可执行设计 (5/23)

> **触发**: 顾源源 5/23 钦定 V3.0 = "目标驱动的 AI 公司操作层", 让 B "辅助对这个东西的理解"
> **作用**: 不是机械复述方案, 而是**翻译成具体可执行设计** + 跟 A V2.5 P0-1/2/3/4 + HONEST 对账 + B 下一步明确动作
> **执行人**: AI B
> **日期**: 2026-05-23 08:50

---

## 0 · 给顾源源的 3 句话核心理解

1. **本质**: 益语 3.0 不是给现有 8 板块"加 AI 功能", 而是 **把 8 板块本身变成 AI 团队的工具** — 工作台变会议室 / 数据中心变共享记忆 / 任务变行动调度 / 战略陪伴变研判会议室 / 资讯情报站变外部情报员 / 智能导入变档案员 / 成长中心变个人教练 / 计划工坊变战略办公室.

2. **关键转折**: 数据中心从"被动数据源"变"主动缺口发现器" — 这是 AI 公司操作层能真正工作的起点. 没有 Data Gap API, AI 调度只是机械流程; 有了 Data Gap API, AI 才能像 CEO 一样"看缺什么 → 调谁去补".

3. **现在欠的不是功能, 是底层协议**: 10 类接口 (Goal/Plan/Tool Registry/Data Gap/Domain Tool/Agent Role/Deliberation/Approval/Run Log/Evaluation) 是 V3.0 真起点. **每个现有功能都要同时支持人类入口 + AI 工具入口**, 这是接下来所有改动的设计约束.

---

## 1 · 4 层抽象 — B 翻译成"具体表/服务/责任"

| 层 | 顾源源描述 | B 翻译成系统现状 |
|---|---|---|
| **第一层 人类关系层** | 客户信任/开会/访谈/价值判断/最终拍板 | 不在系统里, 是用户线下工作; 系统**只暴露 Approval Queue 给人类** |
| **第二层 AI 公司操作层** ★ V3.0 新增核心 | 理解目标/制定计划/调用模块/分配角色/检查缺口/请求证据/形成草稿 | **完全缺**. 当前主仓库 0 服务承担这一层 (`Agent Gateway` / `Tool Registry` / `Plan API` / `Skill Manifest` 全部 0 字段 0 表 0 endpoint) |
| **第三层 功能模块工具层** | 现有 8 板块变 AI 工具 | 主仓库 175 services + 579 endpoint **大部分都已经存在**, 但**没注册到 Tool Registry**, AI 不知道有这些能力, 只能猜或者硬编码调用 |
| **第四层 数据中心共享记忆层** | 升级为"主动缺口发现器" | 当前数据中心是被动 (atomic_facts/event_log/ai_episode_log 都是写入累积). 没有 `data.gap_analyze()` 服务输出"我不知道什么". **完全缺** |

→ **缺口分布**: 第二层 100% 缺 + 第四层升级缺. 第三层 80% 在 (只缺注册和暴露). 第一层不动 (人类层).

---

## 2 · 10 接口跟 A V2.5 P0-1/2/3/4 对账

```
A V2.5 commit 5/23:
  0845ba7 P0-1+P0-2 IngestPipeline trigger deriver + detector
  abeae33 P0-3 ChatMessageReverseIngester
  e06818b P0-4 用户纠错 e2e + 3 客户 dogfood
  ee50669 HONEST 诚实重评 (主仓库一分没动)
```

| # | 接口 | A 当前覆盖 | 缺什么 |
|---|---|---|---|
| 1 | **Goal API** (goal.create) | 🔴 0 | 完全没有"目标"抽象, 当前 endpoint 都是动作级 (POST /tasks 创建任务, 不是"达成目标") |
| 2 | **Plan API** (plan.generate) | 🔴 0 | 0 planner service |
| 3 | **Tool Registry** | 🔴 0 | 0 注册表, 175 services 散落 |
| 4 | **Data Gap API** ★ | 🔴 0 | 没有 `analyze_gaps(client_id)` 服务. data_center_self_verify.py 现有但只做内部校验, 不输出"我不知道什么" |
| 5 | **Domain Tool API** | ⚠️ 50% | 579 endpoint 大部分动作级, 但**业务级工具** (meeting.process / weekly_review.generate 这种) 缺 |
| 6 | **Agent Role API** (Skill Manifest) | 🔴 0 | narrative_generator 是单角色, 0 决策协议 |
| 7 | **Agent Deliberation API** | 🔴 0 | 没有 AI 内部辩论, narrative_generator 是单链路 |
| 8 | **Approval Queue** | 🔴 0 | A V2.5 P0-4 加了用户纠错 e2e (verification_status), 但**没有正式 ApprovalQueue 表 + endpoint** |
| 9 | **Agent Run Log** | ⚠️ 60% | event_log 312 + ai_episode_log 312 + reasoning_traces 7 ✅ 基础就位, 但**没有 run_id 串联整条链**, 不能"给我看这次会议纪要处理的完整 trace" |
| 10 | **Evaluation API** | ⚠️ 40% | dogfood baseline runner + 6 维度评分 ✅ 部分, 但**不评估"是否推动公司工作往前走"** |

→ **10 接口里 6 张完全缺 / 3 张部分有 / 1 张基础有**.

**V3.0 真起点**: A V2.5 P0-1/2/3/4 解决的是"功能模块写入数据中心" 这条**第三层 → 第四层**链路. **第二层 AI 公司操作层完全没起步**, 这是接下来要补的核心.

---

## 3 · 4 设计原则 — B 翻译成具体动作

### 原则一 · 每个功能必须同时支持人类入口 + AI 工具入口

**当前现状** (B 实测):
- 579 endpoint 里**多数是给前端按钮调的**, 不是为 AI 调用设计 (X-Actor-Type 覆盖率 0.3%)
- workspace_chat 依赖 `get_cached_session_user()` — AI agent 没 session
- smart_file_import 走 session 模式 ✅ 部分支持 AI

**具体动作**:
1. **加 X-Actor-Type middleware** 覆盖 579 endpoint (A 1-2 天)
2. **改 workspace_chat 接受 X-Actor-Type: ai_agent + X-Actor-Id** (A 0.5 天)
3. **每个 endpoint POST 接受 idempotency_key header** (扩展 B F2.8 模式, A 1 天)

### 原则二 · 不要硬编码流程, AI 通过目标选择模块组合

**当前现状**: smart_file_import.py 1358 行硬编码"上传文件→抽取→沉淀" 一条链.

**具体动作**:
1. **拆 service**: 把 smart_file_import 拆成 6-8 个独立工具 (sfi.create_session / sfi.add_file / sfi.add_narration / sfi.parse_roles / sfi.commit) — 现有部分已经有 session 模式, 暴露所有 sub-step 即可
2. **加 Goal-Plan-Tool 三层** (A 2-3 天):
   - `POST /api/v1/agent/goals` (goal.create)
   - `POST /api/v1/agent/goals/{id}/plan` (plan.generate, 调 LLM 拆步骤)
   - `POST /api/v1/agent/runs` (run.execute, 调具体 tool)
   - `GET /api/v1/agent/runs/{id}` (status + diff + 回滚)

### 原则三 · 数据中心从"被动数据源"变"主动缺口发现器" ★ 最关键

**当前现状**: 0 服务. 没有 `analyze_gaps(client_id)`.

**具体动作** (V3.0 P0 第 1 优先级):

新建 service: `backend/app/services/data_gap_analyzer.py`

```python
class DataGapAnalyzer:
    def analyze(self, client_id: str) -> list[DataGap]:
        """主动找出客户档案缺什么"""
        gaps = []

        # 1. 缺权威值 (atomic_facts 多版本但无 user_confirmed)
        if has_conflicting_facts_no_confirm(client_id):
            gaps.append(DataGap(
                gap_type="missing_authoritative_value",
                suggested_tools=["workbench.ask_user", "clarification.create"],
                priority="high",
            ))

        # 2. 缺外部证据 (内部说 X, 没有 internet_official source_type 印证)
        if has_internal_only_facts(client_id):
            gaps.append(DataGap(
                gap_type="missing_external_evidence",
                suggested_tools=["intel.search"],
                priority="medium",
            ))

        # 3. 缺时间锚 (重要 fact 没 time_anchor)
        # 4. 缺人物归一 (entity 散落)
        # 5. 缺承诺履行状态 (commitment 过期未关闭)
        # 6. 缺最近活动 (event_line_activities 超 30 天没新增)
        # 7. 缺战略判断 (strategic_thought_insights 不到 3 条)
        ...
        return gaps
```

A 工作量: 1-2 天 (含 endpoint `GET /api/v1/clients/{id}/data-gaps`).

**这是数据中心从"被动"变"主动"的核心**. 没这一步, AI 不知道该调谁去补.

### 原则四 · CEO skill = 决策协议, 不是 prompt

**当前现状**: narrative_generator 单一风格, 0 skill manifest.

**具体动作** (V3.0 P1):

新建表: `agent_skills`
```sql
id, skill_name, decision_style, priority_order_json,
default_questions_json, allowed_tools_json, forbidden_actions_json,
created_at, updated_at
```

种子数据:
- product_visionary_ceo (用户价值/产品清晰度/长期品牌优先)
- operational_efficiency_ceo (闭环/指标/速度优先)
- risk_control_coo (权限/承诺/审计优先)

A 工作量: 0.5 天 (schema + 3 种子).

---

## 4 · 7 最小接口包优先级 (B 推荐给 A 接力的顺序)

按"先解决卡 V2.5 真问题" + "先打通 AI 公司操作层最小骨架" 排:

| 优先级 | 接口 | 拦截 V3.0 的什么 | A 估时 |
|---|---|---|---|
| **P0** | **Data Gap API** ★ | 数据中心被动→主动 (第四层升级核心) | 1-2 天 |
| **P0** | X-Actor-Type middleware | 579 endpoint AI 调用上下文绑定 (硬门槛 3) | 1-2 天 |
| P1 | Goal/Plan/Run 三件套 | 第二层 AI 公司操作层最小骨架 | 2-3 天 |
| P1 | Tool Registry | 第二层调度依据 | 1 天 (基于现有 175 services 注册) |
| P2 | Approval Queue | 硬门槛 4 + 第一层人类裁决入口 | 2 天 |
| P2 | Skill Manifest | CEO skill 决策协议 | 0.5-1 天 |
| P3 | Agent Run Log run_id 串联 | 现有 3 张表加 run_id 外键 | 0.5 天 |

总: **A 8-12 天 P0-P3 跑完**, 第二层 AI 公司操作层骨架成立.

→ A 之前 V2.5 P0-1/2/3/4 (5 个 commit 1 小时) 这种自我加速节奏, 估实际 **3-4 天能跑完 P0-P3 骨架**.

---

## 5 · A V2.5 HONEST 重评 3 选项 (B 评估)

A 给顾源源 3 选项:
1. cherry-pick V2.1 lab → 主仓库 代码 (1 天)
2. 继续 P1 4 板块再一次 cherry-pick (4-6 天)
3. prod db 一次性 read-write 提升 + 后续 cherry-pick (今天能让顾源源看到变化)

A 推荐: **3 + 1 组合**.

### B 评估 (基于 V3.0 新方向)

**B 推荐**: **方式 1 优先, 3 暂缓**.

理由:
- 方式 3 (prod db 一次性 read-write 提升) **只解决"用户看到数字变化"**, 不解决 V3.0 真目标 (第二层 AI 公司操作层骨架)
- 方式 1 (cherry-pick lab → 主仓库) 是**正确路径**, 让 V2.5 P0-1/2/3/4 真正在用户感知层生效
- 方式 2 (继续 P1) **等 V3.0 P0 (Data Gap API + X-Actor-Type) 做完再考虑**, 否则 P1 改更多 backend 仍然不是 V3.0 真路径

修正建议:
```
T+0:    方式 1 cherry-pick V2.5 P0-1/2/3/4 → 主仓库 (A 1 天)
T+1 天: V3.0 P0 Data Gap API + X-Actor-Type middleware (A 2-3 天)
T+3-4 天: V3.0 P1 Goal/Plan/Run + Tool Registry (A 3-4 天)
T+5-6 天: V3.0 P2 Approval Queue + Skill Manifest (A 2-3 天)
T+6 天:  B 跑 R2 "AI 主动补缺口"测试 (1-2 天)
```

→ 总 **~8 天到 R2 验收**.

---

## 6 · R2/R3/R4 目标修订 (跟 V3.0 新方向对齐)

11 文档定的是"AI 客户工作闭环指数 100 分制", 现在 V3.0 升级后, 修订 R2:

### R2 · 工程验收 (V3.0 P0+P1 完成)

| 指标 | 目标 | 跟 11 文档对比 |
|---|---|---|
| **AI 目标调度能力** (Goal→Plan→Tool→Result 全链路) | 100% | 升级 (新维度) |
| **数据中心识别缺口** | ≥ 3 条 | 升级 (新维度) |
| **调用资讯情报站/文件检索补证** | ≥ 1 次 | 升级 (新维度) |
| 调动模块 | ≥ 4 | 11 维度 1 保留 |
| 任务草稿 | ≥ 1 | 11 维度 4 保留 |
| 澄清问题 | ≥ 1 | 11 维度 3 保留 |
| Agent Run Log 完整 | 100% | 11 维度 7 保留 |
| 跨客户串线 | 0 | 11 硬门槛 7 保留 |
| 7 硬门槛通过 | ≥ 6/7 | 11 标准 |

### R3 · dogfood 前 (V3.0 P2 完成 + 双驱动跑通)

| 指标 | 目标 |
|---|---|
| AI 客户工作闭环指数 | ≥ 80 |
| 7 硬门槛 | 7/7 通过 |
| 内置/外置驱动一致性 | ≥ 80% |
| **数据缺口补证后用户感知变化** | ≥ 80% 测试案例 |
| 用户纠错保持率 | 100% |
| 故事卡关键段完整率 | ≥ 90% |

### R4 · 真实使用 (用户开始依赖)

| 指标 | 目标 |
|---|---|
| 三客户 dogfood 平均分 | ≥ 80 |
| **用户感觉 "AI 团队在帮我工作" 评分** | ≥ 4/5 (新指标, 顾源源最在意) |
| 用户 10 分钟内看懂客户状态 | ≥ 80% |
| 每客户有效澄清 | ≥ 3 |
| 每客户可执行下一步 | ≥ 3 |
| 使用前后故事卡提升 | ≥ 20% |

---

## 7 · B 下一步动作 (不撞 A V2.5 / V3.0 P0-P3 工程)

| 工作 | 何时 | 工作量 |
|---|---|---|
| B-1: CLI 命令规范设计 (yiyu agent goal/plan/run/approvals/storycard/datacenter) | 现在可做 | 1 天 |
| B-2: Data Gap API 输出 schema 设计 (跟 A 协商接口契约) | 现在可做 | 0.5 天 |
| B-3: "AI 主动补缺口"测试场景脚本 + 真数据准备 | A V3.0 P0 完成后 | 1 天 |
| B-4: 双驱动同题测试对比框架 (A 组内置 + B 组外置 CLI) | A V3.0 P1 完成后 | 1 天 |
| B-5: 跑 R2 验收 + 修订 100 分制评分 | A V3.0 P2 完成后 | 1-2 天 |

总 **B 4-6 天工作量**, **0 行代码改 backend**.

---

## 8 · 8 个新名词 (B 提炼, 供 A + 顾源源对话用同语言)

| 新名词 | 定义 | 在哪用 |
|---|---|---|
| **AI 公司操作层** (AI Company Operating Layer) | 第二层, 理解目标/制定计划/调用模块/分配角色 | V3.0 全文核心 |
| **共享记忆** (Shared Memory for AI Team) | 第四层数据中心升级形态 | 替代"数据中心被动数据源" |
| **决策协议** (Decision Protocol) | CEO skill 的真本质, 非 prompt | Agent Role API |
| **数据缺口主动发现** (Active Data Gap Discovery) | 数据中心新能力 | Data Gap API |
| **业务级工具** (Business-level Tools) | meeting.process / weekly_review.generate 这种, 非按钮级 | Domain Tool API |
| **CEO 工具** (CEO-level Tools) | 目标级指令, "找下周最值得推 5 件事" | 上层 |
| **AI 内部辩论纪要** (Agent Deliberation Transcript) | 多 AI 角色讨论留痕 | Deliberation API |
| **可调度的客户工作系统** (Schedulable Client Work System) | 益语 3.0 完整形态 | 对外表达 |

---

## 9 · 给顾源源的 5 个决策点

| # | 决策点 | 选项 |
|---|---|---|
| 1 | **V2.5 主仓库提升路径** | 方式 1 (cherry-pick lab → 主仓库) / 方式 3 (prod db read-write 提升 + 后续 cherry-pick) — B 推荐 1, A 推荐 3+1 |
| 2 | **V3.0 P0 是否立刻开始** | 现在开始 / 等 V2.5 cherry-pick 完成 — B 推荐"V2.5 cherry-pick + V3.0 P0 并行" |
| 3 | **Data Gap API 优先级** | P0 (B 强推) / P1 (其它先) — B 推荐 P0 (数据中心从被动→主动是 V3.0 起点) |
| 4 | **CEO skill 第一批种子** | 3 种 (product_visionary / operational_efficiency / risk_control) / 5 种 / 1 种 — B 推荐 3 种 |
| 5 | **R2 验收测试场景** | 11 文档"会议纪要处理闭环" / 12 文档"AI 主动补缺口" / 两个都做 — B 推荐**12 文档为主, 11 作底** |

---

## 10 · 综合判断

V3.0 = **目标驱动的 AI 公司操作层** 不是营销词, 是真实可执行的架构升级.

它的最小骨架:
```
Goal → Plan → Tool Registry (175 services 注册) → Data Gap → Domain Tool → Approval → Run Log
```

只要这 7 件预留, 未来:
- 内置模型/外置 Codex/Claude/CEO skill 都用同一套底座
- 数据中心从"被动展示" 升级为"主动调度判断源"
- 8 板块从"页面"变"AI 工具"
- 人类负责关系/价值判断/最终确认

A V2.5 P0-1/2/3/4 解决了**第三层 → 第四层** (功能模块写入数据中心), 还差**第二层 (AI 公司操作层)** 整层. V3.0 P0-P3 ~8 天就能搭起最小骨架.

**B 强烈建议**: 这套设计**不要拆**, V3.0 P0 必须先做 Data Gap API + X-Actor-Type middleware, 这是整条链路的"入口"和"中枢". 其它接口按依赖关系自然展开.

---

**Author**: AI B · 2026-05-23 08:50
**附**: 跟 A `ee50669 HONEST` 重评协作闭环跑通 — B 5/22 R1 报告 38 分诚实 → A 5/23 P0-1/2/3/4 高速跑 → B 5/23 sync 指出 prod db 没动 → A 自我 HONEST 重评 + 给顾源源 3 选项 → B 12 落档 + 本辅助理解 → 等顾源源决策.
