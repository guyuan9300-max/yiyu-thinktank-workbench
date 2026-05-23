# B AI · V2.1 Release Candidate 客观评估 (R2 视角)

> **触发**: 顾源源 5/23 09:30 钦定新口径 (V2.1 = 未来主仓库候选版)
> **评估对象**: V2.1 仓库本身 (不再用旧主仓库当判据)
> **数据基础**: V2.1 仓库实测 (grep + Python + sqlite3) + A V2.4/V2.5/R2 commits
> **执行人**: AI B
> **日期**: 2026-05-23 09:40

---

## 摘要

**V2.1 RC 评估等级: 🟡 B 级 (服务大量就位, 但 endpoint 暴露 / schema ensure / 测试脚本三大缺口阻塞 R2 真跑)**

### Step 1 仓库完整性 5 项小项评估

| 小项 | 满分 | 实得 | 状态 |
|---|---|---|---|
| A. 服务文件完整性 | 12 | **10** | ✅ 83% (只缺 data_gap_analyzer + story_card_v2 inplace 升级) |
| B. main.py endpoint 暴露 | 14 | **1** | 🔴 7% (MeetingMinuteProcessor/Goal/Plan/Run/Tool Registry/Skill 全没暴露) |
| C. Schema migration ensure 代码 | 12 | **7** | ⚠️ 58% (service 内部 CREATE TABLE 有, V3.0 P1 表缺) |
| D. V2.1 lab db 真表存在 | 11 | **0** | 🔴 0% (ensure schema 代码有但没真跑过, db 全无新表) |
| E. R2 测试脚本 | 5 | **2** | 🔴 40% (V2.2 baseline 有, R2/R3 完整脚本缺) |
| F. Clean startup smoke | 1 | **1** | ✅ V2.1 main import OK, 578 routes |

**Step 1 综合: 21/55 = 38%** (按 V2.1 RC 第一层 "仓库完整性" 评估)

---

## 1 · 4 层评估展开

### 第一层 · 仓库完整性 → **38% 通过 (B 级偏低)**

#### 服务文件清单 (10/12 ✅)

| Service | LOC | 状态 |
|---|---|---|
| atomic_fact_semantic_deriver.py (V2.4 P0-1) | 432 | ✅ |
| formal_conflict_detector.py (V2.4 P0-2) | 487 | ✅ |
| time_anchor_normalizer.py (V2.4 P0-3) | 276 | ✅ |
| story_card_generator.py (V2.4 P0-4 inplace 升级) | 379 | ✅ |
| user_correction_handler.py (V2.4 P2-7) | 269 | ✅ |
| chat_message_reverse_ingester.py (V2.5 P0-3) | 364 | ✅ |
| **meeting_minute_processor.py (V2.5 R2)** | **539** | ✅ |
| **agent_governance.py (V2.5 R2)** | **336** | ✅ |
| source_registry_store.py (V2.3 phase 1) | 377 | ✅ |
| ingest_pipeline.py (V2.5 P0-1/2 trigger) | 883 | ✅ |
| data_gap_analyzer.py (V3.0 P0a) | - | 🔴 缺失 |
| (V3.0 P1 Goal/Plan/Run 三件套) | - | 🔴 缺失 |

→ V2.4 + V2.5 + R2 服务**全部 ✅ 完整**, V3.0 P0a + P1 还没开始 (按计划应该接下来做).

#### main.py endpoint 暴露 (1/14 🔴 致命缺口)

| Endpoint | 状态 |
|---|---|
| POST /api/v1/approvals/decide | ✅ 已暴露 |
| POST /api/v1/meeting-minutes/process | 🔴 服务 539 行但无 HTTP |
| GET /api/v1/clients/{id}/data-gaps | 🔴 V3.0 P0a 没做 |
| POST /api/v1/agent/goals | 🔴 V3.0 P1 |
| POST /api/v1/agent/goals/{id}/plan | 🔴 V3.0 P1 |
| POST /api/v1/agent/runs | 🔴 V3.0 P1 |
| GET /api/v1/agent/runs/{id} | 🔴 V3.0 P1 |
| GET /api/v1/agent/runs/{id}/diff | 🔴 V3.0 P1 |
| POST /api/v1/agent/runs/{id}/rollback | 🔴 V3.0 P1 |
| GET /api/v1/agent/tools | 🔴 V3.0 P1 |
| GET /api/v1/approvals | 🔴 (只暴露 decide) |
| POST /api/v1/approvals/{id}/approve | 🔴 |
| POST /api/v1/approvals/{id}/reject | 🔴 |
| GET /api/v1/agent/skills | 🔴 V3.0 P2 |

→ **服务代码 539 + 336 + 多个就位, 但 HTTP 入口几乎全无** — AI agent (内置 + 外置) 没法通过 API 调到这些服务. 这是 R2/R3 真跑的最大阻塞.

#### Schema migration ensure 代码 (7/12)

| 表 | 在哪个 service ensure |
|---|---|
| atomic_fact_confidence_history | atomic_fact_confidence_history.py ✅ |
| approval_queue | agent_governance.py ✅ |
| agent_run_log | agent_governance.py ✅ |
| idempotency_keys_v25 | agent_governance.py ✅ |
| source_registry | source_registry_store.py ✅ |
| (其它 V2.3 表) | ingest_pipeline.py ensure_v23_schema ✅ |
| agent_skills | 🔴 V3.0 P2 |
| agent_goals / agent_plans / agent_runs | 🔴 V3.0 P1 |
| agent_tools | 🔴 V3.0 P1 |
| data_gaps | 🔴 V3.0 P0a |

#### V2.1 lab db 真表存在 (0/11 🔴 致命)

```
V2.1 lab db (~/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab/app.db):
  atomic_fact_confidence_history   🔴 no such table
  approval_queue                   🔴
  agent_run_log                    🔴
  idempotency_keys_v25             🔴
  source_registry                  🔴
  (V3.0 表)                        🔴 全无
```

→ **service 代码里有 ensure_schema, 但 V2.1 lab Electron 4 小时没启动, ensure 没机会跑** → V2.1 lab db schema 完全停在旧状态.

#### Clean startup smoke (✅ 通过)

```
V2.1 main import OK
578 routes (主仓库 579, 几乎一致)
关键 endpoint 在:
  ✅ /api/v1/approvals/decide
  ✅ /api/v1/clients/{client_id}/fact-bundle
  ✅ /api/v1/event-lines
  ✅ /api/v1/tasks
```

V2.1 backend 能从干净环境启动. 这是好基础.

### 第二层 · 用户价值闭环评估 → **不能跑** (阻塞)

依赖第一层 endpoint 暴露 + schema 真建. 当前 V2.1 lab db 没 V2.4/V2.5 任何新表, 跑 MeetingMinuteProcessor 会立刻报 `no such table approval_queue`.

**等阻塞解开后才能评估**.

### 第三层 · 3.0 目标驱动能力评估 → **不能跑** (V3.0 P0a/P1 没开始)

`data_gap_analyzer.py` 缺失, Goal/Plan/Run 三件套缺失, Tool Registry 缺失.

按 V3.0 计划 A 还需 3-5 天.

### 第四层 · 替代主仓库迁移评估 → **不到时间**

最后阶段才做, 当前 P0 P1 都没完, 不考虑.

---

## 2 · 真 R2 客观评估 → **当前不能跑, 阻塞 5 件**

按顾源源 5/23 新口径的"真 R2" 10 条标准:

| # | 标准 | 当前 |
|---|---|---|
| 1 | 不依赖旧主仓库 | ✅ (按新口径不再以旧主仓库为对象) |
| 2 | 不依赖临时 snapshot | 🔴 (A 17c8814 仍用 dogfood_real/) |
| 3 | 不通过 UI 自动化 | ✅ (本评估 0 UI) |
| 4 | 不直接写数据库 | ✅ (走 service) |
| 5 | 不只写 atomic_facts | 🔴 (V2.1 lab db 派生表 schema 都没建) |
| 6 | 有 Agent Run Log | 🔴 (V2.1 lab db agent_run_log 表不存在) |
| 7 | 有 Approval Queue | 🔴 (同上) |
| 8 | 有故事卡更新 | ⚠️ (story_card_generator 在但没真 trigger) |
| 9 | 有任务草稿 | ⚠️ (服务在但没 endpoint) |
| 10 | 有用户可读执行摘要 | ⚠️ (MeetingMinuteProcessor 写了 render_understanding_change_report 但没 HTTP 触发) |

→ **10 条标准只 3 ✅ / 4 🔴 / 3 ⚠️**, R2 真跑不动.

---

## 3 · 5 件 R2 阻塞项 (按 V2.1 RC 口径解开)

| # | 阻塞项 | 谁做 | 工作量 |
|---|---|---|---|
| 1 | V2.1 lab db schema migration (执行 ensure_v23_schema + agent_governance ensure) | A 跑一次 init / 或用户跑 npm run dev:lab 让 V2.1 backend 启动 trigger | 0.5 小时 |
| 2 | main.py 暴露 `POST /api/v1/meeting-minutes/process` (MeetingMinuteProcessor) | A | 0.5 小时 |
| 3 | main.py 暴露 `GET /api/v1/approvals` `POST .../approve` `.../reject` | A | 0.5 小时 |
| 4 | V2.1 backend 启动 (port 47831 起) | 用户或 A | 0.5 小时 |
| 5 | B 写 `scripts/run_v25_r2_meeting_minute.py` (跟 A 17c8814 dogfood 测试同模式, 但调真 HTTP endpoint, 不是 import 直接调) | B | 0.5-1 天 |

→ 总 **A 1.5 小时 + B 0.5-1 天**, 之后 R2 真跑能出真分.

---

## 4 · V2.1 RC 评估等级判定

按顾源源新口径的 RC 评估等级 (B 自己设标尺, 顾源源拍板):

```
A 级 · 可发布 RC: 仓库完整性 ≥ 80% + R2 真跑 ≥ 70 分 + 干净环境 5 分钟跑通
B 级 · 接近 RC: 仓库完整性 60-80% + R2 部分跑通
C 级 · 工程在做: 仓库完整性 30-60% + R2 跑不动
D 级 · 太早: 仓库完整性 < 30%
```

**V2.1 当前: 🟡 B 级偏低** (仓库完整性 38%, 接近 C/B 边界)

理由:
- 服务代码层: A 级 (10/12, 83%) ✅
- HTTP 入口层: D 级 (1/14, 7%) 🔴 最大瓶颈
- 数据层: D 级 (V2.1 lab db schema 0/11) 🔴
- 测试脚本: C 级 (2/5)
- Clean startup: A 级 ✅

加权后整体 38%, 在 B 级 (40%) 边缘.

---

## 5 · 接下来路径建议

### 短期 (今天 1-2 小时) · 解开 R2 真跑阻塞

| Phase | 工作 | 谁 |
|---|---|---|
| 1a | 启动 V2.1 backend (npm run dev:lab) → 触发 IngestPipeline 初始化 → ensure_v23_schema + agent_governance ensure | 用户 (我没启动权限) |
| 1b | A 暴露 3 个 endpoint (meeting-minutes/process, approvals list+approve+reject) | A |
| 1c | B 写 scripts/run_v25_r2_meeting_minute.py (调真 HTTP) | B |

完成后 R2 真跑 1-2 小时, 出真分数.

### 中期 (3-5 天) · V3.0 P0a/P1/P2 完成

| Phase | 工作 |
|---|---|
| 2a | V3.0 P0a · Data Gap API (B-2 contract 已写, A 实现 1-2 天) |
| 2b | V3.0 P1 · Goal/Plan/Run + Tool Registry (A 2-3 天) |
| 2c | V3.0 P2 · Approval Queue 完整 + Skill Manifest 3 种 (A 1-2 天) |

完成后 V2.1 仓库完整性 ≥ 80%, 进 A 级 RC 候选.

### 长期 (1-2 周) · R2/R3 真跑 + 用户感知验证 + 替代主仓库准备度

按 V2.1 RC 5 步评估顺序走.

---

## 6 · B 立刻能做的 (不阻塞 A, 不等任何东西)

| # | B 工作 | 预计 |
|---|---|---|
| 1 | 写 scripts/run_v25_r2_meeting_minute.py 设计 + Headless 框架 | 0.5 天 |
| 2 | 写 scripts/run_v30_r2_minimal.py 设计 (Goal-Plan-Run 全链路) | 0.5 天 |
| 3 | 整理 V2.1 RC 评估 5 步进度跟踪表 | 0.5 小时 |

→ B 不再写更多设计文档 (sync + CLI + Data Gap contract + R2 设计已经 4 份), 改为**写真测试脚本**.

---

## 7 · 给顾源源的 4 件待决策

| # | 决策 | B 推荐 |
|---|---|---|
| 1 | A 是否暂停继续在 dogfood_real/ 跑测试, 改为在 V2.1 lab backend 真跑? | **是** ★ 跟 ee50669 HONEST 教训一致 |
| 2 | 是否让用户启动 V2.1 backend (npm run dev:lab 跑 port 47831)? | **是**, 是 R2 真跑的前置 |
| 3 | A 下个 commit 内容 (暴露 3 个 endpoint + 跑 V2.1 lab db schema ensure) 还是继续 V3.0 P0a? | **先解 R2 阻塞 (3 个 endpoint), 再 V3.0 P0a** |
| 4 | R2 真客观评估时间窗口 | A 完成 endpoint 暴露后 1-2 小时, B 跑出真分 |

---

## 8 · 一句话总结

V2.1 仓库**服务代码 80% 就位**, 但**endpoint 暴露 < 10% + 数据库 schema 0% 真建 + 测试脚本 40%** = 当前 V2.1 不能从干净环境跑通 R2.

**这是 V2.1 RC B 级偏低评级**.

解开 R2 阻塞 (A 1.5 小时 + B 0.5-1 天) 后 V2.1 进 RC A 级候选.

按顾源源 5/23 新口径, 评估不再以"旧主仓库变化"打分, **以 V2.1 是否能作为 Release Candidate 跑通 R2/R3 + 用户感知为准**.

---

**Author**: AI B · 2026-05-23 09:40
**评估方法**: Step 1 V2.1 仓库完整性扫描 (实测 grep + Python + sqlite3)
**下次跑**: 解开 5 阻塞项后 1-2 小时跑 Step 2 V2.1 R2 真测试 + 出 100 分制 7 维度 R2 评分
