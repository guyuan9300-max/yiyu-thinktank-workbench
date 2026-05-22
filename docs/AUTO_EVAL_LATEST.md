# 自动 eval · 双层 L1+L2 baseline · 日慈基金会

> 生成: 2026-05-22T11:47:42.574896+00:00 · 耗时 117s · trigger: M-G-task3-first-run
> client_id: `client_284afd836e`
> dataset: 5/19 张真会议 7 关键词 (V2.2 阶段唯一 dataset)

## L1 vs L2 命中对比

| 维度 | 命中 | P% | 含义 |
|---|---|---|---|
| **L1** atomic_facts | 2/7 | **28.6%** | LLM extractor 抽到 + IngestPipeline 入库 |
| **L2** 6 段叙事 | 1/7 | **14.3%** | 用户在战略陪伴看到的内容 |

## 诊断

🔴 L1+L2 都低 → 系统性问题. 排查全链路: ingest_pipeline → document_llm_extractor → narrative_collector → narrative_generator

## 7 关键词逐项 (L1 vs L2)

| 关键词 | L1 atomic_facts 计数 | L2 6 段叙事计数 | L1 命中? | L2 命中? |
|---|---|---|---|---|
| 法人 | 0 | 0 | ✗ | ✗ |
| 理事长 | 1 | 2 | ✓ | ✓ |
| 强哥 | 0 | 0 | ✗ | ✗ |
| 秘书长 | 0 | 0 | ✗ | ✗ |
| 兴盛 | 1 | 0 | ✓ | ✗ |
| 心理魔法学院 | 0 | 0 | ✗ | ✗ |
| 安心妈妈 | 0 | 0 | ✗ | ✗ |

## 历史对比 (last 5 runs)

| 时间 | L1 P% | L2 P% | trigger |
|---|---|---|---|
| 2026-05-22T11:47:42 | 28.6% | 14.3% | M-G-task3-first-run |

## 元信息

- model_used: `openclaw`
- overall_confidence: `0.85`
- 6 段生成数量: 6
- atomic_facts 客户行数: 702

---

**触发**: 跑 `python3 scripts/run_v22_dual_layer_baseline.py [client_name]` 或 git post-commit hook 自动触发 (改 ingest/collector/generator/extractor).

**修 bug 路径**: 查 diagnosis 章节给的提示.