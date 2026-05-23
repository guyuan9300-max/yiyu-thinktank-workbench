# B V3 · M0 · 评估标准 + Golden Pack (顾源源 5/23 20:30 路线图重命名)

> **状态**: ✅ 100% 完成 (2026-05-23 19:55 7 件交付里 B0+B1 已交)
> **本文件**: 路线图 M0 索引 (实际内容在子文件)
> **路线**: M0 → M1 Tool Registry → M2 dry-run CLI → M3 单指令 draft-run → M4 Daily Brief → M5/6 质量+返工 → M7 CEO dogfood

---

## 1 · M0 交付清单 (全部 ✅)

| 文件 | 内容 |
|---|---|
| `docs/B_AI_EVAL_STANDARD_V1.md` | 评估标准 v1 · 3 层证据 (L1 API / L2 DB / L3 UI) + R2/R4-P0/V3.0 评分公式 + 14 功能 A-E + 硬门槛 + 通过 vs 实验能力 + 必带 6 件 + blocked_by_X 规则 |
| `docs/B_AI_GOLDEN_TEST_PACK.md` | Golden Test Pack 7 类样本规格 + 期望调用模块 + 期望 evidence + 期望成果包 |
| `fixtures/golden/meeting_mingyuan.txt` | 复杂会议纪要 (V3.0 标准输入, 含 6 子目标) |
| `fixtures/golden/qa_10.txt` | 工作台 10 真问题 |
| `fixtures/golden/files_20.txt` | 20 文件导入样本 |
| `fixtures/golden/weekly_review.txt` | 周复盘 + 历史回指 |
| `fixtures/golden/task_create.txt` | 任务创建 |
| `fixtures/golden/intelligence_brand.txt` | 外部情报检索 |
| `fixtures/golden/method_card.txt` | 方法卡 (R3 H6 不污染验证) |
| `fixtures/golden/README.md` | Golden 目录索引 |
| `docs/B_V3_MILESTONE_REPORT_TEMPLATE.md` | **本批新增**: 8 段 milestone 报告模板 |

---

## 2 · 8 段 Milestone 报告统一模板 (顾源源七钦定)

每个 M1-M7 报告必须含:

```
1. 本次目标
2. 测试输入原文 (Golden Pack 引用 + 全文附录)
3. Agent 生成的计划 (原文)
4. 实际调用的工具
5. 产出的用户成果包
6. 成果质量评分
7. 待审批事项
8. 安全检查 (无直写 db / 无自动发出 / 有 Run Log / 危险动作进 Approval)
+ blocked_by_A / blocked_by_B
+ 下一步修复建议
```

详见 `docs/B_V3_MILESTONE_REPORT_TEMPLATE.md`.

---

## 3 · M0 通过标准 (顾源源 5/23 三 §阶段 0)

| 指标 | 目标 | 实际 |
|---|---|---|
| 固定测试样本类型 | ≥ 7 类 | ✅ 7 类 (meeting / qa / files / review / task / intelligence / method_card) |
| 每类样本有原文 | 100% | ✅ 7/7 |
| 每类样本有期望成果 | 100% | ✅ `B_AI_GOLDEN_TEST_PACK.md` 每类列了期望模块/evidence/成果包 |
| 每次评估输出 Markdown + JSON | 100% | ✅ `run_b_eval_baseline.py` + `run_v3_ai_driven_dryrun_eval.py` 双输出 |
| 每个失败项能标 blocked_by_A / blocked_by_B / blocked_by_user | 100% | ✅ `B_AI_EVAL_STANDARD_V1` §9 规则 |

**通过**: ✅ M0 通过. B 能一键跑出当前外置 Agent 能力分数 + 列缺失 endpoint.

---

## 4 · M0 npm 命令 (顾源源可一键跑)

```
npm run db:check:lab          看 V2.1 lab db 16 张表状态
npm run eval:b:capability     L1 endpoint smoke
npm run eval:b:db             L2 V2.1 lab db 真状态
npm run eval:b:ui             L3 UI 人工 verify 清单
npm run eval:b:baseline       全 4 模式
npm run eval:v3:dryrun        V3.0 L1-L4 dry-run
npm run eval:r2               R2 真测试 (日慈+CFFC)
npm run eval:v30:ai-driven    V3.0 100 分制 + 7 维度
```

---

## 5 · 路线图

```
M0 ✅ (本文) — 评估标准 + Golden Pack 固化
M1 🔄 (下一里程碑) — Tool Registry v1 (外置 Agent 看懂工具清单)
M2 ⏸ — dry-run CLI (能计划不写入)
M3 ⏸ — 单指令 draft-run (明远会议纪要 → 7 成果包)
M4 ⏸ — Daily Brief 项目经理模式
M5 ⏸ — 质量评估器 v1
M6 ⏸ — 返工循环 v1
M7 ⏸ — CEO 模式 dogfood
```

**B 当前在 M1**. M0 全 ✅. 不依赖 A 任何 endpoint.

---

**Author**: AI B · 2026-05-23 20:35
**关联**:
- 顾源源 5/23 20:30 V3.0 外置 Agent 推进计划 (7 阶段路线图)
- B 19:55 7 件交付 (本文 §1 子文件已落档)
- 下一: `docs/B_V3_M1_TOOL_REGISTRY_REPORT.md`
