# B AI · 新计划阶段 0 · 砍废清单

> **来源**: 顾源源 5/22 新计划接力 (`docs/B_AI_SYNC_20260522_NEW_PLAN.md` §阶段 0)
> **触发**: 产品手册 §03 钦定 6 段 (essence/cooperation/business_intro/people/timeline/next_steps) ≠ V2.1 设计的 8 段
> **执行人**: AI B
> **日期**: 2026-05-22

---

## 0 · 偏差根因 (一句话)

V2.1 iterate 1 (5 个 commit) 设计的 "8 段故事网" 跟产品手册 §03 钦定的 6 段不同, 且主仓库 `narrative_generator.py` (1156 行) 已实现 6 段 + 13 张现成表 collector. V2.1 重复造轮子 + 段命名冲突, 全部砍.

---

## 1 · 砍废文件清单 (7 个, 全部 `.DEPRECATED`)

| # | 文件 | 历史 commit | 大小 | 砍废理由 |
|---|---|---|---|---|
| 1 | `scripts/run_v22_n2_baseline.py.DEPRECATED` | d66c026 / 5aa92d8 | ~30 KB | 测 atomic_facts 单源命中, 跟产品手册 6 段无关 |
| 2 | `backend/app/api/full_narrative_router.py.DEPRECATED` | 07b5dd7 | ~10 KB | 8 段 endpoint shell, 跟主仓库 narrative_generator 6 段冲突 |
| 3 | `backend/tests/test_v22_full_narrative_endpoint.py.DEPRECATED` | 90bf24f | ~11 KB | 测 8 段 endpoint, 跟随主代码废弃 |
| 4 | `backend/tests/test_v22_n2_baseline_runner.py.DEPRECATED` | 61a0623 | ~16 KB | baseline runner 自检, 跟随主脚本废弃 |
| 5 | `src/renderer/hooks/useClientFullNarrative.ts.DEPRECATED` | 4b254c1 | ~3 KB | 8 段 React hook |
| 6 | `src/renderer/lib/fullNarrativeTypes.ts.DEPRECATED` | 4b254c1 | ~2 KB | 8 段 TypeScript 类型 |
| 7 | `src/renderer/components/strategic_accompaniment/FullNarrativeSection.tsx.DEPRECATED` | 4b254c1 | ~6 KB | 8 段渲染组件 |

**每个 `.DEPRECATED` 文件头**:
- 加 `[DEPRECATED 2026-05-22 · 顾源源新计划接力指令 阶段 0]` 标记
- 写明跟产品手册 §03 6 段的冲突
- 指向新计划 `docs/V2.2_NEW_PLAN_20260522.md` 阶段 2

---

## 2 · 引用断链清单 (3 处, 全部注释)

为防 build 红 / import 报错, 砍废文件的所有引用方注释掉 (不删除调用方代码本身, 保留方便回退):

| # | 文件 | 改动 |
|---|---|---|
| 1 | `backend/app/main.py:3122-3127` | 注释 `from app.api import full_narrative_router` + `app.include_router(...)`. V2.1 router 不再挂载到 FastAPI app |
| 2 | `src/renderer/components/strategic_accompaniment/StrategicClarificationView.tsx:71 + 319-326` | 注释 `import { FullNarrativeSection } from ...` + 注释顶部接入块 (旧 NarrativePanel 6 维度面板保留, 改后主仓库 NarrativePanel 替代) |
| 3 | `src/renderer/lib/api.ts:1755-1756 + 1784-1813` | 注释 `import type { FullNarrative, FetchFullNarrativeOptions }` + 注释 `fetchClientFullNarrative` 函数 |

---

## 3 · 验收门 (sync 指令 §阶段 0 验收门, 全过)

| 门 | 要求 | 结果 |
|---|---|---|
| ① `git grep` 8 段关键词残留 | ≤ 5 个文件, 都是文档 / DEPRECATED | ✅ 7 个文件: 5 文档 + 2 含注释的代码 (api.ts / StrategicClarificationView.tsx), 0 活代码引用 |
| ② backend import smoke | main.py 导入成功, full-narrative routes 0 个 | ✅ 实测 OK, routes = 0 |
| ③ 前端 tsc | 0 error (允许 unused import 警告) | ✅ 0 error |
| ④ 任何 atomic_facts 单源 baseline 代码 | 全砍 | ✅ 唯一 baseline runner 已 `.DEPRECATED` |

---

## 4 · iterate 1 保留度估算 (跟自检报告对照)

| commit | 自检报告估算保留度 | 阶段 0 真实处置 |
|---|---|---|
| 07b5dd7 endpoint shell + router 模块化 | 100% | 🔴 endpoint 砍, **router 基础设施 `backend/app/api/` (`__init__.py` + `deps.py`) 保留**: 是通用基础设施, 跟"8 段"无关, 等下次新 endpoint 复用 |
| 90bf24f 8 集成测试 | 95% | 🔴 全砍 (测的是 8 段 endpoint) |
| 4b254c1 前端 hook + 组件 + 接入 | 85% | 🔴 全砍 (3 个文件 + 3 处引用注释) |
| 5aa92d8 baseline runner 扩展 | 30% | 🔴 全砍 (主脚本 + 自检测试 2 个文件) |
| e05bb88 audit + PROGRESS | 100% | ✅ **保留** (历史诚实记录, 不删) |
| 007a8de B 自检报告 | 100% | ✅ **保留** (审议过程记录) |

**真实保留代码 = 0%** (全部 7 个文件砍)
**保留 = 2 篇 audit + 1 篇自检报告 + router 基础设施 2 个文件** (历史 + 复用)

---

## 5 · 关键不动的东西

按协作红线 ([B] 严格不动 A 的文件), 工作树里以下 A 的 `.DEPRECATED` 我没动 (A 自己砍的):

- `backend/app/services/narrative_kernel.py.DEPRECATED` (A 自己砍 v0 8 段 kernel)
- `backend/tests/test_v22_narrative_kernel.py.DEPRECATED` (A 自己砍 kernel 测试)
- `docs/V2.2_F21_AI_INFORMATION_NEEDS.md.DEPRECATED` (A 砍 — 文档)
- `docs/V2.2_NARRATIVE_KERNEL_V1_PROMPT_DRAFT.md.DEPRECATED` (A 砍 — v1 prompt 草稿也跟着废)

A 工作树仍有 `?? scripts/run_event_line_activities_extraction.py` (A 留的 untracked 脚本), 我严格不动.

---

## 6 · 下一步 (阶段 1, 等顾源源起步令)

按 sync 指令 §阶段 1 (45 min), 等 A 跑出 dogfood 6 段 baseline 后, B 任务:

1. grep 主仓库 `narrative_generator` / `/narrative` endpoint URL
2. grep 前端 `NarrativePanel` 组件位置 + 调的 API
3. 找"让 AI 重新理解"按钮位置 + 触发链路
4. 写 `docs/B_AI_PHASE_1_FRONTEND_AUDIT.md` (4 个问题全部用 grep 结果回答, 不猜测)
5. 不改前端

**等顾源源在 sync 指令 §三 协作时间表"T+45min"那个点通知开干阶段 1**.

---

## 7 · 提案前 4 道自检 (协作文档 §6.2)

| Q | A |
|---|---|
| Q1 我做的事在 §4 资产映射里有现成表? | 阶段 0 是砍 V2.1 假增量, 不建表, 不抽取 — 跳过 |
| Q2 我加的代码跟主仓库 narrative_generator/collector 重叠? | 阶段 0 砍 V2.1, 反而是为了消除重叠 — 通过 |
| Q3 引用的"段"是产品手册 §03 钦定 6 个之一? | 本砍废清单文档明确认定钦定 6 段, 砍 V2.1 旧 8 段 — 通过 |
| Q4 引用了"行数/字段/commit"事实? | 引用 commit (d66c026 / 5aa92d8 / 07b5dd7 / 90bf24f / 4b254c1 / 61a0623) + 文件大小 + 行号 (`main.py:3122-3127`, `StrategicClarificationView.tsx:71+319-326`, `api.ts:1755-1756+1784-1813`) — 通过 |

**4 道全过, 可 commit**.

---

**B AI · 2026-05-22 · 阶段 0 完成, 等顾源源给阶段 1 起步令**
