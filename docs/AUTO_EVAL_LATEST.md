# 自动 eval · 双层 L1+L2 baseline · 日慈基金会

> 生成: 2026-05-23T11:07:23.214501+00:00 · 耗时 141s · trigger: efd6870: [A] feat(r4-p1 P1-1+P1-2): narrative prompt 真用 R4 + 4 badge 挂前端
> client_id: `client_284afd836e`
> dataset: 5/19 张真会议 7 关键词 (V2.2 阶段唯一 dataset)

## L1 vs L2 命中对比

| 维度 | 命中 | P% | 含义 |
|---|---|---|---|
| **L1** atomic_facts | 7/7 | **100.0%** | LLM extractor 抽到 + IngestPipeline 入库 |
| **L2** 6 段叙事 | 2/7 | **28.6%** | 用户在战略陪伴看到的内容 |

## 诊断

🟡 L1 高但 L2 低 (atomic_facts 有但没拼上) → collector 漏拉 或 generator prompt 没用上. 查 narrative_collector + narrative_generator

## 7 关键词逐项 (L1 vs L2)

| 关键词 | L1 atomic_facts 计数 | L2 6 段叙事计数 | L1 命中? | L2 命中? |
|---|---|---|---|---|
| 法人 | 1 | 0 | ✓ | ✗ |
| 理事长 | 2 | 2 | ✓ | ✓ |
| 强哥 | 2 | 0 | ✓ | ✗ |
| 秘书长 | 4 | 0 | ✓ | ✗ |
| 兴盛 | 9 | 0 | ✓ | ✗ |
| 心理魔法学院 | 1 | 0 | ✓ | ✗ |
| 安心妈妈 | 4 | 1 | ✓ | ✓ |

## 历史对比 (last 5 runs)

| 时间 | L1 P% | L2 P% | trigger |
|---|---|---|---|
| 2026-05-23T11:07:23 | 100.0% | 28.6% | efd6870: [A] feat(r4-p1 P1-1+P1-2): narrative prompt 真用 R4 + 4 badge 挂前端 |
| 2026-05-23T00:34:49 | 100.0% | 42.9% | 0845ba7: [A] feat(v2.5 ★ P0-1+P0-2): IngestPipeline 实时 trigger 接通 deriver+detec |
| 2026-05-22T15:10:18 | 100.0% | 42.9% | b0a07bd: [A] docs(v2.3 ★ 数据源矩阵): 9 板块 × 50 入口 × 7 维度 + 4 层印 |
| 2026-05-22T14:48:51 | 100.0% | 100.0% | e316e5d: fix(ai): 4 个 AI 服务层 P1 防御 [B3] |
| 2026-05-22T14:06:38 | 100.0% | 100.0% | B-verify-A-FINAL-syspath-fixed |

## 元信息

- model_used: `openclaw`
- overall_confidence: `0.84`
- 6 段生成数量: 6
- atomic_facts 客户行数: 1014

---

**触发**: 跑 `python3 scripts/run_v22_dual_layer_baseline.py [client_name]` 或 git post-commit hook 自动触发 (改 ingest/collector/generator/extractor).

**修 bug 路径**: 查 diagnosis 章节给的提示.