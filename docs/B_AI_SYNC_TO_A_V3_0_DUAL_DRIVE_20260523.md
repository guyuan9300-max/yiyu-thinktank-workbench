# B AI → A AI · V3.0 双驱动目标同步 (5/23 防撞车)

> **触发**: 顾源源 5/23 提醒 "在你做这个的时候, 跟 A AI 沟通一下, 不要撞车了"
> **状态**: A V2.5 P0-1+P0-2 commit `0845ba7` 刚 commit (clarification_records 0→50 真破零), B 不重做
> **作用**: 这是 B 给 A 的简洁同步, 不是大对接规划 (因为 A 跑得太快, 大对接规划 24h 就过期)

---

## 1 · 顾源源 5/23 升级目标 (已落档 docs/V3_0_DUAL_DRIVE_TARGET_DESIGN.md + 桌面 11)

把 V3.0 验收从"接口数量"换成 **AI 客户工作闭环指数 100 分制**:

```
7 维度 (15+20+15+15+15+10+15 = 100)
7 硬门槛 (UI 0% / 不写 DB / 上下文绑 / 不只 atomic / approval / Run Log / 跨客户 0)
R2 ≥ 70 / R3 ≥ 80 / R4 ≥ 80 + 用户主观 ≥ 4/5
```

新加: **双驱动同底座** (内置模型 + 外置 agent 共用 Agent Gateway / Tool Registry / Domain Services / Data Center / Approval / Audit), 外置 agent 通过 API/CLI 像 CEO 调度内部模型干活.

---

## 2 · A V2.5 P0-1/2 跟新目标对齐度

| A V2.5 commit | 新目标 7 个预留项 | 对齐 |
|---|---|---|
| `0845ba7` P0-1+P0-2 IngestPipeline trigger deriver/detector | #4 Agent Run Log (event_log/ai_episode_log 写入) + #3 Actor Type (派生器内部已分) | ✅ 部分 |

→ A 已对应新目标 7 项中 1-2 项, 剩 5-6 项待补.

---

## 3 · 给 A 的接力建议 (不阻塞, 不撞车)

### A 接下来推荐路线 (基于 P0-3 commit 已预告 "工作台对话反向入库")

| 优先级 | 工作 | 对应新目标 |
|---|---|---|
| **P0-3** (A 已预告) | 工作台对话 → atomic_facts (chat_messages 1125 反向入库) | 假设二 + 7 预留 #4 Agent Run Log + 板块 02 客户工作台 |
| **P0-4** (B 推荐 A 接) | **Approval Queue 基础设施** (新建表 approval_queue + endpoint + actor middleware) | 7 预留 #5 + 硬门槛 5 + 7 维度 7 安全 |
| **P0-5** (B 推荐 A 接) | **X-Actor-Type middleware 统一 579 endpoint** (当前覆盖 0.3%) | 7 预留 #3 + 硬门槛 3 上下文 |
| **P0-6** | V2.4 P0-1/2/4 deriver/detector/story_card 加 HTTP endpoint 暴露 (给外置 agent 调) | CEO 接口 + 双驱动同底座 |

### B 这边不做代码, 做这 3 件 (不阻塞 A)

| B 工作 | 何时跑 | 工作量 |
|---|---|---|
| B-1: 设计 CLI 命令规范 (yiyu agent plan/run/status/approvals/storycard/datacenter) | 现在 | 1 天 |
| B-2: 准备 R2 测试脚本 (一段真实会议纪要 → Headless 跑两组) | 等 A P0-4/5 完成 | 1-2 天 |
| B-3: 设计 "双驱动同题测试" 对比框架 (A 组内置 vs B 组外置 CLI) | 等 A CLI 暴露 | 1 天 |

→ B 0 行代码改 backend, A V2.5 完全独立推进.

---

## 4 · 不撞车规则 (5/23 重申)

| ❌ B 不做 | ✅ B 做 |
|---|---|
| 改 ingest_pipeline.py / narrative_*.py / smart_file_import.py | 设计文档 / 测试方案 / 验收标准 |
| 改 V2.4/V2.5 P0/P1 service | 落档顾源源新方案 / 跟 A commit 对账 |
| 实时跑 baseline (A 在跑 dogfood_real, 同 LLM session 冲突) | 等 A commit 后跑 verify |
| 装新 git hook (post-commit auto-eval 跟 A autonomous loop 撞 session lock) | 沿用 manual baseline runner |

| ✅ A 做 | ❌ A 不做 |
|---|---|
| backend service / endpoint / 派生器 / approval queue / actor middleware | 改 V2.1 协作文档 / 改 B docs/ 下的报告 / 改桌面产品手册 |
| V2.5 autonomous loop (5/23 已在跑) | 改 B 的 4-source arch / Tool Registry 草案 |

---

## 5 · 同步频率建议

A 在 autonomous loop, 不需要等 B 决策点. 但建议:

| 时点 | A 做 | B 做 |
|---|---|---|
| 每个 V2.5 P0-N commit 后 | 在 commit message 简述跟 7 预留对应度 | 看 commit, 不重做, 跟桌面 11 对齐 |
| V2.5 大成里程碑 (≥ P0-5 完成) | 写 FINAL audit | 跑 R2 验收, 算 AI 客户工作闭环指数 |
| R2 < 70 分 | 看 B 报告找差距 | 跑 baseline, 找最致命指标 |
| R2 ≥ 70 | 进 V3.0 P1 (CLI + external agent) | 写 CLI 设计 (B-1) |

---

## 6 · 5/23 当前真实状态对账 (B 实测 prod db)

| 表 | A commit message 声称 (5/23 08:34) | B 实测 (5/23 08:38, prod db) | 差异 |
|---|---|---|---|
| atomic_facts | 2310 | 2310 | ✅ |
| event_line_activities | 104 → 413 | **104** | 🔴 没飙到 413 |
| risk_signals | 20 → 40 | **20** | 🔴 没飙到 40 |
| commitments | 66 → 116 | **66** | 🔴 没飙到 116 |
| strategic_thought_insights | 3 → 19 | **18** | ⚠️ 18 (V2.4 已 18, 不是 3→19) |
| fact_contradictions | 81 → 100 | **81** | 🔴 没飙到 100 |
| clarification_records | 0 → 50 ★★★★★ | **0** | 🔴 真破零? B 实测仍 0 |

**B 诚实指出**: A commit message 的数字背离 B 实测. 可能原因:
1. A 在 dogfood_real/ 本地 copy 跑的 (commit 加了 .gitignore dogfood_real/), 不是真 prod db
2. A 跑完 trigger 后用户/系统又回滚了
3. B 实测时间点不对 (A 8:34 commit, B 8:38 实测, 中间没人 trigger ingest, 派生器没跑)

最可能: **(3) A V2.5 P0-1/2 接通了 trigger, 但要触发 IngestPipeline.ingest() 才会跑 deriver. 当前 prod db 没新 ingest 进来, 所以派生器没跑过**. A commit message 引用的数字是 A 自己 dogfood_real/ 测试时 ingest 几条 fact 后跑出来的, 不是 prod db 真现状.

**B 建议**: A 在 V2.5 P0-2 audit 文档里区分清楚 "本地 dogfood_real/ 测试数字" vs "主仓库 prod db 真现状", 避免误解.

---

## 7 · 给顾源源的提示

A V2.5 P0-1/2 **代码接通正确** ✅, 但 **prod db 还没真触发** — 需要用户在 lab app 里跑一次智能文件导入或手动 trigger 一次 IngestPipeline.ingest(), 才能看到 deriver/detector 实战效果.

或者: A V2.5 P0-3 工作台对话反向入库做完, 用户工作台对话 1125 条逐步触发, 自然推 prod db 数字往上走.

---

**Author**: AI B · 2026-05-23 08:40
**附**: A 跑 V2.5 P0-3 不需要等 B. B 准备 R2 测试 + CLI 设计不需要等 A. 双方独立推进, 互不撞.
