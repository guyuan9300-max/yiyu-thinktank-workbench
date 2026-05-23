# V2.1 RC 综合评估报告 · AI 操控软件北极星距离 (顾源源 5/23 钦定)

> **生成**: 2026-05-23 21:10
> **commit**: `eb7505d` (B M0+M1) + `51eaab7` (A R4-P1 P1-5+P1-6 97/100)
> **评估对象**: V2.1 仓库 (= 未来主仓库 Release Candidate)
> **评估视角**: 顾源源 5/23 钦定 — "Codex / Claude Code 当 CEO 调度软件做事"
> **B 角色**: 自动验收官 (不替 A 写复杂业务)

---

## 一句话结论

**V2.1 当前完成度约 30-35%**, 距离 "Codex 当 CEO 自主调度软件做事 + 评判返工" 还要 **1-2 个月** (含产品设计风险余量).

- ✅ L1 单链路 (会议纪要专员) — 真过, 用户能用
- ❌ L2 多模块调度 — 缺 5+ endpoint, 距离 2-3 天 (A 工程)
- ❌ L3 主动缺口发现 — 缺 data-gaps endpoint, 距离 1-2 天
- ❌ L4 Goal-Plan-Run — 全没, 距离 3-5 天 (V3.0 P1)
- ❌ L5 质量评估器 — 全没, 距离 1-2 周 (需 ground truth)
- ❌ L6 返工循环 — 全没, 距离 1 周
- ❌ L7 CEO 自主决策 — 全没, 距离 1-2 周 (需组织记忆架构)

---

## 1 · 三大客观指标 snapshot

| 指标 | 分 / 状态 | 数据来源 | 备注 |
|---|---|---|---|
| **R2 真分** | **64/100 + 6/6 硬门槛全过 ✅** | B 真测 V2.1 lab db | 跨客户 0 leak / 幂等 / HTTP only / facts +5 / event_line +3 / clarif +1 |
| **R4-P0 用户可感知** | **A 自评 90** ⚠️ 待 B 复验 | A 285e185 复测 | A 14 功能 ABCDE 评级 1A+5B+5C+3D, R4-P0 通过线 A 级 ≥ 5 |
| **R4-P1 用户工作流** | **A 自评 97** ⚠️ 待 B 复验 | A 51eaab7 复测 | A 6 项 P1 全干完, 10/10 硬门槛全过 |
| **R4 数据库-功能深度联动** | A 自评 63 → 90 → 94 → ? | A 5fefcf3 → 285e185 → 804a849 | 读取 33→43→49 / 写入 30→47→48 |
| **V3.0 AI 驱动软件做事** | **B 真测 66.5/100** 🔴 (差 13.5) | B 698d2ca 真测 V2.1 lab db | 56.5 → 66.5 (+10) 是 prompt 调优软涨, 不是 endpoint 硬涨 |
| **V3.0 L1-L4 通过层数** | **B 真测 1/4** 🔴 | B 19:45 / 20:18 dryrun (2 次) | L1 ✅ / L2 L3 L4 全 blocked_by_A |
| **V3 M0/M1/M2 路线图** | **B 完成 3/8** ✅ | B M0+M1+M2 commit | M3-M7 待做 |

---

## 2 · "Codex 操控软件" 7 层能力评估

| 层 | 描述 | 当前 % | 距通过 | 阻塞 |
|---|---|---|---|---|
| **L1 read-only 调用** | Codex 读软件数据 (客户/任务/事实/审批) | **45%** | 1-2 天 | 缺 Tool Registry endpoint, GET /agent-run-logs 404, GET /data-gaps 404 |
| **L2 单工具单动作** | Codex 给一个明确动作 (写会议纪要 / 触发问答) | **60%** | 2-3 天 | 合同/模板/品牌 endpoint 缺 (V3.0 任务书 3 个核心) |
| **L3 多步拆解** | Codex 给目标, AI 自己拆 N 步执行 | **5%** | 3-5 天 | POST /agent/plan + /agent/run + Tool Registry 全 404 |
| **L4 每步成败判断** | 自动判每步 success/error + retry | **30%** | 1-2 周 | agent_run_log 表有, 但没 Goal-Plan-Run 框架挂上 |
| **L5 评判结果质量** | AI 评 AI 输出好不好 | **10%** | 1-2 周 | 没 "AI 评 AI" 反馈机制, 需 ground truth 校准 |
| **L6 大模型返工** | 不好的结果让 AI 重新做 | **15%** | 1 周 | A 有 self_heal service 不暴露, 没循环机制 |
| **L7 CEO 自主决策** | 每天自主"今天该做什么" | **0%** | 1-2 周+ | 完全没 (需长期目标记忆 + 日程感知 + 优先级判断 + 任务调度) |

**整体平均**: **27%** (跟前一份估算 25-30% 一致)

---

## 3 · 两个目标各自的真实距离

### 目标 A: Codex 给单一指令操作软件 (例如"处理明远 5/22 会议纪要")

**乐观估**: 3-5 天 (A 全职 + 不被打断)
**实际估 (含 30% 余量)**: **1 周**

需要 A 暴露:
1. `POST /api/v1/contracts/draft` (合同草稿) — V3.0 P0-1
2. `POST /api/v1/templates/generate` (理事会说明) — V3.0 P0-2
3. `POST /api/v1/clients/{id}/brand-proposition` (品牌建议) — fix 405
4. `POST /api/v1/strategic-cockpit/meeting-pack` (会谈提纲) — fix 403
5. `GET /api/v1/clients/{id}/data-gaps` (Data Gap) — V3.0 P0a
6. `POST /api/v1/agent/plan` + `/agent/run` (Goal-Plan-Run) — V3.0 P1
7. `GET /api/v1/agent-run-logs` (用户可见 Run Log)
+ B 写 yiyu CLI 真实现 (M2 已写本地模拟版, 真版要打包)

**B 当前已做**: M0/M1/M2 (评估标准 + Tool Registry + dry-run CLI) ✅

### 目标 B: Codex 当 CEO 自主决策 + 返工 (顾源源描述的"每天 AI 自主调度")

**乐观估**: 2-4 周
**实际估 (含产品设计风险)**: **1-2 个月**

需要目标 A 全套 + 4 层新能力:

```
A 全套 (1 周)
+ L5 质量评估器 (M5, 3-5 天)
   - 给每类成果定 quality score
   - AI 自我评分 + 外部 ground truth 校准 (避免 LLM 评 LLM 自欺)
+ L6 返工循环 (M6, 3-5 天)
   - 评分 < 阈值时生成 "为什么不好 + 怎么改" prompt 重跑
   - max_retries=3, exponential backoff
+ L7 CEO 决策 (M7, 5-7 天)
   - 长期目标记忆 + 日历感知 + 优先级判断 + 任务调度
+ 真客户跑通 + 调优 (1-2 周)
```

---

## 4 · 4 个隐藏风险 (顾源源应该知道)

### 风险 1 — A 自评 vs B 真测信任差 33 分

```
A R4-P1 自评: 97
B V3.0 真测: 66.5
差: 30.5 分

但维度不同 (A R4-P1 评 14 功能, B V3.0 评 7 维度 100 分制)
不能直接对比, 但提示: A 自评偏乐观, B 真测更严
```

**对策**: B 下一波必须跑 Golden Pack qa_10 × 14 功能逐项独立 verify, 2-3h 工作量.

### 风险 2 — "AI 评 AI" 容易陷入循环 (L5 真难)

L5 质量评估器要求 LLM 自己评自己输出. 但 LLM 评分:
- 虚高常见 ("这份合同写得很好" 实际漏 IP 条款)
- 评分波动大 (同输入跑 3 次, 4/5 → 3/5 → 4/5)

**对策**: 需外部 ground truth (真客户案例) 校准. 这工作量没算 L5 1-2 周里, 真做要 **+1 周**.

### 风险 3 — CEO 决策需要"组织记忆" (L7 是新工程)

顾源源描述"Codex 当 CEO, 每天判断该做什么" — 要求:
- Codex 知道 "明远基金会下周三会谈" → 今天该准备会谈提纲
- Codex 知道 "上周日慈合同还在审批" → 今天该跟进
- Codex 知道 "5 月底交理事会简版" → 倒推今天做什么

需 **长期目标记忆 + 时间感知 + 跨客户优先级**. V3.0 P3 设计文档提了, A 没动. 真做 **+1 周**.

### 风险 4 — 双驱动一致性

顾源源 5/23 钦定 "双驱动同底座" — 益语内置 AI 跟 Codex 共用 Agent Gateway + Tool Registry. 但:

- 益语内置 AI: 跑在 backend service 内部 (workspace/chat)
- Codex: 想通过 HTTP 调同底座

如果 Codex 跟内置 AI 不一致, B 测过 facts 5 vs 5 一致 ✅, 但更复杂场景 (合同/品牌) 没测. **隐藏返工 3-5 天**.

---

## 5 · 路线图 (M0-M7) 状态

| Milestone | 目标分 | 状态 | 完成时间 | 产出 |
|---|---|---|---|---|
| **M0** 评估标准 + Golden Pack | (基础, 无分) | ✅ **100%** | 5/23 19:55 + 20:35 | `docs/B_V3_M0_STANDARD_AND_GOLDEN_PACK.md` + 7 样本 + 8 段模板 |
| **M1** Tool Registry v1 | ≥ 80 | ✅ **100%** | 5/23 20:50 | `docs/B_V3_M1_TOOL_REGISTRY_V1.md` + 探针 + 报告 |
| **M2** 外置 Agent dry-run CLI | ≥ 80 | ✅ **100%** | 5/23 21:00 | `scripts/yiyu_agent_cli.py` 6 子命令 + dry-run 报告 |
| **M3** 单指令 draft-run | ≥ 80 | ⏸ **0%** | 等 A V3.0 5 endpoint | 等 |
| **M4** Daily Brief 项目经理模式 | ≥ 80 | ⏸ 0% | M3 后 | - |
| **M5** 质量评估器 v1 | ≥ 80 | ⏸ 0% | M4 后 | - |
| **M6** 返工循环 v1 | ≥ 80 | ⏸ 0% | M5 后 | - |
| **M7** CEO 模式 dogfood | ≥ 80 | ⏸ 0% | 全部 + 1-2 个月 | - |

**M0+M1+M2 全过通过线 ≥ 80** (顾源源 5/23 20:30 路线图三件 done).

---

## 6 · A 接下来要建什么 endpoint 才能 V3.0 ≥ 80 真过

**优先级 P0** (V3.0 任务书核心, 直接卡 L2):
1. `POST /api/v1/contracts/draft` — 合同草稿 (顾源源样本 1 最重要)
2. `POST /api/v1/templates/generate` — 理事会说明 / 品牌方案
3. `POST /api/v1/clients/{id}/brand-proposition` (改 POST) — 品牌建议
4. `POST /api/v1/strategic-cockpit/meeting-pack` (修 403) — 会谈提纲
5. `GET /api/v1/clients/{id}/data-gaps` — Data Gap (V3.0 P0a)

**优先级 P1** (R4-P0 前端 + UI):
6. R4-P0 P0-4 narrative_generator prompt 用 R4 字段 (A 自报已做)
7. R4-P0 4 badge 挂头部 (A 自报已做)
8. `GET /api/v1/agent-run-logs` — 用户可见 Run Log

**优先级 P2** (V3.0 P1 Goal-Plan-Run, 大工程):
9. `POST /api/v1/agent/plan`
10. `POST /api/v1/agent/run`
11. `GET /api/v1/agent/status`
12. `GET /api/v1/tool-registry` (让 Codex 真调)

→ A 干完 P0 5 件 (估 8-12h), V3.0 D3 成果包从 4/10 → 9/10, 总分预测 66.5 → 85+.

---

## 7 · B 已交付清单 (5/23)

### 文档 (12 份)
- `docs/B_AI_EVAL_STANDARD_V1.md` — 评估标准 v1
- `docs/B_AI_GOLDEN_TEST_PACK.md` — Golden Pack 规格
- `docs/B_AI_EVAL_BASELINE_REPORT.md` — 评估基线 (3 模式真跑)
- `docs/B_AI_V3_DRYRUN_REPORT.md` — V3.0 L1-L4 dryrun (1/4)
- `docs/B_AI_EXTERNAL_AGENT_DRYRUN_CONTRACT.md` — 6 命令上层契约
- `docs/B_AI_PROGRESS_RADAR.md` — 进展雷达 (持续更新)
- `docs/B_AI_NEXT_STAGE_WORK_REPORT.md` — 阶段总结
- `docs/B_V3_M0_STANDARD_AND_GOLDEN_PACK.md` — M0 索引
- `docs/B_V3_MILESTONE_REPORT_TEMPLATE.md` — M1-M7 8 段模板
- `docs/B_V3_M1_TOOL_REGISTRY_V1.md` — Tool Registry 11 工具 schema
- `docs/B_V3_M1_TOOL_REGISTRY_REPORT.md` — M1 探针报告
- `docs/B_V3_M2_DRY_RUN_REPORT.md` — M2 dry-run 报告
- `docs/B_V3_COMPREHENSIVE_EVAL_REPORT_20260523.md` — **本文 (综合评估)**

### 脚本 (5 个)
- `scripts/init_v21_lab_schema.py` — V2.1 lab db 16 表 ensure
- `scripts/run_v25_r2_meeting_minute.py` — R2 真测试
- `scripts/run_v30_ai_driven_software_eval.py` — V3.0 100 分制评估
- `scripts/run_b_eval_baseline.py` — 4 模式总入口
- `scripts/run_v3_ai_driven_dryrun_eval.py` — V3.0 L1-L4 dryrun
- `scripts/probe_tool_registry.py` — Tool Registry 探针
- `scripts/yiyu_agent_cli.py` — yiyu CLI 6 子命令 dry-run 模拟器

### Golden Pack (7 样本)
- `fixtures/golden/meeting_mingyuan.txt` — 复杂会议纪要
- `fixtures/golden/qa_10.txt` — 工作台 10 真问题
- `fixtures/golden/files_20.txt` — 20 文件导入
- `fixtures/golden/weekly_review.txt` — 周复盘
- `fixtures/golden/task_create.txt` — 任务创建
- `fixtures/golden/intelligence_brand.txt` — 外部情报
- `fixtures/golden/method_card.txt` — 方法卡

### npm 命令 (集成, 顾源源一键跑)
```
npm run db:init:lab          16 张表 ensure
npm run db:check:lab         只看不建
npm run eval:r2              R2 真测试
npm run eval:v30:ai-driven   V3.0 100 分制
npm run eval:b:baseline      4 模式总入口
npm run eval:b:capability    L1 endpoint smoke
npm run eval:b:db            L2 V2.1 lab db
npm run eval:b:ui            L3 UI 人工 verify
npm run eval:v3:dryrun       V3.0 L1-L4
```

### inbox 协议 (跟 A 协作, 4 次 sync)
- inbox-A.md (B 写 A 读) — 3 条留言
- log.md — 双方时间线 (持续追加)

---

## 8 · 给顾源源的 5 件待拍板

1. **接受 A R4-P1 97 自评当 V2.1 RC 真合格?**
   - B 推荐: **不接受** (A 自评偏乐观, 跟 B V3.0 真测 66.5 差 30.5)
   - B 替代方案: A 97 当"实验能力", V2.1 RC 真合格等 **B Golden Pack × 14 功能独立复验** (2-3h)

2. **V3.0 任务书 5 endpoint 优先级你定?**
   - B 推荐: 合同 > 模板 > Data Gap > 会谈提纲权限 > 品牌建议
   - 干完 P0 估 8-12h, V3.0 预测 66.5 → 85+

3. **CEO 模式 (L7) 现在不要做?**
   - B 推荐: ✅ 先聚焦 L3 (Goal-Plan-Run), L3 通了真让 Codex 处理 1 个真客户 1 个真目标
   - 看完真实效果再决定 L5-L7 怎么做 (避免按想象做错方向)

4. **桌面同步?**
   - B 推荐: 拷 V3.0 报告 + R4 报告 + 本综合报告 到 `~/Desktop/益语智库 2.0 产品手册/` (顾源源任意时刻可读)

5. **B 接下来 autonomous 干什么?**
   - 选项 A: 跑 Golden Pack × 14 功能独立复验 (2-3h, 真验 A 自评)
   - 选项 B: 修 M1 探针 path (smart_import / tasks) → 完善 (30 min)
   - 选项 C: 准备 M3 单指令 draft-run 脚本 (等 A V3.0 5 endpoint 后真跑)
   - B 推荐: B + C 并行 (修探针 + 准备 M3, 1.5h), 等 A 真暴露 P0 后立刻 M3 测试

---

## 9 · 一句话总结

```
现在: AI 是会议纪要专员 (L1 通)
目标 A (1 周): AI 是项目助理 (L2+L3 通, Codex 单指令操作软件)
目标 B (1-2 个月): AI 是 CEO (L4-L7 全通, Codex 当 CEO 调度 + 评判 + 返工)
```

**B 路线**:
```
✅ M0 评估标准 + Golden Pack
✅ M1 Tool Registry v1 (11 工具)
✅ M2 外置 Agent dry-run CLI
⏸ M3 单指令 draft-run (等 A V3.0 5 endpoint)
⏸ M4 Daily Brief (项目经理模式)
⏸ M5 质量评估器
⏸ M6 返工循环
⏸ M7 CEO 模式 dogfood
```

**A 路线** (B 推断):
```
✅ R2 endpoint 暴露 + fix-2
✅ R4-P0 P0-2/3/5
✅ R4-P1 P1-1~P1-6 真做完 (94→97, 但 V3.0 任务书 endpoint 没碰)
⏸ V3.0 任务书 5 endpoint (合同/模板/品牌/会谈提纲/Data Gap)
⏸ V3.0 P1 Goal-Plan-Run 三件套
```

---

**Author**: AI B · 2026-05-23 21:10
**冻结**: V1 (后续 commit 用 V2, 不覆盖)
**关联**:
- B 已交付 12 文档 + 7 脚本 + 7 Golden 样本 (本文 §7)
- A 285e185 R4 90 / 51eaab7 R4-P1 97 (A 自评待 B 复验)
- B 748c833 V3.0 56.5 → 698d2ca V3.0 66.5 (B 真测)
- 顾源源 5/23 7 阶段路线图 (本文 §5)
