# E · 文档富化主链路重建 · M0 旧 pipeline 诊断固化

- 线程 E · 2026-05-27 · 实测固化(不再围绕 Qdrant / local_text_deep 旧链路盲修)
- 上游依据:`docs/E_SEARCH_STACK_QDRANT_FTS_SURROGATE_DEEP_TEST_REPORT.md`(61-E)
- 实测脚本:`scripts/e_deepread_shiping_benchmark.py`、`scripts/e_deepread_fullchain_huifeng.py`

## 0. 结论(为后续防回退)

**旧 deep-read 链路是多层断裂,不是单点慢。停止把"修旧 pipeline / 全量 Qdrant reindex"当主线。** 下一阶段转向新建 `DocumentEnrichmentService`,直接服务当前真实工作的检索层(surrogate/lexical + LIKE + v2_documents SQL)。Qdrant、document_cards、local_text_deep 全部降级为兼容层/技术债。

## 1. 旧链路断点(实测,逐层)

旧链路:`local_model_tasks(local_text_deep) → document_card_generation → document_cards → hydrate_missing_surrogates → Qdrant/coverage`

| 层 | 实测状态 | 证据 |
|---|---|---|
| UI 入口 | DeepReadSettingsCard 原本孤儿(本会话临时接入语音区);但点"自动解析"→ `PUT /local-ai/settings` **404** | 日志 404 |
| 后端控制面 | `/local-ai/settings`、`/coverage`、`/backfill` **全 404**;只有 health/queue/run-now 存在 | grep + 日志 |
| 任务 profile | card-gen 任务钉死 `model_profile_id='local_text_deep'`、`model_name=''`,该 profile 不可用 | 任务表 |
| **worker** | 汇丰 6 个 card-gen 任务 **status=queued / attempts=0**(从未被处理);全局 31 个 queued 全 attempts=0;30 分钟 worker 处理的是**别的客户**积压,不碰汇丰 | 全链路实测 |
| 全局切豆包 | **无效**——card-gen 按 per-task profile 路由,不看全局 provider | 实测(切 doubao 后汇丰仍 0) |
| document_cards | 多数客户 = 0(士平/益语/云南/为爱黔行/善加/汇丰),hydrate 无原料 | DB |
| hydrate | 依赖 document_cards;无卡片 → 0.1s 空转,0 产出 | 实测 |
| Qdrant | **全局零贡献**:7 客户 qdrant_hits=0;manifest master_indexed=0/stale;磁盘点数=0;populate 未闭环 | 61-E |

## 2. 当前真实可用的检索层

| 模块 | 走哪条 | 用 Qdrant? |
|---|---|---|
| 战略陪伴 | `knowledge_base.retrieve_knowledge_bundle`(surrogate/lexical + FTS + Qdrant) | 是,但=0;**仅 CFFC 有富 surrogate 语义**,其余靠 LIKE |
| 工作台问答 / 周复盘 / review_narrative / 分析 / 数据中心搜索 | `knowledge_v2.retrieve_knowledge_bundle` = **直查 v2_documents SQL** | 否 |

**真主力 = surrogate/lexical(仅 CFFC 富)+ LIKE + v2_documents SQL。**

## 3. CFFC 为什么能用(分水岭)

| 客户 | document_cards | document surrogate | 6 维语义 chunk(纯语义) |
|---|---|---|---|
| CFFC | 157 | 157 | 104 ✅ |
| 日慈 | 86 | 0 | 0 |
| 士平/益语/云南/为爱黔行/善加/汇丰 | 0 | 0 | 0 |

CFFC 是 pipeline 还能跑、profile 还配着的历史时期被处理过的**遗产**;现 pipeline 对新客户跑不动。差异在 `knowledge_master_index.searchable_text` 充实度(CFFC avg 855 字 vs 其余 ~230)。

## 4. 本轮不做 / 要做

**不做**:全库 backfill;继续救 local_text_deep;把 document_cards 当必需前置;以 Qdrant 命中为验收;污染 confirmed facts。

**要做(M1+)**:建 `DocumentEnrichmentService`,链路(schema 已验证 v2→kd→surrogate→master_index 汇丰 6 篇全通):
```
v2_documents.markdown_content(真正文,汇丰 6 篇 1.9k–19k 字)
  → 豆包富化(复用 ai_service.generate_memory_surrogate / enrich_retrieval_summary)
  → 写 knowledge_surrogates(rich 字段)+ UPDATE knowledge_master_index.searchable_text/retrieval_summary(写厚 ≥700 字)
  → 直接被 bundle/lexical + v2_documents 检索读到
  → 战略陪伴 / 工作台问答 / documents.generate 命中
状态记录复用 document_deep_read_states(已存在)
```
**不以 Qdrant 为验收。**

## 5. 关键表/字段(M1 写入目标)
- 读正文:`v2_documents.markdown_content`(fallback doc_index_text/preview_text)。
- 写厚(检索打分读这个):`knowledge_master_index.searchable_text` + `retrieval_summary`。
- rich 字段:`knowledge_surrogates.{overview_summary,retrieval_summary,distinct_findings_json,entities_json,time_markers_json,query_hints_json}`。
- 状态:`document_deep_read_states`(复用)。
- LLM:走豆包(全局 provider=openai_compatible + model doubao-seed-2-0-pro,ready)。**不走 local_text_deep**。
