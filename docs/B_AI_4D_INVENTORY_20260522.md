# B AI · 4 维度全盘盘点 (顾源源 5/22 钦定流程)

> **触发**: 顾源源 5/22 钦定流程 — 每个里程碑结束必跑
> **执行人**: AI B (独立跑一遍, 不依赖 A 的 4D evaluation)
> **日期**: 2026-05-22
> **目的**: 防"上下文衰减后凭想象设计", 用真实事实 (行数 / 字段 / commit / 表名) 建立判断

---

## 维度 1 · 软件功能架构 (产品手册 9 份 docx)

数据源: `docs/V2.2_PRODUCT_MANUAL_FULL_TEXT.md` (A 抓的镜像 56KB) ←
桌面 `~/Desktop/益语智库 2.0 产品手册/` 9 份 docx 原文.

### 1.1 软件骨架 (顾源源亲手定义, 不可改)

```
顶部主导航 5 个 tab:
  1. 任务与日程 (01)
  2. 工作台 / 客户工作台 (02)
  3. 战略陪伴 (03) ← 6 段叙事 + AI 主动研判 + 事实澄清
  4. 资讯情报站 (04)
  5. 成长中心 (05)

底部账户区辅助入口 2 个:
  6. 组织计划工坊 (08 上半)
  7. 系统设置 (08 下半)

工具页 / 重点新功能:
  8. 智能文件导入 (06) — 在客户工作台工具页打开

底层基础设施 (用户不直接进):
  9. 数据中心 (07) — 所有板块的事实层
```

### 1.2 战略陪伴 §03 钦定 6 段叙事 (重要核心)

```
essence       (本质)        : 这个客户到底是干什么的, 核心定位
cooperation   (合作)        : 跟我们的合作历史 + 协作模式
business_intro(业务介绍)    : 他们的核心业务 / 产品 / 服务
people        (人物)        : 关键人物 + 角色
timeline      (时间线)      : 关键事件按时间排序
next_steps    (下一步)      : AI 建议接下来该做什么
```

每段带"把握度" (high/medium/low). 战略陪伴页顶部有 **"让 AI 重新理解"按钮**作为兜底刷新入口.

### 1.3 设计哲学 (4 条)

| # | 哲学 | B 视角验证 |
|---|---|---|
| 1 | 数据中心是地基, 所有板块都长在它上面 | ✅ 跟 IngestPipeline 4 路径设计一致 |
| 2 | 用户讲故事 + AI 整理, 不要反过来 | ⚠️ smart_file_import 体现了, 但其它路径未必 |
| 3 | 每个板块都有"兜底入口"(让 AI 重新理解 / 重新触发) | ⚠️ 战略陪伴有按钮, 其它板块未必 |
| 4 | 表面平等 + 后台分级 (CEO 权重 + 顾源源说的"显性平等隐性秩序") | 跟 memory: [[project_yiyu_surface_equality]] 完全对齐 |

### 1.4 用户感受到的 N1/N2/N3 对照

```
N1 (现有功能不掉链): 9 板块全部能跑, 用户日常工作不被打断
N2 (机器人能拿全数据流畅回答): 战略陪伴 6 段 + 工作台 AI 对话引用具体段落
N3 (3.0 接入预留): 产品手册 §00 "对未来 3.0 的方向" 提到了"智能公司预置 AI 团队"
```

---

## 维度 2 · 软件代码结构 (主仓库)

数据源: `~/openclaw/workspace/yiyu-thinktank-workbench/`

### 2.1 总览规模

```
backend/         Python FastAPI
backend/app/main.py             54,885 行 ← 单文件巨大, 27000+ endpoint 闭包
backend/app/services/           175 个 *.py
backend/app/models.py            9,193 行
backend/app/db.py                5,154 行 (schema 定义)
backend/app/services/ai.py       5,550 行 (LLM 调用)
backend/app/services/knowledge_v2.py 5,174 行
backend/app/services/growth_engine.py 4,870 行
backend/app/services/knowledge_base.py 4,391 行
backend/app/services/analysis_center.py 3,984 行

合计 backend: ~190,000 行

cloud_backend/   独立云端 (火山云部署), 含独立 schema
src/renderer/    Electron React 前端
mobile/          独立手机端代码
docs/            产品文档
tests/           E2E 测试
qa/              手工测试
```

### 2.2 跟产品手册 9 板块的代码映射 (前端 .tsx 数量)

| # | 板块 | 前端目录 | .tsx 数 | 主仓库代码量 |
|---|---|---|---|---|
| 01 | 任务与日程 | `src/renderer/components/tasks/` | 17 | 大 |
| 02 | 客户工作台 | `src/renderer/components/client_workspace/` | 8 | 中 |
| 03 | 战略陪伴 | `src/renderer/components/strategic_accompaniment/` | 4 (NarrativePanel 是核心) | 大 |
| 04 | 资讯情报站 | `src/renderer/components/intelligence/` | 1 | 中 (`intelligence_candidate_supply.py` 7111 行) |
| 05 | 成长中心 | `src/renderer/components/growth/` | 1 | 中 (`growth_engine.py` 4870 行) |
| 06 | 智能文件导入 | `src/renderer/components/smart_file_import/` | 1 | 中 (`smart_file_import.py` 大) |
| 07 | 数据中心 | `src/renderer/components/data_center/` | 4 | 极大 (knowledge_v2 + memory_foundation + workspace_data_center_adapter ~12000 行) |
| 08 | 组织计划工坊 | `src/renderer/components/plan_workshop/` | 1 | 小 |
| 系统设置 | `src/renderer/components/settings/` | 10 | 大 |

### 2.3 N2 6 段叙事关键服务 (新计划 §0)

```
backend/app/services/narrative_generator.py   1,156 行 — 主仓库已实现 6 段叙事 + 调本地 AiService
backend/app/services/narrative_collector.py   1,192 行 — 拉 13 张现成表喂 generator
```

这两个 = N2 真核心. V2.1 NarrativeKernel 已废 (跟它重复造轮子).

### 2.4 4 主路径 (V2.2 IngestPipeline 设计) 在主仓库的现状

| 路径 | 主仓库代码状态 | 接通度 |
|---|---|---|
| workbench_file (工作台文件) | `smart_file_import.py` + `document_llm_extractor.py` | 接 IngestPipeline (B F2.1 试过) |
| task_review (任务复盘) | `weekly_review_*.py` 多个服务 + tasks 表 | normalizer 有, 没绑数据源 |
| internet_crawler (爬虫) | `internet_crawler.py` + `wechat_sogou_ingest.py` 全套 | 写 v2_documents, 不进 atomic_facts |
| mobile_ai_chat (手机聊天) | `chat_threads` / `chat_messages` 表存在 | 0 写入路径 |

→ **跟 A 4D §1.2 + B 自检报告 §三 完全一致: 4 路径只 1 路通**

---

## 维度 3 · 数据库表 (真实 prod db)

数据源: `~/Library/Application Support/YiyuThinkTankWorkbench2/app.db`

### 3.1 表总数

**217 张表** (A 盘点 §1 写 208, 我跑实测 217 — 差 9 张可能是 V2.2 phase 1 期间 A 新加 schema 后增长)

### 3.2 11 组业务模块行数 (实测验证 A 盘点)

```
A 客户/组织/人员       — clients 12 / entities 4987 ✓ (1,301 行总, 跟 A 一致)
B 文档/文件/导入       — (跟 A 一致, 30,726)
C 任务/计划/复盘/承诺  — tasks 238 / commitments 66 / weekly_reviews 9 / decisions 3 (1,544 总)
D 事件线/活动/吞入     — event_lines 16 / activity_logs 26,677 / event_line_activities 104 (31,581)
E 事实/知识/记忆/术语  — atomic_facts 1998 / memory_facts 3038 / entities 4987 ★ 关键
F 战略/分析/DNA       — client_dna_documents 32 / organization_dna_v2_items 199 / decisions 3
G AI/聊天/学习/写作    — chat_threads 305 / chat_messages 真实数据
H 智能情报/爬虫/品牌   — intelligence_candidate_items / intelligence_items
I 成长/经验/积分       — growth_signal_events
J 同步/云/系统/运行时
K 审计/迁移/去重
```

### 3.3 关键数字 (实测) — 印证 4D 评估 + 资产清单 § 重大发现

```
atomic_facts            1,998   V2.2 新设计, 信息商 + 5 维元数据
memory_facts            3,038   旧记忆层 (跟 atomic_facts 重复造轮子风险) ★ 待顾源源决策
activity_logs          26,677   真主时间线 (顾源源说"时间串人物串文件"的真源)
event_line_activities     104   视图子集 (我之前误以为是主线, 实际只是部分)
clients                    12
entities                4,987   (人物 / 组织 / 日期 / 金额 等)
tasks                     238
event_lines                16
commitments                66
risk_signals               20   ★ 现成 risks 段直接读
open_questions             23   ★ 现成 open_questions 段直接读 (表名跟段名一样)
weekly_reviews              9   ★ our_collab 段
meetings                    7
decisions                   3
client_dna_documents       32   ★ identity 段主源
organization_dna_v2_items 199
chat_threads              305
reasoning_traces            0   ★ N3 设计了未接通
ai_episode_log              0   ★ 同上
idempotency_keys            0   ★ 我 F2.8 接通了, 但 prod 没产生流量
```

### 3.4 8 段 → 现成表映射 (复用 A 资产清单 §4, 实测确认)

| 段 (产品手册 §03 钦定) | 现成表 | 行数 | 状态 |
|---|---|---|---|
| essence (本质) | client_dna_documents / organization_dna_v2_items / clients | 32+199+12 | ✅ 数据全 |
| cooperation (合作) | weekly_reviews + chat_threads + meetings + task_collaborators | 9+305+7+184 | ✅ 数据全 |
| business_intro (业务介绍) | event_lines + tasks + project_modules + commitments | 16+238+4+66 | ✅ 数据全 |
| people (人物) | entities (type=person) + entity_mentions | ~?+12184 | ✅ 数据全 |
| timeline (时间线) | activity_logs (filtered) + meetings + event_line_activities | 26677+7+104 | ✅ 数据极全 |
| next_steps (下一步) | open_questions + tasks (status=open) + risks/risk_signals | 23+(238 过滤)+20+2 | ✅ 数据全 |

**结论**: 产品手册钦定的 6 段, **每段都有现成表 + 实测数据**. 主仓库 narrative_collector 拉的 13 张表覆盖了这 6 段所需的全部.

---

## 维度 4 · V2.1 仓库 B 视角真实保留 (阶段 0 砍废后)

数据源: `git log --author=...`, `find *.DEPRECATED`

### 4.1 B 一共 14 个 commit (含本里程碑 commit)

```
本里程碑 (2026-05-22 后半段):
  96cc2d2  [B] chore(★ pivot): 砍 V2.1 8 段叙事 / baseline runner / frontend hook
  007a8de  [B] resp(asset pivot): iterate 1 资产盘点纠偏自检报告
  e05bb88  [B] docs: MILESTONE FULL_NARRATIVE audit + PROGRESS

上里程碑 N2 突破 (本次砍废后大部分 .DEPRECATED):
  5aa92d8  [B] feat(N2): baseline runner 扩展 6 待办 + 5 人物 — 砍
  4b254c1  [B] feat(N2): 前端故事全景 hook + 组件 + StrategicClarification — 砍
  90bf24f  [B] test(N2): full-narrative endpoint 8 集成测试 — 砍
  07b5dd7  [B] feat(N2): backend/app/api/ router + endpoint shell — 砍 endpoint, router 保留
  30ffca0  [B] docs: MILESTONE N2-baseline audit — 保留
  28f2a3b  [B] fix(N1): test_client_{fact_view,repository} fixture — ✅ 保留
  61a0623  [B] test(N2): baseline runner 12 自检 — 砍
  d66c026  [B] feat(N2): 5/19 金标准 baseline runner — 砍

更早 F2.8 N3 A6 (保留):
  172675e  [B] docs: F2.8-endpoint MILESTONE audit — 保留
  7ee740e  [B] test(F2.8): 8 集成测试 Stripe retry — ✅ 保留 (N3 A6 真接通)
  b43bc4a  [B] feat(F2.8): main.py 3 P0 endpoint 接入幂等 — ✅ 保留 (idempotency_keys 表流量预留)
```

### 4.2 阶段 0 砍废 11 个 .DEPRECATED 文件

```
4 个 A 自砍:
  backend/app/services/narrative_kernel.py.DEPRECATED         (V2.1 8 段 v0 内核)
  backend/tests/test_v22_narrative_kernel.py.DEPRECATED        (内核 18 单测)
  docs/V2.2_F21_AI_INFORMATION_NEEDS.md.DEPRECATED             (旧设计)
  docs/V2.2_NARRATIVE_KERNEL_V1_PROMPT_DRAFT.md.DEPRECATED     (基于 8 段)

7 个 B 自砍 (本里程碑):
  scripts/run_v22_n2_baseline.py.DEPRECATED
  backend/app/api/full_narrative_router.py.DEPRECATED
  backend/tests/test_v22_full_narrative_endpoint.py.DEPRECATED
  backend/tests/test_v22_n2_baseline_runner.py.DEPRECATED
  src/renderer/hooks/useClientFullNarrative.ts.DEPRECATED
  src/renderer/lib/fullNarrativeTypes.ts.DEPRECATED
  src/renderer/components/strategic_accompaniment/FullNarrativeSection.tsx.DEPRECATED
```

### 4.3 B 真实活代码保留 (阶段 0 砍废后, 跨多个里程碑累积)

#### 后端真活代码 (8 个文件)
```
backend/app/services/idempotency_store.py       (~280 行) ★ F2.8 N3 A6 完整, 主仓库已用
backend/app/api/__init__.py                     (~12 行)  router 包基础
backend/app/api/deps.py                         (~28 行)  Depends 注入
backend/tests/test_v22_f28_endpoint_idempotency.py  (~290 行) 8 集成测试
backend/tests/test_v22_f28_idempotency.py       (~370 行) 17 单测
backend/tests/test_v22_f22_f26_compound_events.py  (协助 A 测试)
backend/tests/test_v22_f27_reasoning_traces.py     (协助 A 测试)
tests/test_client_repository.py + test_client_fact_view.py + test_client_scope_filter.py 修 fixture
```

#### 前端真活代码 (3 处注释 + 0 个新文件保留)
```
阶段 0 砍废后: 0 个 B 主写的活前端文件保留.
3 处引用注释 (main.py / StrategicClarificationView / api.ts).
```

#### 文档真活 (10+ 个)
```
docs/V2.1_AI_COLLABORATION.md            (协作契约, A+B 共编)
docs/B_AI_*.md                           (8 份 audit / 自检报告)
docs/MILESTONE_*.md                      (4 份里程碑 audit)
docs/V2.2_F28_*.md                       (2 份 F2.8 设计文档)
docs/V2.2_W1W2W3_REUSE_BOUNDARY.md
```

### 4.4 B 视角真贡献价值 (诚实)

```
★ 真贡献 (主仓库未来会用上, 不是孤岛):
  - F2.8 IdempotencyStore (N3 A6 完整) — 3.0 AI agent retry 容错的基础设施
  - 协作流程文档 (V2.1_AI_COLLABORATION.md + 8 份 audit + 自检报告)
  - 多个里程碑诚实 audit 留档

⚠️ 价值不确定:
  - backend/app/api/ router 基础设施 — 暂时孤儿, 等下次新 endpoint 复用
  - Client repository / fact_view fixture 修复 — 在 V2.1 修了, 主仓库可能不需要 sync

🔴 已废:
  - 8 段假增量 + baseline runner (单源测试)
  - V2.1 自己的 NarrativeKernel (重复造轮子)
```

---

## 综合评估

### 评估 1: 工程方向跟 3 大目标的对齐度

| 目标 | 主仓库现状 | V2.1 B 贡献 | 整体进度 |
|---|---|---|---|
| **N1 (现有功能不掉链)** | 9 板块完整运行 (Mac 公证打包流程通) | fixture 修复 +5 测试 | ✅ ~90% |
| **N2 (机器人能拿全数据流畅回答)** | narrative_generator 6 段已实现, 但 collector 漏拉关键现成表 (A 阶段 2 在做) | F2.8 idempotency 给 N2 LLM 调用预留 retry 容错 | ⚠️ ~40-50% (待 A 阶段 2 补 collector + 阶段 3 接 smart_file_import) |
| **N3 (3.0 接入预留)** | 6/7 schema 在 + IdempotencyStore 完整 + AI Memory 5 表占位但 0 流量 | F2.8 N3 A6 100% + 3 P0 endpoint 接入 | ⚠️ schema ~85% / 流量 ~15% |

### 评估 2: 主仓库 vs V2.1 关系再确认

```
V2.1 = 主仓库的实验下游 mirror (新计划 §1.1 顾源源确认):
- 跟主仓库共享代码骨架 (60+ services 重叠)
- V2.1 自己加: F2.8 + IngestPipeline + V2.2 schema 实验
- V2.1 砍废的 8 段假增量是"在主仓库已有 6 段的情况下平行实验出错的版本"

接下来该做的:
- V2.1 实验通的 (F2.8 idempotency) → A 阶段 2/3 把它合入主仓库
- 主仓库 narrative_generator 6 段 + collector 补漏 → 直接走主仓库, V2.1 不平行
```

### 评估 3: 当前里程碑结束位置 (阶段 0 完成)

```
✅ 砍废干净, 没历史包袱
✅ 双 AI 协作流程跑通了纠偏 + 同步砍废
✅ 共享文档 (V2.2_DATA_ASSET_INVENTORY + V2.2_PRODUCT_MANUAL + 4D ASSESSMENT + NEW PLAN + B 自检) 完整
⚠️ 还没真改主仓库代码 (B 阶段 1-5 等顾源源给起步令)
⚠️ N2 业务数字目前 = 主仓库 narrative_generator 现有命中率 (A 阶段 1 跑出 dogfood 后才知道)
```

---

## 下一步计划 (B 视角, 等 A 阶段 1 完成 + 顾源源决策)

### 短期 (本周, 跟 sync 指令 §阶段 1-5 对齐)

```
阶段 1 (B 45 min)  · 前端 NarrativePanel + 让 AI 重新理解按钮链路审计 (等 A 阶段 1 完成 dogfood baseline)
阶段 2 (B 2h)      · narrative endpoint 集成测试 + 前端 6 段渲染扩展 (等 A 阶段 2 collector 补完)
阶段 3 (B 2h)      · smart_file_import → 90 秒 6 段自动刷新 e2e (等 A 阶段 3 接通 broadcast)
阶段 4 (B 旁观)    · 跑 V2.2 acceptance 三道门, 看 ai_episode_log / reasoning_traces 流量增长
阶段 5 (B 45 min)  · 9 模块手动过 audit + 配合 final dogfood
```

### 中期 (V2.2 完成后)

```
1. V2.1 实验产物 (F2.8 idempotency + IngestPipeline 4 路径设计 + ClientFactView L2 共识层) 合入主仓库
2. 主仓库 atomic_facts vs memory_facts 决策落地 (顾源源待拍板)
3. Mac 公证打包 release:mac:publish → 用户实际感知到 v2.2 上线
```

### 长期 (3.0 准备)

```
1. AI Memory 5 表真接通 (reasoning_traces / ai_episode_log / ai_feedback_signals 等)
2. 4 主路径全部接 IngestPipeline (路径 2 / 路径 3 / 路径 4)
3. 手机 AI 朋友式聊天 schema 扩展 (chat_messages 不够支撑朋友式澄清)
```

---

## §EDGE · 流程沉淀建议

按顾源源 5/22 钦定: **每个里程碑结束都要跑 4 维度盘点流程**.

建议在 `docs/V2.1_AI_COLLABORATION.md` §7 (每个里程碑结束必做) 加新条款 §7.1 (B 即将做).

参考: 本文档 = 这个流程的第一份完整产物.

---

**B AI · 2026-05-22 · 阶段 0 后立刻跑完 4 维度盘点 — 等顾源源对齐**
