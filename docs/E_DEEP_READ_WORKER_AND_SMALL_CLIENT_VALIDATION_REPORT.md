# 56-E · 深读 Worker 与小客户端到端验证报告

- 作者: E 线程 | 日期: 2026-05-26 | 分支: `feat/deep-read-foundation`(未合 main)
- 范围: M1 document_card worker 修复 + 士平端到端验证 + 日慈首批诊断

## 结论口径: **B — 士平端到端通过(机制证明成立); 日慈首批未完成(队列被消费, 需重置+新鲜card重跑); 不允许直接全量 backfill**
机制已在士平证明成立; 日慈路径清晰但需一轮新鲜 card 跑; 全量 backfill 另需 worker 提速/降失败率。**不写"深读地基最终完成"。**

---

## 1. 本轮最大成果: 找到并修复深读总根 bug
**`_process_document_card_task` 调 `ai_service.generate_local_model_json()` —— 该方法全仓从未定义**。所以 document_card_generation 任务**从第一天就 AttributeError 必失败** → 队列卡 3 周 → 无 document_cards → 无饱满 surrogate → 全客户 sem=0。
- **修复(commit `d6111f4`)**: 改用真实存在的 `_qwen_generate`(本地 qwen, 返 JSON) + `_DOCUMENT_CARD_SCHEMA`。
- 一个未实现的方法名, 拖垮了所有客户的深读。

## 2. 士平 14 篇端到端验证: ✅ 全过
| 指标 | 改前 | 改后 | 目标 |
|---|---|---|---|
| document_cards | 0 | **14 (100%)** | ≥90% ✓ |
| surrogate 均长 | 229 字 | **968 字** | ≥700 ✓(超 CFFC 855) |
| 语义探针 sem>0 维度 | 0/5 | **5/5** | ≥3/5 ✓ |
| business_intro | 空(0) | semantic(12) | 不空 ✓ |

**链路证明成立**: 修复后 worker → document_cards → hydrate 饱满 surrogate → reindex → 语义检索 sem>0。这是深读地基机制的端到端实证。

## 3. 日慈首批: 未完成, 原因清楚(非新拦路虎)
- worker batch0 processed=0/队列空: 日慈 114 个 queued document_card 任务**被早前(修复前)broker worker 消费**(worker 不按客户过滤, claim 了日慈的也全失败) → 现 completed 54 / failed 34 / queued 0 → 无新鲜 card 可建。
- 日慈 surrogate 仍 **234 字薄**(用旧 88 card, hydrate 非force 未重建) → 语义仍 0/6。
- **对比士平(新鲜 card→968字→sem 5/5)**: 日慈只差"新鲜饱满 card"这一步。
- **修法(机制同士平, 无新未知)**: 重置日慈 document_card 任务为 queued → 修复后 worker 跑新鲜 card → `hydrate(force_refresh=True)` 富化 → reindex → 探针。

## 4. 性能现实(全量 backfill 前必须解决)
- 士平 14 篇耗时 **36 分钟**(47 成功 + 72 失败重试; LLM 偶发非-JSON 被重试恢复, 最终 14/14 完成)。
- 折算 ~18s/任务 + 高单次失败率 → **日慈 234 篇≈数小时, 全量 841≈数十小时**, 不调速/降失败率无法全量。
- 待优化: 降 LLM 非-JSON 失败率(更稳 schema/解析) + 并发/限流 + 跳过已 completed。

## 5. 已交付(feature 分支 feat/deep-read-foundation, 未合 main)
```
8016f7c M0 深读基线冻结(998文档/157深读/909没入队/124卡死)
91fac96 M1+M2 deep_read_service 状态机 + document_deep_read_states 状态表
4407984 M6 检索命门(retrieve_knowledge_bundle 传 db, 修写active/查legacy错位; CFFC sem=20无回归)
d6111f4 M1 worker 命门(generate_local_model_json 未实现 → 改 _qwen_generate); 士平 e2e 5/5
0210b57 验证脚本(士平 PASS / 日慈诊断)
```
副产品: **士平已成为真·深读客户**(document_cards 14, 饱满 surrogate, 语义可检索)。

## 6. 是否允许全量 backfill: 否
| 条件 | 状态 |
|---|---|
| 士平端到端通过 | ✅ |
| 日慈首批通过 | ❌(需重置队列+新鲜card重跑) |
| worker 稳定/提速 | ❌(36min/14篇, 失败率高) |
→ 先做: (1)日慈重置+新鲜card跑通 (2)worker 降失败率+提速; 两者过了再分批全量。

## 7. 剩余(本轮未做, 后续)
- M4 处置 stuck/dead_letter 队列(日慈 34 failed 重置) + worker 提速降失败。
- M5 导入即入队(各导入口接 enqueue)。
- M6 deep-read-health API。
- M7 模块复测(战略陪伴/工作台/documents.generate 的 before/after)。
- 全量分批 backfill(gated)。

## 8. 一句话
**深读地基的总根 bug 已找到并修复, 并在士平上端到端证明"worker→card→饱满surrogate→语义命中"成立。** 剩下是"把同一机制可靠地、提速地跑给日慈和全量"——清晰的工程活, 无新未知。
