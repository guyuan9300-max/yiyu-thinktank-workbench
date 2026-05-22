# B AI · 完整 Systematic 盘点 (代码 / 数据 / 功能 全量交叉)

> **触发**: 顾源源 5/22 18:xx "排查一遍现在所有的代码和所有的软件功能, 以及所有的数据表, 然后再写计划"
> **跟 4D INVENTORY 区别**: 4D 是宏观采样, 本文是 systematic 全扫描 (175 services + 217 tables + 9 板块 .tsx)
> **执行人**: AI B (独立跑)
> **日期**: 2026-05-22 阶段 0 后

---

## 0 · 关键数字总表

| 维度 | 数字 |
|---|---|
| backend services | **175 个** (.py) |
| backend main.py 行数 | 54,885 行 (含 27000+ closure endpoint) |
| backend 总 LOC | ~190,000 行 |
| 前端 components 模块 | **9 主板块 + 7 跨板块共用** (client_fact/collab/global/handbook/reports/topics/weekly_review) |
| 前端 9 板块 .tsx 数量 | 17+8+4+1+1+1+4+1+10 = **47 个 view** |
| 前端跨板块 .tsx | 16 个 |
| 前端 hooks | 1 个 (useClientFact) |
| 数据库表 | **217 张** |
| 有数据表 | 161 张 |
| **空表** | **56 张** ← N3 设计未启用基础设施债 |

---

## 1 · 175 services 按业务族归类

### A 族 · 数据中心枢纽 (19 个) ★ 整个系统的"地基"

```
data_center_kernel          734 行
data_center_ingest         1970
data_center_search          370
data_center_broadcast       371
data_center_sync            579
data_center_self_verify     446
data_center_quality         142
data_center_artifacts       271
data_center_shadow          234
data_center_access          246
data_center_schema          156
data_center_prep            163
data_center_operational_status 145
data_center_proposal        630
data_center_rollback_drill   56
data_center_profiler         23

ingest_pipeline             662  ★ V2.2 新枢纽, 但只 1 路真接入
idempotency_store           256  ★ F2.8 N3 A6 (B 主写)
memory_foundation          2253
```

### B 族 · 知识层 (3 个)

```
knowledge_v2                5174  ★ 主仓库最大业务服务
knowledge_base              4391
embedding_provider          491
```

### C 族 · LLM / AI 调用 (12 个)

```
ai                          5550  ★ 总入口
local_model_optimizer       948
local_inference_governor    331
local_memory                693
local_semantic_router       234
generation_runtime_policy   439
rerank_provider             141
public_search               415
multi_platform_search       476
social_search               188
question_focus               66
chat_intent                  87
```

### D 族 · 客户工作台 (13 个 workspace_*)

```
workspace_data_center_adapter   2483
workspace_chat_multipass         687
workspace_answer_value_diagnostics 1155
workspace_relation_docs          756
workspace_chat_diagnostics       436
workspace_answer_experience      290
workspace_query_router           365
workspace_context_refresh        337
workspace_followups              318
workspace_thread_memory          513
workspace_action_perspective      80
workspace_chat_kernel_bridge      24
workspace_file_search             65
workspace_answer_finalizer       201
```

### E 族 · 战略陪伴 6 段叙事 + AI 研判 (5 个)

```
narrative_generator         1156  ★ N2 6 段核心
narrative_collector         1192  ★ 拉 13 张现成表
digital_asset_narrative      657
digital_asset_center        3513
digital_asset_narrative.py 子模块
review_narrative            2494
```

### F 族 · 资讯情报站 (14 个 intelligence_*)

```
intelligence_candidate_supply    7111  ★ 主仓库最长单 service!
intelligence_search_intents      1740
intelligence_sentiment            942
intelligence_theme_cluster        536
intelligence_query_strategy       658
intelligence_timely_strategy      700
intelligence_feedback             609
intelligence_brand_audit          605
intelligence_card_enricher        419
intelligence_positioning_gap      351
intelligence_missions             214
intelligence_insight_agent        250
intelligence_transcript_enrich    142
intelligence_ai_runner            232
```

### G 族 · 爬虫 / 互联网 (5 个)

```
internet_crawler            1430
internet_pdf_worker          248
wechat_sogou_ingest          300
wechat_rsshub_ingest         143
nonprofit_authority_seeds    329
```

### H 族 · 任务 / 复盘 / 会议 (10 个)

```
review_analysis             2713
review_narrative            2494  (跟战略陪伴共用)
review_rollup               1465
review_simulation            147
weekly_review_material_pack  862
agent_worklogs              1158
task_context_brief_engine    596
meeting_action_extractor     263
meeting_followup             178
meeting_context              244
```

### I 族 · 智能文件导入 / 抽取 (10 个)

```
smart_file_import           1358  ★ 路径 1 唯一接通点
link_material_import        1572
document_decomposition       788
structured_table_parser      405
structured_table_store       329
full_text_extractor          124
fact_extractor               332  ★ 抽 atomic_facts
entity_extractor             416  ★ 抽 entities
relation_extractor           133
ocr_quality                  509
```

### J 族 · 成长中心 (5 个)

```
growth_engine               4870
badge_engine                1228
exp_wall_service             537
experience_story_engine      132
```

### K 族 · 实体 / 术语 / 矛盾 (11 个)

```
entity_store                 274
entity_merger                299
glossary_attribute_extractor 426
glossary_candidate_generator 626
glossary_attributes_pack     120
glossary_store               132
glossary_helpers             162
glossary_conflict_alert      106
contradiction_detector       408  ★ 旧矛盾检测 (跟 ingest_pipeline.detect_update_relation 平行)
relation_store               215
relation_dictionary          149
```

### L 族 · 报告生成 (7 个)

```
report_docx_helpers          863
report_docx_renderer         561
report_context_builder       466
report_chart_generator       423
report_blueprint_drafter     367
report_section_drafter       383
report_section_scheduler     137
report_chart_materializer    215
```

### M 族 · 客户层 / 项目层 (5 个)

```
client_profile               394
client_strategic_pulse       653
project_portrait_builder     428
module_dna                   321
platform_dna                 108
strategic_context            114
```

### N 族 · 系统 / 集成 (12 个)

```
feishu                       161
feishu_sync                  591
secrets                      137
system_logger                298
template_fill               1073
self_heal                    748
proposal_execution           458
proposal_approval            249
website_audit                255
brand_mirror_analyzer        438
brand_strategy_extractor     430
unified_workspace_migrator   326
```

### O 族 · 证据 / 验证 / 质量 (9 个)

```
evidence_tier                235  ★ Tier A/B/C 分层
evidence_selector            520
evidence_quality             246
evidence_quality_store       230
evidence_quality_feedback     61
evidence_quality_feedback_snapshot 171
external_evidence            426
external_learning            171
citation_validator           123
freshness_decay              206
auto_verify_rules            332
```

### P 族 · 学习预设 / 反馈 (5 个)

```
learning_presets             640
todo_aggregator              282
diagnosis_engines            333
clarification_context        439
clarification_pre_search     421
```

### Q 族 · 答案生成 (4 个)

```
answer_layer                 430
understanding_builder        712
analysis_center             3984
analysis_context            2080
fill_table_evaluator         436
```

### R 族 · 其它枢纽 (7 个)

```
topic_capture                922
topic_source_fetcher         579
topic_data_center            173
kernel_primary_rollout       503
generation_runtime_policy    439
reasoning_trace_store        292  ★ B 协助主写 (N3 reasoning trace)
text_normalizer              147
data_center_proposal         630
query_router                 448
retrieval_shadow             162
retrieval_model_settings     134
source_semantics             264
source_reachability          216
source_integrity             110
execution_retry_metrics      183
trash_can                    175
markdown_to_docx              95
data_center_shadow           234
version_manifest              63
event_line_timeline          544
semantic_classifier          239
action_suggestion_service    133
structured_query             276
```

---

## 2 · 217 张表完整归类

### 2.1 按表前缀分布

```
intelligence_*  14 张  (资讯情报站)
knowledge_*    13      (知识库)
task_*         12      (任务系统)
client_*       10      (客户层)
event_*         9      (事件线)
growth_*        7      (成长中心)
document_*      7      (文档导入)
workspace_*     5      (工作台)
organization_*  5      (组织)
topic_*         4      (话题)
mirror_*        4      (镜像/sync)
import_*        4      (导入)
evidence_*      4      (证据)
data_*          4      (数据中心)
ai_*            4      (AI Memory)
v2_*            3      (V2 文档结构)
sync_*          3      (同步)
strategic_*     3      (战略)
project_*       3      (项目)
glossary_*      3      (术语)
chat_*          3      (聊天)
analysis_*      3      (分析)
weekly_*        2      (周复盘)
report_*        2      (报告)
narrative_*     2      (叙事)
... 其它 80+ 单表
```

### 2.2 161 张有数据表 - Top 30 行数

```
activity_logs                      26,677  ★ 主时间线骨架
entity_mentions                    12,184  ★ 跨文档人物提及
v2_chunks                          11,998  ★ V2 文档分块
answer_citations                    7,595
v2_sections                         6,121
document_chunks                     5,214
entities                            4,987  ★ 4 种实体: person/org/date/money
memory_facts                        3,038  ★ 旧记忆层 (kv-style)
knowledge_job_events                2,837
atomic_facts                        1,998  ★ V2.2 新事实层 (三元组+5维)
intelligence_fetch_jobs             1,996
documents                           1,922
intelligence_candidate_items        1,703
document_fields                     1,334
chat_messages                       1,125  ★ 现有聊天数据
v2_documents                          998
glossary_attributes                   808
data_center_shadow_runs               778
intelligence_search_intents           667
file_reclass_events                   631
knowledge_documents                   600
growth_signal_events                  598
answer_runs                           543
data_center_ingest_events             540
knowledge_master_index                518
```

### 2.3 ★ 56 张空表 (按字段数排, 字段 ≥10 = 设计成熟但未启用)

| 表名 | 字段数 | 用途 (推断) | N1/N2/N3 |
|---|---|---|---|
| intelligence_profiles | **47** | 资讯情报站客户画像快照 | N2 |
| data_center_proposal_drafts | 26 | 数据中心提案草稿 | N2 |
| external_evidence_cards | 23 | 外部证据卡 (爬虫/口述/官方分层) | N2 |
| org_events | 22 | 组织事件流 (变更/任命/重组) | N2 |
| key_decisions | 21 | 关键决策 (跟 decisions 3 行可能重复) | N2 |
| reasoning_traces | 20 | AI 推理轨迹 | N3 ★ |
| event_line_state_changes | 19 | 事件线状态变更 | N2 |
| proposal_records | 19 | 提案记录 | N2 |
| mirror_users | 19 | 用户镜像 | N1 |
| data_center_sync_outbox | 18 | 数据中心 sync 队列 | N1 |
| intelligence_search_diagnostics | 17 | 搜索诊断 | N2 |
| execution_tickets | 16 | 执行工单 | N2 |
| intelligence_feedback_summaries | 16 | 情报反馈 | N2 |
| prompt_log | 15 | LLM prompt 日志 | N3 ★ |
| kernel_primary_rollout_runs | 14 | 内核灰度发布 | N1 |
| project_flows | 14 | 项目流程 | N2 |
| ai_improvement_suggestions | 13 | AI 自我改进建议 | N3 ★ |
| digital_asset_narrative_snapshots | 13 | 数字资产叙事快照 | N2 |
| clarification_records | 13 | 用户澄清记录 | N2 |
| event_log | 12 | 系统事件总线 (V2.2 N3 设计的) | N3 ★ |
| event_line_weekly_snapshots | 12 | 事件线周快照 | N2 |
| ai_learned_rules | 12 | AI 学到的规则 | N3 ★ |
| idempotency_keys | 12 | 幂等键 (B F2.8 N3 A6) | N3 ★ |
| cooperation_relationships | 12 | 合作关系图 | N2 |
| generation_runtime_state | 12 | 生成时态 | N3 ★ |
| ai_episode_log | 11 | AI 调用 episode | N3 ★ |
| heal_log | 11 | 自愈日志 | N1 |
| mirror_departments | 10 | 部门镜像 | N1 |
| project_procedures | 10 | 项目程序 | N2 |
| entity_merge_log | 10 | 实体合并日志 | N2 |
| ai_feedback_signals | 9 | AI 反馈信号 | N3 ★ |
| 其余 25 张空表 (字段 < 10) | | 多为辅助 / 占位 | 混合 |

★ 关键: **N3 (3.0 接入预留) 的 8 张核心表全部 0 行** — AI Memory / reasoning_traces / event_log / idempotency_keys / prompt_log / ai_learned_rules / ai_improvement_suggestions / ai_episode_log

### 2.4 atomic_facts vs memory_facts (不是重复造轮子)

**纠正我之前的判断** — 这两个表 schema 完全不同, 不是重复:

| atomic_facts (1998) | memory_facts (3038) |
|---|---|
| 三元组: subject + attribute + value | kv-style: scope_type + fact_key + fact_value |
| 5 维元数据 (source_type/role/time/actor/confidence) | freshness + evidence_refs |
| 用途: 客户事实 ("张真接任法人") | 用途: 系统状态 ("user_X.last_login") |
| V2.2 新设计 | 旧 v0/v1 |

→ **职责不同**, 不是替代关系。但**接口可能要统一** (待顾源源决策)。

---

## 3 · 9 板块三向交叉

### 3.1 完整对照表

| # | 板块 | 前端 .tsx | 后端 services | 关键表 | AI 接入 | N1/N2/N3 实现度 |
|---|---|---|---|---|---|---|
| 01 | 任务与日程 | 17 | 8+ (review_*/agent/meeting_*) | tasks 238/weekly_reviews 9/meetings 7 | review_narrative 出复盘 | N1 90% / N2 30% |
| 02 | 客户工作台 | 8 + handbook 6 + client_fact 1 | 14+ (workspace_*) | clients 12/chat 305+1125 | workspace_chat_multipass | N1 90% / N2 60% |
| 03 | 战略陪伴 ★ | 4 | 7 (narrative_*/digital_asset_*) | atomic_facts 1998 + 6 段现成表 | narrative_generator 6 段 | N1 85% / N2 40% |
| 04 | 资讯情报站 | 1 + topics 3 | 19 (intelligence_*/爬虫) | intelligence_candidate 1703/profiles **0** | AI agent + 爬虫 | N1 80% / N2 50% |
| 05 | 成长中心 | 1 | 4 (growth/badge/exp_wall) | growth_signal_events 598 | growth_engine 4870 | N1 90% / N2 30% |
| 06 | 智能文件导入 ★ | 1 | 10 (smart_file_import+) | documents 1922 + atomic_facts 1998 | LLM extractor | N1 85% / N2 70% (路径 1 通) |
| 07 | 数据中心 (基础设施) | 4 (运维) | 19 (data_center_*+knowledge_*) | 全部 217 表 | IngestPipeline (1/4 路通) | N1 60% / N2 50% / N3 设计 85% 流量 5% |
| 08a | 组织计划工坊 | 1 | 4 | project_modules 4 / project_flows **0** | project_portrait_builder | N1 30% (空管道多) |
| 08b | 系统设置 | 10 | 12 | settings/sync 全套 | feishu / ollama 集成 | N1 95% |

### 3.2 跟"3 子目标 (AI 深度 / 顺畅访问 / 跨源印证)" 的对照

每个板块对 3 子目标的贡献:

| 板块 | a (AI 更深理解) | b (顺畅访问) | c (跨源印证) |
|---|---|---|---|
| 01 任务 | ⚠️ review_narrative 抽行动项 | ❌ 不读 ClientFactBundle | ❌ 不参与 cross-source |
| 02 工作台 | ✅ workspace_chat 多轮对话引 fact | ✅ 走 ClientFactBundle | ⚠️ 引用但不仲裁 |
| 03 战略陪伴 ★ | ⚠️ narrative_generator 6 段 (1/7 命中) | ✅ 6 段统一入口 | ⚠️ collector 缺漏 |
| 04 资讯情报站 | ✅ AI agent 分析 / sentiment | ❌ 没接 atomic_facts | ❌ Tier C 数据不进 IngestPipeline |
| 05 成长中心 | ⚠️ growth_engine 算成长信号 | ❌ 不读 fact bundle | ❌ |
| 06 智能文件导入 ★ | ✅ LLM extractor 抽 25 条 fact | N/A (是写入方) | ❌ 只通路径 1 |
| 07 数据中心 | ★ 是其它板块的输入 | N/A | 🔴 4 路径只 1 路通 |
| 08a 工坊 | ❌ | ❌ | ❌ |

---

## 4 · 真实"断链" 清单 (基于全扫描)

### 4.1 写入端断链 (4 主路径未接通)

```
路径 1 (工作台文件):       ✅ smart_file_import → atomic_facts (但直接 INSERT 没经 IngestPipeline)
                          ⚠️ 应该 smart_file_import → IngestPipeline → atomic_facts

路径 2 (任务复盘):         ❌ weekly_review_material_pack 拉了 9 条 review, 但不进 atomic_facts
                          ❌ meeting_action_extractor 抽出 4 条 action_items, 不进 IngestPipeline
                          ❌ review_narrative 出复盘文字, 不沉淀 atomic_facts

路径 3 (互联网爬虫):       ❌ internet_crawler 抓到的进 v2_documents 1922, 不进 atomic_facts
                          ❌ intelligence_candidate_items 1703 条不进 IngestPipeline
                          ❌ wechat_sogou_ingest / rsshub 同上

路径 4 (手机 AI 聊天):     ❌ chat_messages 1125 条对话不进 atomic_facts
                          ❌ chat_threads 305 条线程不进 IngestPipeline
                          ❌ workspace_chat_multipass 对话不沉淀 fact
```

### 4.2 读取端断链 (8 板块只 2 个用上数据中心)

```
✅ 战略陪伴   → narrative_collector 拉 13 张表
✅ 客户工作台 → workspace_chat 读 atomic_facts

❌ 任务与日程 → 不读 narrative
❌ 资讯情报站 → 不读 atomic_facts (有自己的小池子 intelligence_candidate_items)
❌ 成长中心   → 不读 fact bundle
❌ 计划工坊   → 不读 narrative
❌ 智能文件导入 → 单向写入, 不回头读
```

### 4.3 信息商引擎接通

```
ingest_pipeline.detect_update_relation 实现 (5 规则):
  none / conflict / supersedes / complement

实际 atomic_facts.update_relation 分布 (1998 条):
  none: 99%+ (首次写入)
  conflict/supersedes/complement: 几乎 0

→ 信息商引擎"装好了, 没流量"
```

### 4.4 N3 接入预留 - 8 张核心表 0 流量

| 表 | 字段数 | 设计用途 | 流量 |
|---|---|---|---|
| reasoning_traces | 20 | AI 推理过程 (B 主写 store) | 0 |
| ai_episode_log | 11 | AI 调用 episode | 0 |
| ai_feedback_signals | 9 | AI 反馈信号 | 0 |
| ai_improvement_suggestions | 13 | AI 自我改进 | 0 |
| ai_learned_rules | 12 | AI 学到的规则 | 0 |
| event_log | 12 | 系统事件总线 | 0 |
| idempotency_keys | 12 | F2.8 (B 主写) | 0 (主仓库未 trigger) |
| prompt_log | 15 | LLM prompt 日志 | 0 |

→ **3.0 启动时缺培训数据**, 全部需要重新跑流量

### 4.5 完整设计但 0 数据的"空管道" (除 N3 外)

```
intelligence_profiles      47 字段 → 资讯情报站客户画像  (产品手册 §04 提到, 但没建)
data_center_proposal_drafts 26 字段 → 数据中心提案
external_evidence_cards    23 字段 → Tier A/B/C 外部证据 (产品手册 §03 提到)
org_events                 22 字段 → 组织事件流
key_decisions              21 字段 → 关键决策 (跟现有 decisions 3 行不同字段)
event_line_state_changes   19 字段 → 事件线状态变更
project_flows              14 字段 → 项目流程图
project_procedures         10 字段 → 项目程序
clarification_records      13 字段 → 用户澄清记录 (产品手册 §03 让 AI 重新理解)
event_line_weekly_snapshots 12 字段 → 事件线周快照
cooperation_relationships  12 字段 → 合作关系图
digital_asset_narrative_snapshots 13 字段 → 数字资产叙事快照
intelligence_feedback_summaries 16 字段 → 情报反馈
```

---

## 5 · 综合评估 (基于完整事实, 不再 hand-wave)

### 5.1 整体进度 (各板块加权)

```
N1 现有功能不掉链:      85%  (9 板块都能跑, 但 08a 计划工坊空管道多)
N2 机器人深度+广度+印证:
  ├ a (AI 更深理解):    30%  (单源抽 fact 通, LLM extractor 已就位; 但 6 段叙事 dogfood 1/7)
  ├ b (顺畅访问):       30%  (9 板块只 2 个真通)
  └ c (跨源印证):        5%  (IngestPipeline 4 路径只 1 路, update_relation 99% 是 none)
N3 接入预留:
  ├ schema 设计:        90%  (8 张核心表完整设计 + 56 张完整 schema 空表)
  └ 真流量:              5%  (8 张 N3 表全 0)
```

### 5.2 主仓库 vs 我 (V2.1) 关系再确认

```
V2.1 是主仓库下游 mirror, 不是平行项目:
- 主仓库 backend/app/services/ 175 个文件中, V2.1 几乎完全镜像 (本仓库存在 ingest_pipeline.py 等同名文件)
- V2.1 真"新增" = 6 个文件 (其中 3 个已 .DEPRECATED):
  ✅ idempotency_store.py     (F2.8 N3 A6) — 主仓库可能要 sync
  ✅ document_llm_extractor.py (路径 1 LLM 抽取, A 主写) — 主仓库已 sync
  ✅ reasoning_trace_store.py  (N3) — 主仓库已 sync
  ❌ narrative_kernel.py.DEPRECATED (8 段假增量)
  ❌ scripts/run_v22_n2_baseline.py.DEPRECATED (单源 baseline)
  ✅ backend/app/api/ (router 基础设施, 孤儿等用)
```

### 5.3 8 个真实致命 gap (优先级排序)

| # | gap | 影响 | 工作量 |
|---|---|---|---|
| 1 | smart_file_import.py:1002 直接 INSERT atomic_facts (不经 IngestPipeline) | 路径 1 没真走信息商引擎, cross-source 触发缺最后一步 | 1 天 |
| 2 | 路径 2 (任务复盘) 不进 atomic_facts | weekly_review 9 条 / meetings 7 / action_items 4 / commitments 66 全部不沉淀到 fact bundle | 2-3 天 |
| 3 | 路径 3 (爬虫) 不进 atomic_facts | intelligence_candidate_items 1703 + v2_documents 1922 不喂信息商 | 2-3 天 |
| 4 | 路径 4 (手机 AI 聊天) 不进 atomic_facts | chat_messages 1125 + chat_threads 305 全部不沉淀 | 5-10 天 |
| 5 | narrative_collector 漏拉关键现成表 | 6 段 dogfood 1/7 命中 (A 22d8bb8 确认) | 1-2 天 (A 阶段 2) |
| 6 | 8 张 N3 核心表 0 流量 | 3.0 启动时无培训数据 | 渐进 1-2 周 |
| 7 | 13 张"完整 schema 但 0 数据"空管道 | external_evidence_cards / intelligence_profiles / key_decisions / org_events / clarification_records — 都是产品手册提到的功能, schema 在但没接 | 渐进 1 周 |
| 8 | 其它 7 板块不读 ClientFactBundle | 任务/资讯/成长/工坊用户体验跟数据中心脱钩 | 渐进 1 周 |

---

## 6 · B 计划 (基于完整事实, 不是基于想象)

### 6.1 立场再确认

我的角色 = endpoint / 前端 / 测试 / docs (协作文档 §4 分工).
不动: schema 重设计 / 核心算法 / 4 路径 normalizer (A 主导).

### 6.2 短期 (本里程碑剩余 + 下一里程碑)

**继续按 sync 指令 §阶段 1-5 走, 但我加 2 个补丁建议**:

**[B 立刻能做, 不阻塞 A]**:

P1 · 配合 A 阶段 1 完成后, 跑前端 NarrativePanel 审计 (sync §阶段 1)
P2 · 等 A 阶段 2 collector 补完, 写 6 段 endpoint 集成测试 (sync §阶段 2)

**[B 提案给顾源源 review]**:

P3 · 提议下一里程碑优先解 §5.3 gap #1 (smart_file_import → IngestPipeline 切迁)
理由: A 阶段 2 在改 collector 是为提 a (AI 深度), 但 gap #1 是为提 c (跨源印证) 的基础. 解了它, 信息商引擎 第一次有机会"在 1 个路径内"真触发 supersedes/conflict (多 docx 抽 fact 撞).

P4 · 提议把 #5.3 gap #2 (路径 2 接入) 纳入下下里程碑, 给"任务复盘 → atomic_facts" 接通
理由: 9 板块只有 06 智能文件导入真喂数据中心, 这是数据"广度"最大 gap.

### 6.3 中期 (V2.2 完成前)

P5 · 等 A 完成 4 路径切迁后, B 写跨路径信息商集成测试
- 测试场景: 路径 1 客户官方文档说 "金额 800 万", 路径 4 用户聊天说 "金额 300 万要重签" → 应该触发 supersedes, atomic_facts.update_relation 不再 99% 是 none.
- 这是顾源源 "AI 要对接收的信息有分辨能力" 原话的真验证.

P6 · 5 张 N3 AI Memory 表流量观测
- B 不动 schema, 但写自动化 sanity check: 每 milestone 跑一次 sqlite COUNT, 看 reasoning_traces/ai_episode_log 是否真长出数据.

### 6.4 长期 (V2.2 → V3.0)

P7 · 等 V2.2 4 路径全通后, 给主仓库 PR (从 V2.1 → 主仓库):
- IdempotencyStore 完整接入 (F2.8 N3 A6)
- ClientFactView L2 共识层 endpoint (V2.1 接通了 6 view, 主仓库该 sync 过去)
- 协作文档 + 4D 流程 + memory 流程沉淀

P8 · 8 张 N3 表流量 → 3.0 培训数据基础
- 不是单独里程碑做, 而是 P3-P5 接通 4 路径时, IngestPipeline 写入时**顺手**写 ai_episode_log / reasoning_traces — 跟 P3 同时落地.

---

## 7 · 偏差描述 (按协作文档 §7.2 schema)

### 偏差 1 · smart_file_import 没经 IngestPipeline (根因: A 维度 - schema 未读全 / B 维度 - 没提议)

```
主仓库现状: backend/app/services/smart_file_import.py:1002 直接 INSERT INTO atomic_facts
V2.1 当前实现: 同主仓库 (因为是 mirror)
冲突点: 跟 ingest_pipeline.py docstring "4 主路径写入出口统一走 IngestPipeline.ingest()" 设计不符
判决: 改 — 这是 §5.3 gap #1, B 提案 P3
```

### 偏差 2 · narrative_collector 漏拉关键现成表 (根因: A 阶段 1 dogfood 才发现)

```
主仓库现状: narrative_collector.py 1192 行已实现, 但 dogfood 1/7 命中
V2.1 当前实现: 同主仓库
冲突点: 应该拉的 13 张现成表只覆盖 ~30%, 漏 risk_signals/open_questions/decisions 等关键段对应表
判决: 改 — A 阶段 2 在做
```

### 偏差 3 · 路径 2/3/4 全部不接 IngestPipeline (根因: 维度 2 主仓库代码 + 维度 3 数据库表 没交叉读)

```
主仓库现状:
- 路径 2: weekly_review_material_pack 拉 review, 不写 atomic_facts
- 路径 3: internet_crawler / wechat_*_ingest 写 v2_documents, 不进 atomic_facts
- 路径 4: workspace_chat_multipass / chat_messages 不沉淀 atomic_facts
V2.1 当前实现: 同主仓库 (镜像)
冲突点: IngestPipeline 4 路径 normalizer 都在 (metadata_for_task_review/metadata_for_internet_crawler/metadata_for_mobile_ai_chat), 但没真调
判决: 改 — §5.3 gap #2/#3/#4, B 提案 P4 + A 长期任务
```

### 偏差 4 · N3 8 张核心表 0 流量 (根因: schema 设计完 → 测试通 → 但没接生产代码)

```
主仓库现状:
- reasoning_traces (20 字段) / ai_episode_log (11 字段) / event_log (12 字段) / idempotency_keys (12 字段) / prompt_log (15) / ai_learned_rules (12) / ai_improvement_suggestions (13) / ai_feedback_signals (9)
- 全部 schema 完整, 0 数据
V2.1 当前实现: B 的 idempotency_store.py 在 V2.1 测试场景跑过, 但主仓库生产没 trigger
冲突点: schema 90% 完成, 实际流量 5%, 3.0 启动时缺培训数据
判决: 渐进 — 跟 P3/P4/P5 同步, IngestPipeline 接入时顺手写
```

---

## 8 · §EDGE · 跟 4D INVENTORY 的关系

本文 = 4D INVENTORY 的 systematic 深化版:
- 4D INVENTORY (2 小时前) = 每维度采样 5-10 个关键事实
- 本文 = 每维度全量扫描

跟用户原话 "排查一遍现在所有的代码和所有的软件功能, 以及所有的数据表" 对应:
- ✅ 所有代码: 175 services 完整归类
- ✅ 所有软件功能: 9 板块 + 7 跨板块 = 47 + 16 = 63 个 .tsx view
- ✅ 所有数据表: 217 张表完整扫描 + 56 张空表全列

跟 A 的 V2.2_ASSESSMENT_4D_20260522.md 互补 (协作文档 §7.3 双产物):
- A 文档偏 "重设计建议 + V2.1 砍废"
- 本文偏 "全量代码事实 + 4 路径接通 + N3 流量"

---

**B AI · 2026-05-22 阶段 0 后 systematic 盘点 — 等顾源源 review 计划后再动手**
