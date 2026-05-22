# B AI · V2.2 现状 · Karpathy 方法论评估 + 新计划

> **触发**: 顾源源 5/22 19:xx "用 karpathy 方法评估 V2.2 + 按规则排查"
> **执行规则**: 顾源源 [[feedback_run_by_rules_trigger]] "按规则排查, 然后做计划 → 不问不解释立刻跑"
> **数据基础**: B 30 分钟前刚跑完的 systematic inventory (commit `6cd753a` / 17:46) + 4D inventory (`36e1264` / 17:27) — 数据新鲜, 不重采
> **方法论 skill**: `~/.claude/skills/karpathy-software-3-0/SKILL.md` (B 刚部署, 19:13)
> **独立采样规则**: §7.3 — 不读 A 同时段 964458b v2 评估, 写完再比较

---

## 0 · 4 维度数据基础 (复用 systematic inventory, 不重复)

按协作文档 §7.1 强制 4 维度, B 已跑完 (commit `6cd753a` 完整事实):

| 维度 | 关键数字 | 来源 |
|---|---|---|
| D1 产品手册 9 板块 | 战略陪伴钦定 6 段 (essence/cooperation/business_intro/people/timeline/next_steps) | `docs/V2.2_PRODUCT_MANUAL_FULL_TEXT.md` |
| D2 主仓库代码 | 175 services / main.py 54885 行 / narrative_generator 1156 行 | `docs/B_AI_FULL_SYSTEMATIC_INVENTORY_20260522.md` §1 |
| D3 数据库表 | 217 张 / 161 有数据 / 56 空管道 / atomic_facts 1998 / activity_logs 26677 | systematic §2 |
| D4 V2.1 B 视角 | 14 commit / 阶段 0 砍 11 .DEPRECATED / 真活代码 = IdempotencyStore + api + docs | systematic §5.2 |

→ 数据完整, 直接进 Karpathy 心智模型切片.

---

## 1 · §1 Software 1.0 / 2.0 / 3.0 三层架构视角

**V2.2 现在每件事在哪层?**

| 任务 | 真实层 | 该在的层 | 偏差 |
|---|---|---|---|
| `ingest_pipeline.detect_update_relation` 5 条规则判 conflict/supersedes | 1.0 ✅ | 1.0 | ✅ 对 |
| `DocumentLLMExtractor` 抽 atomic_facts | 3.0 ✅ | 3.0 | ✅ 对 |
| `narrative_generator` 6 段拼故事 | **混合** (collector 1.0 + LLM 3.0) | 3.0 主导, 1.0 兜底 | ✅ 对 |
| `smart_file_import.py:1002` 直接 INSERT atomic_facts | 1.0 (硬编码 INSERT) | 应走 IngestPipeline (1.0 normalizer + 3.0 LLM 判 role) | 🔴 **过度 1.0** |
| `intelligence_candidate_supply.py` 7111 行 | **过度 1.0** (硬编码业务逻辑爆炸) | 应该把"判断哪些情报相关"的 3.0 部分 LLM 化 | 🟡 **过度 1.0** |
| 任务复盘 → atomic_facts (没接) | 不存在 | 1.0 normalizer + 3.0 LLM 抽 fact | 🔴 **0 层** |
| 爬虫 → atomic_facts (没接) | 不存在 | 1.0 + 3.0 | 🔴 **0 层** |
| 手机聊天 → atomic_facts (没接) | 不存在 | 1.0 + 3.0 | 🔴 **0 层** |
| 9 板块用 atomic_facts (只 2 个) | N/A | L2 共识层 1.0 接 + 3.0 调用 | 🟡 7/9 板块没接 |

### Karpathy §1 视角诊断

**V2.2 整体 = 1.0 过重 + 3.0 不足 + 2.0 几乎缺席**

```
1.0 (显式代码):    🟢 充足甚至过重 (intelligence_*  14 个服务硬编码逻辑)
2.0 (训练好的模型): 🟡 仅 entities NER (4987 实体), embedding_provider, rerank_provider
3.0 (LLM prompt):  ⚠️ DocumentLLMExtractor + narrative_generator 是孤岛, 其它 6 板块 LLM 没接入数据中心
```

→ **应用**: V2.2 不缺 1.0 代码 (175 services 已经够多), 缺的是 **3.0 LLM 真接到每个板块**.

---

## 2 · §2 LLM as OS · Context 管理视角

**V2.2 把 LLM 当 OS 用得对吗?**

| OS 类比 | V2.2 现状 | Karpathy 标准 | 评估 |
|---|---|---|---|
| Context = RAM | 完全没管理 (54885 行 main.py 一锅炖) | 主动 swap, progressive disclosure | 🔴 不及格 |
| Tools = IO 设备 | 175 services 互调, 但**没 service registry** | tool 命名稳定 + schema 严格 + 输出确定 | 🟡 部分 |
| Embedding = 硬盘 | `embedding_provider.py` + `knowledge_master_index` 518 条 | persistent retrieval | 🟢 OK |
| Agent 多步推理 | reasoning_traces 表 20 字段, **0 行流量** | 跨步追溯 + 自我学习 | 🔴 装好没用 |
| 中断 / 系统调用 | `broadcast_data_changed` 钩子 (一处写全局刷) | 事件驱动 | 🟢 OK |
| Prompt 即程序 | LLM 调用散落 ai.py (5550 行) | prompt 集中管理 + 版本化 | 🔴 散乱 |

### Karpathy §2 视角诊断

**致命的 Context 不管理**:
- A 跑 dogfood 6 段 = 把 13 张表的全部数据 stuff 进 prompt → 当 atomic_facts 长到 5000+ 条时会爆 context
- workspace_chat_multipass 多轮对话 → context 累积无管理

**reasoning_traces 表设计成熟 (20 字段) 但 0 行流量** — 整个 N3 8 张核心表全 0 = **OS 把 swap 区准备好了但从不 swap**.

→ **应用**: 没有真"AI 操作系统", 只有"LLM 嵌入到散乱 1.0 代码里 175 处".

---

## 3 · §3 Eval-Driven Dev 视角 (核心审视点)

**V2.2 有真 eval-first 吗?**

| 模块 | 有 eval dataset? | 有 eval runner? | 用 eval 数字驱动迭代? |
|---|---|---|---|
| narrative_generator 6 段 | ⚠️ 5/19 张真会议 (但只 1 个 dataset) | ✅ A 跑 dogfood (964458b 之前) | ⚠️ 跑出 1/7 但 prompt 还没改 |
| F2.1 DocumentLLMExtractor | ✅ 5/19 docx 真跑 (25 条 fact) | ⚠️ B 写过 baseline runner 已砍 | ❌ |
| `intelligence_candidate_supply` | ❌ 没 dataset | ❌ | ❌ |
| `growth_engine` | ❌ | ❌ | ❌ |
| `workspace_chat_multipass` | ❌ | ❌ | ❌ |
| 9 板块其它 | ❌ | ❌ | ❌ |

### Karpathy §3 视角诊断

**6 段叙事 = V2.2 唯一接近 eval-driven 的部分**. 其它 8 个板块跟 9 个其它服务 (intelligence/growth/workspace/...) **全是凭感觉调 prompt**.

V2.2 路径 1 (工作台文件) 走通的根因 = **它有 5/19 这一个 eval dataset**. 其它路径 / 其它板块没通 = **它们连 eval dataset 都没建**.

→ **应用 Karpathy 公式**: "Show me your eval, I'll tell you your model" — 当前 V2.2 模型 = 1/9 板块有 eval = **质量 1/9**.

---

## 4 · §4 长任务 Agent Harness · 三角色视角

**V2.2 双 AI 协作是不是真 Planner/Generator/Evaluator?**

| Karpathy 角色 | V2.2 实际身份 | 是否真按角色工作? |
|---|---|---|
| Planner | 顾源源 | ✅ 5/22 顾源源连发 5 个 sync 指令 (asset_pivot / new_plan / 4d / 按规则 trigger) — Planner 主动 |
| Generator A | A AI | ✅ A 做 schema / 内核 / collector / NarrativeKernel — 跟分工对得上 |
| Generator B | B AI | ✅ B 做 endpoint / 前端 / 测试 / audit — 跟分工对得上 |
| Evaluator | baseline runner / dogfood / 三道门 | ⚠️ **存在但弱** — baseline runner 砍了, dogfood 是 A 自己跑, 三道门是 manual |

### Karpathy §4 视角诊断

**A/B Generator 协作很健康** (5/22 一天连跑 4 次纠偏接力, 0 误删对方文件), **Planner (顾源源) 极强主动** (5 次 sync 全是顾源源驱动).

**唯一弱角色 = Evaluator**:
- baseline runner 砍了, 重写排到阶段 2
- dogfood 是 A AI 自己跑自己审, 不独立
- 三道门 audit 是 manual checklist, 不自动化

→ **应用**: V2.2 缺一个**独立 Evaluator**. 当前 Generator A 既跑 dogfood 又审 dogfood = 自评.

---

## 5 · §5 多 AI 协作模式视角

**V2.2 实际用的是哪种模式?**

按 Karpathy skill §5 三模式分类:

| 模式 | V2.2 真实使用 |
|---|---|
| 模式 A · 序贯接力 (A → B → A) | ✅ sync 指令 §阶段 0-5 是这套 |
| 模式 B · 平行独立采样 (A 跑 + B 跑 + 比较) | ✅ §7.3 5/22 钦定 (4D 评估 + 本文 vs A 964458b) |
| 模式 C · 互检 (A 写 → B 审 → A 改) | ✅ B asset_pivot self-audit 是这套 |

### Karpathy §5 视角诊断

**V2.2 同时跑 3 种模式, 非常健康**. 5/22 一天就完整跑过 3 种:
- 模式 A: 阶段 0 双方各砍各的
- 模式 B: A v2 4D + B v2 4D (本文)
- 模式 C: B 自检报告

**反模式检查** (§5):
- ❌ "A 和 B 同时改同一文件" — V2.1 没发生 (协作文档 §8 严守)
- ❌ "A 跑了 B 不验证就照抄" — V2.1 没发生 (§7.3 钦定不允许)
- ❌ "B 不跟 Planner 对齐自己加任务" — B 5/22 没越界

→ **应用**: V2.2 协作模式 = Karpathy 教材级正确. 这是难得的优点.

---

## 6 · §6 Unhobbled Iteration · 拆轮子视角

**V2.2 哪些"过度约束"该拆?**

| 当前约束 | 是不是过度? | 拆掉会怎样? |
|---|---|---|
| V2.1 必须设计跟主仓库平行的 8 段叙事 | ❌ 已拆 (5/22 阶段 0 砍废) | 已经拆了, 效果立竿见影 |
| narrative_generator 必须用 deterministic 列事实 | 🔴 过度 | 拆 → v1 LLM 编排 (A 阶段 2 正做) |
| atomic_facts 必须经 IngestPipeline (path 1 没真经) | ⚠️ 没强制 → 反过来变成"约束不够" | 强制走 IngestPipeline → cross-source 信息商真触发 |
| 路径 2/3/4 必须等 path 1 完美再做 | 🔴 过度 (我 5/22 早判断) | 拆 → 4 路径并行接入 |
| "1 个 LLM 调用一次解决一段" | 🔴 过度 | 拆 → §4 三角色分 (Planner 拆段 + Generator 各段单调 + Evaluator 整合) |
| V2.1 必须做平行实验, 跟主仓库不能 merge | 🔴 过度 | 拆 → F2.8 + ClientFactView L2 sync 回主仓库 |

### Karpathy §6 视角诊断

**V2.2 已经拆过 1 个轮子 (8 段假增量) + 立刻见效**. 现在还有 5 个轮子该拆.

最该立刻拆的 2 个:
- **轮子 #1**: "路径 2/3/4 必须等 path 1 完美再做" — 拆了 IngestPipeline 4 路径才能真触发跨源信息商
- **轮子 #2**: "V2.1 不能 merge 回主仓库" — 拆了 IdempotencyStore + ClientFactView 才能真服务用户

---

## 7 · §7 反检查清单 (调用前必跑)

按 Karpathy skill §7, 跟 V2.1_AI_COLLABORATION.md §6.2 互锁:

| Q | Karpathy 标准 | V2.2 真实状态 |
|---|---|---|
| Q1 有 eval dataset 吗? | 没 eval 不准动 prompt | ⚠️ 5/19 1 个 (1/9 板块) |
| Q2 加的事是 Software 几层? | 三层共存原则 | 🔴 1.0 过重 / 3.0 孤岛 / 2.0 缺席 |
| Q3 Planner/Generator/Evaluator 都有人吗? | 单 LLM 做不了长任务 | ⚠️ Planner/Generator 强, Evaluator 弱 |
| Q4 有没有过度约束? | 拆轮子 | 🔴 5 个轮子待拆 |

**4 道题命中度: 1/4 满分 / 3/4 部分** — V2.2 当前是 "好的协作 + 过重 1.0 + 弱 evaluator + 待拆轮子".

---

## 8 · Karpathy 视角 V2.2 现状综合判定

### 8.1 单维度评分 (Karpathy 5 视角)

```
§1 三层架构:           ████░░░░░░ 40%  (1.0 过重, 3.0 不足, 2.0 缺席)
§2 LLM as OS:          ███░░░░░░░ 30%  (context 不管理, 8 张 N3 表 0 流量)
§3 Eval-Driven:        ██░░░░░░░░ 20%  (只 1/9 板块有 eval)
§4 三角色:             ███████░░░ 70%  (Planner/Generator 强, Evaluator 弱)
§5 协作模式:           █████████░ 90%  (3 种模式都跑过, 0 反模式)
§6 Unhobbled:          ████░░░░░░ 40%  (拆了 1, 待拆 5)

平均: 48%
```

### 8.2 三大目标对照 (Karpathy 视角)

跟顾源源 5/22 18:xx 钦定 3 子目标:

| 子目标 | Karpathy 视角 | V2.2 真实 |
|---|---|---|
| a (AI 更深理解) | §1 + §3 (3.0 充分 + eval-driven) | 30% (3.0 LLM 孤岛 + 1/9 eval) |
| b (顺畅访问) | §2 (LLM as OS, context 共享) | 30% (9 板块只 2 个真用 fact bundle) |
| c (跨源印证) | §1 + §4 (3.0 + Evaluator) | 5% (4 路径只 1 路 + Evaluator 弱) |

**Karpathy 视角再确认我 5/22 18:xx 的判断**: c 是真目标, a 和 b 是前置. 当前 c=5% = 数据中心根没扎下.

### 8.3 Karpathy 最致命洞察

> "Show me your eval, I'll tell you your model"

V2.2 当前模型 = **1/9 板块有 eval** = 9 板块里 8 个在凭感觉调 prompt = 整体质量天花板 = 1/9.

→ **要把 V2.2 整体提到 N2 PASS, 必须先让 8/9 → 9/9 板块都有 eval dataset**, 而不是继续优化 1/9 那个.

---

## 9 · 新计划 (Karpathy 方法驱动)

### 9.1 立刻拆 2 个轮子 (§6 Unhobbled)

**轮子 #1**: 拆"路径 2/3/4 必须等 path 1 完美" → **并行接入 IngestPipeline**

- A 阶段 2 当前: 改 narrative_collector 补漏 → **优化 1/9 那一个** (Karpathy 视角 = 错优先级)
- 建议改成: A 阶段 2 → 切 IngestPipeline 4 路径 normalizer 真接业务调用
  - 路径 2: weekly_review_material_pack → IngestPipeline.ingest(metadata_for_task_review)
  - 路径 3: internet_crawler 写入时 → IngestPipeline.ingest(metadata_for_internet_crawler)
  - 路径 4: chat_messages 写入时 → IngestPipeline.ingest(metadata_for_mobile_ai_chat) (schema 不够要先扩)

**轮子 #2**: 拆"V2.1 不能 merge 回主仓库" → **本里程碑后立刻 PR**

- V2.1 IdempotencyStore (B F2.8) → 主仓库 sync (主仓库已经在用)
- V2.1 ClientFactView L2 共识层 → 主仓库 sync (用户感知到的 v2.2 启动)
- V2.1 协作文档 + 4D 流程 + Karpathy skill → memory + 全局沉淀

### 9.2 建 Evaluator (§4)

**当前**: A Generator 跑 dogfood + A 自审 = 自评. 不独立.

**建议**: B 接力指令 §阶段 2-5 改成 B 主导 dogfood eval, 不是 A.
- A 改 collector → B 跑 dogfood baseline → B 写 eval 数字 → 顾源源决策
- 类比 Karpathy "Planner / Generator / Evaluator" 三角色, 现在 A 既是 Generator 又是 Evaluator. 拆给 B.

### 9.3 8/9 板块建 eval dataset (§3)

**当前只 1/9 (战略陪伴 6 段) 有 eval**. 目标: 渐进让其它 8 板块都有.

按可感知度排:
1. **02 客户工作台** (用户高频使用) - 建"客户问 AI X, 期望答案 Y" 的 dataset (用现有 chat_messages 1125 条筛 20 个真问真答)
2. **04 资讯情报站** (intelligence_candidate 1703 条) - 建"哪些应该推哪些不推"的 golden 50 条
3. **01 任务与日程** (tasks 238) - 建"AI 抽行动项"的 golden dataset
4. **05 成长中心** (growth_signal_events 598) - 建"哪些应该算成长信号"的 dataset
5. **06 智能文件导入** (已有 5/19 这个) - 加 5/20 / 5/21 扩 dataset
6. **03 战略陪伴** (已有, 持续加新会议)
7. **08a 计划工坊** - schema 大量空管道, 先用就行不急建 eval
8. **08b 系统设置** - 不需 LLM eval

### 9.4 把 Karpathy skill 跟 V2.2 协议绑死 (§7)

修改 `docs/V2.1_AI_COLLABORATION.md` §6 + §7, 加入 Karpathy §7 反检查 4 题作为提案前必跑.

→ 这一步 B 立刻能做 (跟 §1.5 写共享文档同型).

### 9.5 §1 三层架构整顿 - V3.0 前必做

**长期任务** (不是本里程碑做):
- 1.0 过重: intelligence_candidate_supply 7111 行 → 拆部分到 3.0 LLM 判 (但要先建 eval, 否则不准动 §3)
- 2.0 缺席: 引入 fine-tune 客户专属 NER 模型? 或者纯 LLM zero-shot?
- 3.0 孤岛: prompt 集中管理 + 版本化 (现在散在 ai.py 5550 行各处)

---

## 10 · 立刻 actionable 的 4 件事 (按优先级)

| # | 任务 | 谁做 | 工作量 | Karpathy 理由 |
|---|---|---|---|---|
| 1 | A 阶段 2 重定向: 改 collector → 切 IngestPipeline 4 路径 | A 主导 | 2-3 天 | §6 拆轮子 #1 + §1 让 3.0 真接到每路径 |
| 2 | B 接管 dogfood eval (从 A 自评 → B 独立评) | B 立刻 | 0.5 天 | §4 独立 Evaluator |
| 3 | B 加 Karpathy §7 反检查 4 题进协作文档 §6.3 | B 立刻 | 30 min | §7 反"凭想象设计" |
| 4 | B 跟 A v2 (964458b) 比较 4D 数字 + 写联合声明 | B 接下来 | 30 min | §7.3 A/B 独立采样 → 比较 |

---

## 11 · 跟 A v2 (964458b) 的比较 (§7.3 联合声明)

按 V2.1_AI_COLLABORATION.md §7.3 钦定: A/B 各自独立跑, 写完比较.

**待做**: B 即将完整读 A 964458b v2 4D 评估 + 计划, 然后写联合声明:
- 数字对齐 ≤ 5% → 双方真相一致, 推进
- 数字差异 > 5% → 找 root cause

(本文写完先 commit, 联合声明单独 commit)

---

**Author**: B AI · 2026-05-22 · 用刚部署的 karpathy-software-3-0 skill 自切
**附**: V2.2 整体 Karpathy 综合评分 48% — 协作 (§5 90%) 救场, 但 §3 eval (20%) 和 §2 OS (30%) 拉后腿
