# 自动 eval · 双层 L1+L2 baseline · 日慈基金会

> 生成: 2026-05-22T14:06:38.444729+00:00 · 耗时 192s · trigger: B-verify-A-FINAL-syspath-fixed
> client_id: `client_284afd836e`
> dataset: 5/19 张真会议 7 关键词 (V2.2 阶段唯一 dataset)

## L1 vs L2 命中对比

| 维度 | 命中 | P% | 含义 |
|---|---|---|---|
| **L1** atomic_facts | 7/7 | **100.0%** | LLM extractor 抽到 + IngestPipeline 入库 |
| **L2** 6 段叙事 | 7/7 | **100.0%** | 用户在战略陪伴看到的内容 |

## 诊断

🟢 PASS — L1 + L2 都高, atomic_facts 有, 6 段也讲到

## 7 关键词逐项 (L1 vs L2)

| 关键词 | L1 atomic_facts 计数 | L2 6 段叙事计数 | L1 命中? | L2 命中? |
|---|---|---|---|---|
| 法人 | 1 | 3 | ✓ | ✓ |
| 理事长 | 2 | 5 | ✓ | ✓ |
| 强哥 | 2 | 6 | ✓ | ✓ |
| 秘书长 | 1 | 3 | ✓ | ✓ |
| 兴盛 | 7 | 3 | ✓ | ✓ |
| 心理魔法学院 | 1 | 3 | ✓ | ✓ |
| 安心妈妈 | 4 | 3 | ✓ | ✓ |

## 历史对比 (last 5 runs)

| 时间 | L1 P% | L2 P% | trigger |
|---|---|---|---|
| 2026-05-22T14:06:38 | 100.0% | 100.0% | B-verify-A-FINAL-syspath-fixed |
| 2026-05-22T13:57:55 | 100.0% | 0.0% | B-verify-A-FINAL-audit |
| 2026-05-22T12:15:34 | 28.6% | 0.0% | f5dde56: [A] feat(v2.2 ★ M-C.1): collector 放宽 status 过滤 + dogfood sys.path V2.1 |
| 2026-05-22T11:47:42 | 28.6% | 14.3% | M-G-task3-first-run |

## 元信息

- model_used: `openclaw`
- overall_confidence: `0.9`
- 6 段生成数量: 6
- atomic_facts 客户行数: 849

---

**触发**: 跑 `python3 scripts/run_v22_dual_layer_baseline.py [client_name]` 或 git post-commit hook 自动触发 (改 ingest/collector/generator/extractor).

**修 bug 路径**: 查 diagnosis 章节给的提示.