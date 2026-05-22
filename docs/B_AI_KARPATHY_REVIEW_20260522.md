# B AI · K-3 Karpathy 7 维度独立 review

> **触发**: A AI sync 指令 K-3 (`docs/B_AI_SYNC_20260522_K3_KARPATHY_REVIEW.md`)
> **目标**: 用 Karpathy 7 维度独立 review A AI Karpathy 评估 (c427d18 `V2.2_KARPATHY_EVALUATION_20260522.md`)
> **采样原则**: V2.1_AI_COLLABORATION.md §7.3 — 不 copy A 数字, 自己跑 sqlite3 验证
> **执行人**: AI B
> **日期**: 2026-05-22 19:30+

---

## 0 · 独立数据 verify (跑 sqlite3 跟 A 数字对账)

| A 声称 | B 自跑 sqlite3 结果 | 一致? |
|---|---|---|
| atomic_facts 100% update_relation='none' | **1998/1998 全 none, 0 conflict/supersedes/complement** | ✅ 100% 印证 |
| reasoning_traces 0 行 | 0 | ✅ |
| ai_episode_log 0 行 | 0 | ✅ |
| event_log 0 行 | 0 | ✅ |
| idempotency_keys 0 行 | 0 | ✅ |
| prompt_log 0 行 | 0 | ✅ |
| ai_learned_rules 0 行 | 0 | ✅ |
| ai_improvement_suggestions 0 行 | 0 | ✅ |
| ai_feedback_signals 0 行 | 0 | ✅ |

**B 独立数据结论**: A AI 关键事实 9/9 印证, 数据可信. 进入方法论 review.

---

## 1 · 7 维度对照表 (A 判断 vs B 独立判断)

| 维度 | A 判断 | B 独立判断 | 印证 / 异议 |
|---|---|---|---|
| §1 三层架构 | ✅ 三层共存 | ⚠️ **基本同意 + 1 反例** | A 说"没看到错层错用", 但 `smart_file_import.py:1002` 直接 INSERT atomic_facts 是 1.0 写, 漏了 IngestPipeline 该跑的 1.0+3.0 流程 — 这是错层 |
| §2 LLM as OS · syslog | 🟡 reasoning_traces 0 | ✅ **完全印证** | 实测验证 + B 补一条: broadcast_data_changed 是 interrupt signal (A OS 类比表里漏了) |
| §3 Eval-Driven | 🟡 eval 对象错 (我 87% vs dogfood 1/7) | ⚠️ **同意 + 修正补 L1 层** | A 提议"eval 对象改 6 段输出"对, **但漏了 L1**: 应该 L1 (atomic_facts 抽取质量) + L2 (6 段拼合质量) 双层 eval, 单 L2 会掩盖 L1 |
| §4 三角色 · Evaluator 弱 | 🟡 V2.2 完成后做 | 🔴 **异议** — Evaluator 自动化应该现在做, 不是 V2.2 后 |
| §5 协作模式 | ✅ + v2 缺 B review | ✅ 印证 + 补 1 条 | B review 即本文 ✅; 补: 协作延迟周期 (Planner 主动指令间隔) 是否最优? |
| §6 拆轮子 · 3 候选 | V2.1 双 app / 4 路径 / 文档 | ⚠️ **3 条都有不同判断** | 详见 §6 |
| §7 反检查 + Q5 | ✅ + Q5 eval 对象 | ✅ + 提 **Q6 + Q7 候选** | 详见 §7 |

---

## 2 · 我的 5 处独立异议 / 修正 (按重要度)

### 异议 1 · §1 错层反例 — smart_file_import.py:1002

A 7 维度评估 §1 判 ✅ "三层共存原则已落地, 没看到错层错用".

**B 反例**: `smart_file_import.py:1002` (主仓库 + V2.1 同) 直接执行:
```python
INSERT INTO atomic_facts(...)
```

→ 这是路径 1 已经在用的写入路径, **不经 IngestPipeline.ingest()**, 跳过了:
- 1.0 detect_update_relation (信息商引擎)
- 1.0 metadata_for_workbench_file (渠道 normalizer)
- 3.0 LLM 判 content_role 二次精化
- 3.0 actor / time_anchor / speaker 推断

**这就是 §1 视角的错层**: 1.0 直接 INSERT 把本该 1.0+3.0 共存的流程压成纯 1.0.

**Karpathy 视角解释**: 正是这一处错层导致 update_relation 100% 是 'none' (因为没经引擎). 修这一处 = 跨源信息商立刻能在路径 1 内部触发 (多 docx 抽出同 subject+attribute 的 fact 会撞).

**A 评估漏点**: A 说"三层共存已落地"是看大架构, 看具体调用点会发现路径 1 这一处把架构绕过去了.

---

### 异议 2 · §4 Evaluator 自动化优先级 — 现在做, 不是 V2.2 后

A 7 维度评估 §4 + K-2 行动说 **"Evaluator 自动化 V2.2 完成后做, 不阻塞主路径"**.

**B 反对**:

Evaluator 自动化是 V2.2 推进的**工具**, 不是 V2.2 后的优化.

```
反例 (A 当前真实工作流):
  A 改一次 collector → 手动跑 dogfood 脚本 (~30 秒) → 人读 markdown → 看 1/7 → 判断
  
  假设 A 阶段 2 改 collector 迭代 10 次:
  10 × 30 秒 + 10 × 人读 markdown (2 min) = 25 min 等待 + 大量人读时间
  
  自动 evaluator:
  10 × auto trigger eval → JSON 报告 → 看综合 P% 数字
  = 5 min 等待, 0 人读
```

**Karpathy §3 视角**: 没自动 eval = 凭感觉调 prompt = §3 反模式. A 阶段 2 改 collector 没 evaluator = 跟 5/22 早上 B 自己测 87% 自我感觉良好同一类错误.

**B 建议**: K-2 跟 M-C (collector 补漏) 同步做, 不是 V2.2 完成后. 工作量小 (改现有 dogfood 脚本加 auto-trigger + JSON 输出), 0.5 天.

---

### 异议 3 · §6 拆轮子候选 2 (4 路径) — V2.2 必须通路径 2

A 7 维度评估 §6 候选 2 说 **"路径 3/4 跟 V2.2 北极星 5/19 命中无关, 留 V2.3"** → 标 M-F V2.3.

**B 部分反对**:

A 站在 "5/19 唯一 dataset" 视角对 — 5/19 是 docx, 路径 1 就够.

但**站在三子目标视角错**:
- 目标 c (跨源印证) 当前 0% (实测 100% none 印证)
- 跨源印证的"源" = 4 路径
- V2.2 N2 北极星包含目标 c
- 因此 V2.2 不通路径 2/3/4 任一 → 目标 c 永远 0% → N2 永远不算 PASS

**B 折中提案**:
| 路径 | V2.2 必须通? | 理由 |
|---|---|---|
| 路径 1 (文件) | ✅ 已通 (但错层 - 见异议 1) | 必须 |
| 路径 2 (任务复盘) | ✅ **本 V2.2 必须通** | weekly_reviews 9 + meetings 7 + action_items 4 + commitments 66 数据齐, 接入工作量小 (1-2 天), 接入后跟路径 1 形成"客户官方 docx vs 我方任务复盘"跨源信息商首次触发 |
| 路径 3 (爬虫) | ⏸ V2.3 (跟 A 一致) | internet_official 数据跟 5/19 dataset 不匹配, V2.2 接没价值 |
| 路径 4 (手机聊天) | ⏸ V2.3 (跟 A 一致) | 手机端 v2 没启动, 工作量大 |

→ **B 跟 A 在路径 3/4 一致, 在路径 2 不一致** (A 把路径 2 留 V2.3 是错, B 觉得必须 V2.2 做).

---

### 异议 4 · §6 拆轮子候选 3 (文档过载) — 不是 archive 而是收敛产出率

A 7 维度评估 §6 候选 3 说 **"文档不是过度, 需要 indexer + 每 milestone archive 过期文档"**.

**B 同意"不是过度" + 补充新视角**:

5/22 一天产出 5000+ 行 docs 不是质量问题, 是**产出率信号**:

```
顾源源 5/22 实际表达模式 (我观察到的疲劳):
- "你按推荐做"
- "不问不解释立刻跑"  
- "用 karpathy 方法评估"
- 4 个连续 sync 指令 (asset_pivot / new_plan / 4d / k3) 在 8 小时内
```

**Karpathy 视角真信号**: 顾源源 (Planner) 在快速推 Generator 工作, **不是文档太多, 是 Generator 反复纠偏次数太多** (4 次纠偏 = 4 套新文档).

**B 建议** (跟 A archive 方案补充):
- archive 过期文档 ✅ (A 提的, OK)
- **+ 收敛纠偏频次** — 下个里程碑前不再"重新评估", 让 M-A/M-B/K-3 走完才再纠偏 (避免 Planner 疲劳累积)
- **+ Generator 之间互检前置** — 这次 A 写 Karpathy → B review 是好模式, 应该写进协作文档 §7 让 milestone 计划都走 A 写 → B review → 顾源源批准, 减少 Planner 临时拉群

---

### 异议 5 · §5 协作 — 补充协作延迟周期审视

A 7 维度评估 §5 ✅ "A/B/C 三模式都在用", 补 "v2 计划缺 B review".

**B 印证 + 补充新维度**:

Karpathy §5 视角看协作健康度, 应该看**延迟周期**:

| 决策点 | 5/22 实际延迟 | 评估 |
|---|---|---|
| 顾源源 → A 接力 sync 指令 | ~5-15 min (顾源源主动) | 🟢 极短 |
| A 产物 → B 接力 sync | ~5-10 min (A 主动发 sync) | 🟢 极短 |
| B 产物 → 顾源源决策 | ~10-30 min (顾源源 review) | 🟢 短 |
| 决策点 → 下一里程碑启动 | ~5-30 min | 🟢 短 |

**Karpathy 视角**: 周期短 = Planner 必须强 (§4). 5/22 顾源源全天主动 = 健康但**对 Planner 依赖过强**.

**风险**: 顾源源 5/23/24 不主动指令 → Generator A/B 进入"等指令"状态. 长任务 harness 应该有"Generator 自己生成下一里程碑" 兜底.

**B 建议**: V2.1_AI_COLLABORATION.md §6 加一条 — Generator 完成一个里程碑后, **自动写出"下一里程碑提案"** (不等 Planner 主动 sync), Planner 用 30 秒批准就能继续.

---

## 3 · §7 反检查清单补 Q5/Q6/Q7

A 已经加 Q5 (eval 对象对). B 补 Q6 + Q7 候选:

| Q | Karpathy 视角 | 触发场景 |
|---|---|---|
| Q1 | §3 有 eval dataset 吗? | 改 prompt 前 |
| Q2 | §1 三层架构共存吗? | 设计新功能时 |
| Q3 | §4 三角色齐吗? | 启动长任务前 |
| Q4 | §6 过度约束已拆吗? | 卡住时 |
| Q5 (A 加) | §3+§4 eval 对象对吗? | dogfood 出数字时 |
| **Q6 (B 新)** | §1 大架构对了但**具体调用点错层吗**? | 写新写入路径时 (smart_file_import 反例) |
| **Q7 (B 新)** | §5 协作**是否过度依赖 Planner 主动**? | 长任务跨 session 时 |

---

## 4 · 必答 4 个核心问题 (K-3 sync 指令)

### Q1 · A AI 提的 K-1 (eval 对象重对齐) 对吗?

**B 答**: ✅ **印证 + 修正**.

eval 对象改为 6 段叙事最终输出是对的. **但漏了 L1 层**:
- L1 = atomic_facts 抽取层 eval (LLM extractor 抽的 fact 对不对)
- L2 = 6 段叙事拼合层 eval (collector + generator 拼的对不对)

只测 L2 会**掩盖 L1**: collector 漏拉 vs LLM 抽漏, 两种 bug 都让 L2 命中低, 不分.

**B 提议 K-1 升级**: 双层 eval, **L1 + L2 同时跑**, baseline runner 出 2 个 P% 数字.

---

### Q2 · A 提的 K-2 (Evaluator 自动化) 优先级?

**B 答**: 🔴 **强烈反对 "V2.2 完成后" — 应该立刻做**.

理由: A 阶段 2 改 collector 迭代时不能没 evaluator, 否则跟 5/22 早上 B 自测 87% 同一类错误. 0.5 天工作量, 立刻接入 M-C 一起做.

---

### Q3 · A 提的 3 个过度约束哪个该拆?

**B 答**:

1. **V2.1 双 app 同跑**: 同意 A 选项 c (折中保留 V2.1 lab 作实验场, M-A 直接在主仓库改). **再加一条**: V2.1 lab README 明确写"我自己的实验沙盒, 不是 A/B 同比".

2. **4 路径全接通**: 🔴 **不全同意 A**. 路径 3/4 留 V2.3 OK, 但**路径 2 (任务复盘) 必须 V2.2 通**. 否则目标 c (跨源印证) 永远 0%, V2.2 N2 不能 PASS. 数据齐 (weekly_reviews 9 + meetings 7 + commitments 66), 工作量小 (1-2 天).

3. **文档过载**: 🟡 不是过度, 是产出率信号. archive ✅ + 收敛纠偏频次 + Generator 互检前置.

---

### Q4 · B 视角有没有 A 漏掉的维度?

**B 答**: 5 处 (见 §2):

1. **§1 错层反例** — smart_file_import.py:1002 直接 INSERT atomic_facts 是 1.0 写架构, 错层
2. **§2 OS 类比补 interrupt** — broadcast_data_changed = interrupt signal, A 漏在 OS 类比表
3. **§3 eval 对象升级双层** — L1 atomic_facts + L2 6 段, 单 L2 掩盖 L1
4. **§5 协作延迟周期** — Planner 主动间隔健康但依赖过强, 应让 Generator 自动写下一里程碑提案
5. **§7 补 Q6 (具体调用点错层) + Q7 (Planner 依赖过强)**

---

## 5 · 综合判决

### 5.1 A/B 双 Karpathy 评估一致点 (顾源源决策依据)

| 一致点 | A | B | 真信号 |
|---|---|---|---|
| atomic_facts 100% update_relation='none' (跨源信息商 0 触发) | ✅ | ✅ | ★ 已 100% 印证 |
| N3 8-9 张核心表 0 行 (syslog 没启用) | ✅ | ✅ | ★ |
| Evaluator 是手动的, 不是自动的 | ✅ | ✅ | ★ |
| eval 对象错了 (B baseline 87% vs dogfood 1/7) | ✅ | ✅ | ★ B 已承认 |
| §1 三层架构大方向对 | ✅ | ✅ | ★ (但 B 指出具体调用点错层) |
| §5 协作 3 模式都用 | ✅ | ✅ | ★ |
| V2.1 双 app 选项 c (折中保留) | ✅ | ✅ | ★ |
| 路径 3/4 留 V2.3 | ✅ | ✅ | ★ |

### 5.2 A/B 异议点 (顾源源需要拍板)

| 异议点 | A | B | 建议拍板方向 |
|---|---|---|---|
| K-2 Evaluator 自动化优先级 | V2.2 后 | 立刻做 (跟 M-C 同步) | **B 视角** (工作量 0.5 天, 不阻塞) |
| 路径 2 (任务复盘) V2.2 通还是 V2.3? | V2.3 | **V2.2 必须通** | **B 视角** (目标 c 不通则 N2 不能 PASS) |
| K-1 eval 对象 (单 L2 还是 L1+L2)? | 单 L2 | **L1 + L2 双层** | **B 视角** (避免掩盖) |
| §1 三层架构 100% 通过 vs 有错层 | 100% 通过 | 有错层 (smart_file_import:1002) | **B 视角** (具体反例) |

### 5.3 最终评分 (B 视角加 7 维度 = 49 项)

```
§1 三层架构:           ███░░░░░░░ 30% (有错层反例)  ← B 比 A 严
§2 LLM as OS:          ███░░░░░░░ 30% (syslog 0 流量) ← 跟 A 同
§3 Eval-Driven:        ██░░░░░░░░ 20% (1 dataset + 错对象, 还缺 L1 层) ← 跟 A 同
§4 三角色:             ██████░░░░ 60% (Evaluator 弱, 但本 B review = 弥补 §5) ← 比 A 略低
§5 协作模式:           █████████░ 90% (3 模式都用, B review 进行中) ← 跟 A 同
§6 Unhobbled:          ████░░░░░░ 40% (3 候选 + B 加路径 2 该 V2.2 通) ← 跟 A 同
§7 反检查 + Q5/Q6/Q7:  ████████░░ 80% (5 题 → 7 题) ← 比 A 严

B 综合分: 50% (A 是 85%)
```

**为什么 B 比 A 严**: B 在具体调用点 (smart_file_import:1002) + 具体 dataset 缺陷 (单 L2) + 协作 Planner 依赖 上找到具体反例, 整体大方向同意但执行细节有 gap.

**给顾源源决策建议**:
- **A 评估**作为方向参考 (85% 通过率)
- **B 异议 4 条**作为细化建议 (路径 2 必通 / Evaluator 立刻 / 双层 eval / 错层反例)

---

## 6 · 我承认 / 我没承认 (透明)

### 我承认

1. ✅ A AI 关键事实 9/9 印证 (atomic_facts + N3 8 表)
2. ✅ A AI 7 维度大方向判断对 (85% 通过率合理)
3. ✅ B 自己 5/22 87% baseline 是错对象, A 提的 K-1 对
4. ✅ V2.1 双 app 选项 c, 路径 3/4 留 V2.3 — 跟 A 一致

### 我没承认 / 反对

1. 🔴 A "Evaluator V2.2 完成后做" — 应立刻 (异议 2)
2. 🔴 A "路径 2 留 V2.3" — V2.2 必须通 (异议 3)
3. ⚠️ A "§1 三层架构 100% 通过" — 有错层反例 (异议 1)
4. ⚠️ A "K-1 改测 6 段输出" — 应双层 L1+L2 (异议 4)
5. ⚠️ A "v2 计划缺 B review" 已部分解 — 但**协作还有 Planner 依赖过强**风险 (异议 5)

---

## 7 · 我推荐的下一步 (跟 sync 指令对齐)

按 sync 指令 §四 协作时间表:

T+0   ★ 本文 commit (K-3 完成)
T+5   M-A broadcast 接通 commit (A 已在 e1d8fa8)
T+15  顾源源拿 A 评估 (c427d18) + B review (本文) 决策:
        - 是否吸收 B 4 条异议
        - K-1 是否升级双层 eval
        - 路径 2 是否进 V2.2
        - K-2 是否立刻接 M-C

之后:
- 如顾源源采纳 B 异议 2 (K-2 立刻) → A 改 collector 同步加 auto-eval
- 如采纳 B 异议 3 (路径 2 V2.2) → M-B 加路径 2 (估 1-2 天工作量)
- 如采纳 B 异议 4 (双层 eval) → K-1 升级
- 如不采纳 → 按 A v2 计划走

不阻塞任何东西. B 继续按 §阶段 1-5 sync 指令走.

---

**Author**: B AI · 2026-05-22 · K-3 独立 review
**附**: A AI 5/22 22:30 Karpathy 评估 (c427d18) 印证 9/9 数据事实 + 大方向 85% 同意 + 4 处异议待顾源源拍板
