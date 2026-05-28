# 54-E · 全客户深读地基 · M0 基线报告(修复前冻结)

- 作者: E 线程 | 日期: 2026-05-26 | 分支: `feat/deep-read-foundation`
- 任务: 全客户自动深度索引与文档深读地基修复(M0-M9)的 M0——复现问题 + 冻结基线
- 方法: 只读真生产库(998 文档) + 本地语义探针(retrieve_dimension, 无 LLM 生成)
- 原始数据: `docs/E_DEEP_READ_M0_BASELINE_REPORT.json`
- 口径: deep_read_done = `document` 型 surrogate 数(深加工产物); never_queued = 没进过 `local_model_tasks` 的文档

## 全库基线(修复前)
| 指标 | 值 |
|---|---|
| v2_documents 总数 | **998** |
| 已深读(document surrogate) | **157 (15%)** |
| 从没入深读队列 | **909** |
| local_model_tasks queued | **124**(全部 stuck >24h) |
| failed | 2 |
| completed | 60 |

## 每客户基线(冻结对比表)
| 客户 | documents | deep_read | 覆盖率 | queued | stuck | never_queued | sem_hits | fallback | 状态 |
|---|---|---|---|---|---|---|---|---|---|
| **CFFC** | 185 | **157** | **84%** | 0 | 0 | 185* | **20** | 0 | **semantic-rich** |
| 日慈基金会 | 234 | 0 | 0% | 114 | 114 | 146 | 0 | 20 | fallback-rich · **reindex_required** |
| 为爱黔行 | 161 | 0 | 0% | 0 | 0 | 161 | 0 | 20 | fallback-rich · reindex_required |
| 益语智库 | 135 | 0 | 0% | 0 | 0 | 135 | 0 | 20 | fallback-rich · reindex_required |
| 云南儿童资助研究 | 126 | 0 | 0% | 0 | 0 | 126 | 0 | 20 | fallback-rich · reindex_required |
| 善加基金会 | 49 | 0 | 0% | 10 | 10 | 48 | 0 | 20 | fallback-rich · reindex_required |
| 乡村发展基金会 | 36 | 0 | 0% | 0 | 0 | 36 | 0 | 20 | fallback-rich · reindex_required |
| 新思考 | 32 | 0 | 0% | 0 | 0 | 32 | 0 | 20 | fallback-rich · reindex_required |
| 顾源源文章 | 26 | 0 | 0% | 0 | 0 | 26 | 0 | 12 | fallback-rich · reindex_required |
| 士平——足球 | 14 | 0 | 0% | 0 | 0 | 14 | 0 | 19 | fallback-rich · reindex_required |

\* CFFC 的 157 份深读 surrogate 不是走 local_model_tasks 队列建的(全库仅 89 文档进过该队列), 故 never_queued 仍计 185——印证"机制不统一、深读不靠单一可靠入口"。

## 复现的关键问题(M0 必测项, 全部复现 ✓)
| 问题 | 目标 | 复现 |
|---|---|---|
| 全库 998 / 深读 157 | 复现 | ✓ 998 / 157(15%) |
| 909 从没入队 | 复现 | ✓ 909 |
| local_model_tasks stuck | 复现 | ✓ 124 全 stuck >24h(日慈114+善加10) |
| 日慈 sem=0 | 复现 | ✓ sem=0, fallback-rich |
| 每客户覆盖统计 | 100% | ✓ 10 个有文档客户全覆盖 |

## 结论(冻结基线)
- **除 CFFC 外, 9 个有文档的客户深读覆盖率全为 0%, 全部 reindex_required。** 软件"深读每个客户"的核心价值只对 1/10 客户兑现。
- 深读机制**碎裂**(CFFC 不走队列建)、**积压**(124 卡 3 周)、**绝大多数从没排过**(909)、**无自愈** → 这是修复目标。
- 本表 = **修复前冻结基线**, M5(backfill)/M8(模块复测) 完成后用同一脚本(`scripts/run_deep_read_baseline.py`)复测对比。

## 下一步
M1 建统一 `deep_read_document` 入口 → M2 状态表 → M3 导入即入队 → M4 队列自愈 → M5 存量 backfill(先日慈/善加/CFFC) → M6 修签名 bug(日慈 sem>0) → M7 健康 API → M8 模块复测 → M9 报告。
