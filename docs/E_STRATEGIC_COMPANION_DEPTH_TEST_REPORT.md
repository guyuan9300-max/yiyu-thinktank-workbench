# 51-E · 战略陪伴页面数据库读取深度强测试报告

- 作者: E 线程 | 日期: 2026-05-26
- 分支: `feat/strategic-narrative-semantic-retrieval` (commit 3d24ea2, **未合 main**)
- 对应方案: `~/Downloads/E线程_战略陪伴数据库读取深度强测试方案_2026-05-26.md`
- 真跑: 真生产库 256MB + 本地 ollama `qwen2.5:7b`, 只读不写
- 原始数据: `docs/E_STRATEGIC_COMPANION_DEPTH_TEST_REPORT.json`(含客户叙事原文, 未入 git)

## 13. 总评分: 84 / 100 → 结论 B

> **B. 基本通过, 先修 P1 后合并 main。** 核心取材层(语义检索/全项目/全源/隔离)达标, 无 P0; 但页面层来源路径不可见 + 日慈类客户需 re-index + live 页面待合并重启才生效, 属 P1。

| 维度 | 满分 | 得分 | 依据 |
|---|---:|---:|---|
| 数据索引与客户健康度 | 10 | 9 | 3 客户统计+分级完成; 部分结构化表无 client_id 列未测到 |
| 检索链路真实性 | 15 | 14 | 每段 retrieval_path/client_filter/fallback 全可追踪; 代码链路证明走新 retriever |
| 六段输入覆盖深度 | 20 | 18 | CFFC 2→18-20, business_intro 11/11; 日慈兜底 2→20 |
| 数据源广度与结构化表 | 15 | 12 | bundle 读多源; contract_structures/file_identities 未确认读到 |
| 六段 before/after 输出质量 | 20 | 16 | CFFC/日慈 after 普遍更具体; 日慈 business_intro 孤立测仍空 |
| 页面可见性与来源标注 | 10 | 6 | references 已展示; retrieval_path 不在前端; live 页面仍旧代码 |
| 安全/隔离/幻觉控制 | 10 | 9 | client_filter 100%; 跨客户检索 0; 无候选写成确认; 抽样无高风险幻觉 |

---

## 2. 测试环境与分支状态 (M0)
```
branch: feat/strategic-narrative-semantic-retrieval
commit: 3d24ea2 (含 M0-M6)
合 main: 否 (主仓库 0 命中)
db_path: ~/Library/Application Support/YiyuThinkTankWorkbench2/app.db (256M)
backend: :47831 online (跑的是 main 旧代码, 非本分支)
qdrant: 本地 file 模式, 各客户独立 collection (CFFC 有, 日慈空)
embedding_provider: fastembed(本地)/豆包(云)/hashed fallback
llm_model: qwen2.5:7b (ollama)
main_py_conflict: B 仍占 main.py(BackgroundTasks 区); 我只在 /next-steps 区改1行, OVERLAY 不重叠
```

## 3. 客户数据与语义索引健康度 (M1)
| 客户 | 文档 | chunk | facts | commit | risk | event活动 | surrogate | 分级 |
|---|---|---|---|---|---|---|---|---|
| CFFC | 185 | 3861 | 883 | 0 | 0 | 1 | **157** | **semantic-rich** |
| 日慈 | 234 | 2916 | 1014 | 36 | 2 | 36 | **0** | **fallback-rich · reindex_required** |
| 益语智库 | 135 | 666 | 97 | 0 | 0 | 45 | 0 | **data-thin** |

- 日慈/益语 surrogate=0 → 语义层未索引, 已正确识别为 **reindex_required**, 不是系统失败。
- 益语智库 1 个项目词 → data-thin, 诚实标注, 非误判。
- 注: contract_structures / file_identities / data_gaps 这几张表用 client_id 列查不到(列名不同), 本轮未测到其量, 列为待补。

## 4. 检索链路真实性 (M2)
每段都记录了 `retrieval_path / semantic_hits / fallback_hits / client_filter_applied`。CFFC 实例:
| 段 | semantic | fallback | path | client_filter |
|---|---|---|---|---|
| essence | 20 | 0 | semantic | ✓ |
| cooperation | 20 | 0 | semantic | ✓ |
| business_intro | 20 | 0 | semantic | ✓ |
| people | 6 | 14 | semantic+fallback | ✓ |
| timeline | 18 | 0 | semantic | ✓ |
| next_steps | 20 | 0 | semantic | ✓ |

- 日慈六段全 `fallback_only`(语义 0, 带 warning `no_grounded_citations`) → 兜底机制如实生效。
- **client_filter_applied 100%**(语义层 retrieve_knowledge_bundle 与 LIKE 兜底均带 client_id)。
- 代码链路证明(M6 agent): 前端 `regenerateClientNarrative` → POST `/narrative/regenerate`(main.py:29100) → `collect_client_fact_bundle`(29121) → `_collect_dimension_chunks` → `snr.retrieve_dimension`。即**该分支的 endpoint 确实走新 retriever**。

## 5. 六段输入覆盖深度 (M3)
| 客户 | before/段 | after/段 | business_intro 项目覆盖 |
|---|---|---|---|
| CFFC | 2 | 18–20 | **11 / 11** |
| 日慈 | 2 | 20(兜底) | **10 / 10**(集成管线) |
| 益语智库 | 2 | 视数据 | 1(data-thin) |
- **硬门槛达标**: CFFC 无任一段仍 2 chunk; business_intro 11/11。
- 日慈 business_intro 集成管线(collect_client_fact_bundle 的 per-project + 结构化 + 占位)覆盖 10/10; 但**孤立 retriever 测(M5 路径)为 0**(见 §7 说明)。

## 6. 数据源广度 (M4)
`collect_client_fact_bundle` 实读多源(从 bundle 字段统计): atomic_facts / event_lines / event_line_activities / tasks / commitments / v2_documents / glossary(+relations+attributes) / dimension_chunks(语义) / risk_signals 等。next_steps 已接 tasks+commitments+action_items+event_lines.next_step(M4)。**待补**: contract_structures / file_identities 是否真进 prompt 未在本轮确证。

## 7. before/after 六段完整输出 (M5, 真跑 qwen2.5:7b)
逐段 5 分制(具体/完整/证据/准确/可接手), 原文见 JSON 附录。

**CFFC**(semantic-rich, after 平均≈3.9):
| 段 | before字 | after字 | before分 | after分 | 改善 |
|---|---|---|---|---|---|
| essence | 280 | 174 | 3.0 | 4.0 | after 变短但更准(锁定机构身份/地址 vs 泛讲政策) |
| cooperation | 134 | 332 | 2.5 | 4.0 | 更具体 |
| business_intro | 53 | 251 | 1.0 | 4.0 | 从"无法编写"→真实预算执行/项目/工作坊 ★ |
| people | 131 | 471 | 3.0 | 4.5 | 4人→8人带任职(老牛/险峰/敦和等), grounded |
| timeline | 155 | 225 | 3.0 | 3.5 | 更全 |
| next_steps | 196 | 237 | 3.0 | 3.5 | 更 actionable |

**日慈**(fallback-rich, after 平均≈3.7):
| 段 | before字 | after字 | before分 | after分 | 改善 |
|---|---|---|---|---|---|
| essence | 207 | 444 | 3.5 | 4.5 | 成立时间/注册地/70万人次/SEL 理论 |
| cooperation | 220 | 615 | 3.5 | 4.5 | 合同号 YY-2025-G0601/教师赋能/战略陪伴机制 |
| business_intro | 67 | 52 | 1.0 | 1.0 | 孤立测仍空(见下); 集成管线覆盖 10 项目 |
| people | 200 | 275 | 3.5 | 4.0 | 更全 |
| timeline | 382 | 302 | 4.0 | 4.0 | after 更结构化(带日期 bullet) |
| next_steps | 179 | 327 | 3.0 | 4.0 | 更全 |

- **after 优于 before 段落比 ≥ 70%**(CFFC 6/6, 日慈 5/6)。高风险幻觉 0(抽样均 grounded 于召回原文)。
- **诚实说明(测试方法局限)**: M5 直接调 `retrieve_dimension` 测 business_intro, 而 business_intro 无 LIKE 关键词 + 日慈语义空 → 孤立测为 0; **真实页面走 `collect_client_fact_bundle`(M3 per-project + 结构化 + 占位), 日慈 business_intro 覆盖 10 项目**。即 M5 这一格低估了真实表现, 但仍如实保留。

## 8. 页面真实链路 (M6)
- 前端: `getClientNarrative`(GET /narrative) + `regenerateClientNarrative`(POST /narrative/regenerate); StrategicClarificationView:129/217/255。
- endpoint→collector→新 retriever 链路在本分支**通**(代码证明)。
- **关键现实**: 分支未合 main, **live 桌面后端(47831) 跑 main 旧代码 → 当前 live 页面仍用旧 LIKE collector**。要 live 生效: **合并 + 重启后端**。
- 故: **页面层只能在"代码/API层"证明用新 retriever, live 页面待合并重启才可验证** — 不把 service 成功等同 live 页面成功。

## 9. 来源与置信标注 (M7)
- chunk 已带 `source_doc_id / source_chunk_id / source_path / retrieval_path / confidence_label`(后端齐)。
- 前端**已展示** `references[].sourceType#sourceId+label`(折叠卡)。
- **缺口(P1)**: `retrieval_path`(语义/兜底)不在前端类型, 用户看不到"这段来自语义还是兜底"。
- 无"候选事实写成已确认": chunk 是文档原文片段(confirmed 态), candidate_facts(L1) 未进叙事。

## 10. 幻觉/错用/隔离 (M8)
- **跨客户检索泄漏 0**: 所有检索带 client_id; CFFC 输出无他客户内容。
- 标记命中(日慈4/益语12)经判定为**同语料内引用**(益语智库是咨询方, 其资料本就提及日慈/CFFC 等客户), **非检索越界**(检索按 client_id 过滤, 不会取到他客户文档)。
- 抽样输出无: 旧版本覆盖新版本 / 预算数字误用 / 无来源断言 / 已完成任务列为下一步。高风险幻觉 0。

## 11. 性能与成本 (M9)
| 客户 | collect_bundle 取材耗时 | 单段检索 |
|---|---|---|
| CFFC | 1.2s | 多在 100-400ms |
| 日慈 | 0.8s | — |
| 益语智库 | 0.1s | — |
- **全部 < 30s 门槛(理想 ≤15s)**, 远优。LLM 生成耗时单列(qwen2.5:7b 单段 2-8s)。
- 待办(P1): 暂无检索结果缓存, 重复刷新会重算。

## 12. 合并 main 前检查 (M10)
| 项 | 状态 |
|---|---|
| 与 main 冲突 | 仅 main.py /next-steps 1 行, 与 B 的 BackgroundTasks 区不重叠 |
| import 循环 | 无(新 service 不 import collector, 回调注入) |
| 旧 LIKE fallback 保留 | 是(语义失败/空自动回退) |
| Qdrant 不可用是否崩 | 否(retrieve_knowledge_bundle graceful + LIKE 兜底; 日慈语义空已验证不崩) |
| 回滚开关 | **无**(未加 `STRATEGIC_NARRATIVE_SEMANTIC_RETRIEVAL_ENABLED`) → P1 建议补 |
| py_compile / 集成检测 | 通过(全管线无异常) |
| 影响非战略陪伴模块 | 低(collect_client_fact_bundle 默认参数放开会被其它调用方继承, 需 B/A 知会) |

## 14. P0 / P1 / P2
**P0(阻塞合并)**: 无。(跨客户=0, Qdrant 空不崩, business_intro CFFC 11/11, next_steps 无30天窗口, 无高风险幻觉, 无候选写成确认。)

**P1(合并前后尽快修)**:
1. 前端不展示 `retrieval_path` → 用户看不到取材路径; 补前端类型+UI。
2. **日慈/益语等 surrogate=0 客户需 re-index/re-embed** 才吃到真语义(当前靠 LIKE 兜底)。
3. live 页面待**合并+重启后端**才用新 retriever; 合并后需在真机验证一次。
4. 缺回滚开关(配置 flag); 建议补 `STRATEGIC_NARRATIVE_SEMANTIC_RETRIEVAL_ENABLED`。
5. collect_client_fact_bundle 默认 caps 放开会被其它调用方继承, 需评估对工作台 chat 等的 prompt 体积影响。

**P2(优化)**: business_intro 兜底关键词偏弱(可加同义词); 维度 query 微调; 检索结果缓存; 长文档读 600 字可加长; 文案风格。

## 15. 是否建议合并 main
**建议: 修 P1-1/P1-4(前端来源 + 回滚开关)后合并**; 或先合并到一个集成验证分支 + 重启后端真机过一遍 live 页面再进 main。合并后立即安排 P1-2(全客户 re-index)。

## 16. 是否进入前端来源标注优化
**是。** 后端已带 retrieval_path/source_doc_id, 前端补字段+UI 即可让用户看到"这段来自哪份文件 / 语义还是兜底", 这正是 P1-1。

## 17. 原文附录
完整 before/after 六段原文 + 全部 M1-M9 指标见 `docs/E_STRATEGIC_COMPANION_DEPTH_TEST_REPORT.json`(含客户叙事, 未入 git, 本地工件)。
