# 50-E · 战略陪伴语义检索改造后测评报告 (M0–M6 完成)

- 作者: E 线程
- 日期: 2026-05-26
- 分支: `feat/strategic-narrative-semantic-retrieval` (隔离 worktree, 已 commit, **未合 main / 未 push**, 待 review)
- 配套: 49-E (改造前测评) / docs M0 基线 / docs 实现报告 / docs after 报告 (本文桌面同步版)
- 真跑环境: 真生产库 256MB + 本地 ollama `qwen2.5:7b` (真调, 非想象)

---

## 0 · 一句话结论

战略陪伴取材层从「固定关键词 LIKE + 每维 2 chunk」**真正升级为「语义检索优先 + LIKE 兜底 + 全项目覆盖 + 全源 next_steps + 来源标注」**。真库实测: 每维度输入 **2 → 18–20 chunk**, business_intro 项目覆盖 **6 → 全覆盖(CFFC 11/11, 日慈 10/10)**。真跑 qwen 对比: 已索引客户(CFFC)内容显著变具体(business_intro 41字"无法编写" → 234字含真实预算/项目)。**检测自评 92/100, 过通过线 90**, 带 2 个诚实 caveat (见 §6)。

---

## 1 · 测评方法 (诚实)

- **before** = 旧路径 `_retrieve_top_chunks`(固定关键词 LIKE, limit=2)。
- **after** = 新路径 `strategic_narrative_semantic_retriever.retrieve_dimension`(语义优先 `retrieve_knowledge_bundle` + LIKE 兜底)。
- 6 维度都量输入差; essence + business_intro 两维**真调 qwen2.5:7b**(同模型同提示, 只换喂进去的资料)对比输出。
- 另跑**集成检测**: 真实 `collect_client_fact_bundle` 全管线(含 M3 全项目 + M5 预算), 验证不崩 + 项目覆盖。
- 全程只读库 + 只调本地 ollama, 不写表、不 POST 云端。原始数据: `docs/E_M6_BEFORE_AFTER_RAW.json`。

---

## 2 · 输入覆盖: before → after (真库实测)

### CFFC (client_a4d1db29a7, 已建语义索引)
| 维度 | before | after | 来源构成 | 覆盖 |
|---|---|---|---|---|
| essence | 2 | 20 | 语义 20 | 0.50 |
| cooperation | 2 | 20 | 语义 20 | 0.25 |
| business_intro | **0** | 20 | 语义 20 | 0.50 |
| people | 2 | 20 | 语义 6 + 兜底 14 | 0.25 |
| timeline | 2 | 18 | 语义 18 | 0.50 |
| next_steps | 2 | 20 | 语义 20 | 0.38 |

→ 真语义检索生效, 召回 ~10×; business_intro 旧关键词 0 命中, 语义找到 20。people 语义不足 8 段时自动 LIKE 补满(兜底机制验证生效)。

### 日慈基金会 (client_284afd836e, 语义层未充分索引)
| 维度 | before | after | 来源构成 | 说明 |
|---|---|---|---|---|
| essence/cooperation/people/timeline/next_steps | 2 | 20 | **兜底 20**(语义 0) | 语义层空(`no_grounded_citations`)→ LIKE 兜底, 但 limit 放开后仍 2→20 |

→ 诚实: 日慈 surrogate/Qdrant 层几乎空(见 49-E / M0), 语义返回 0, 全靠 LIKE 兜底。但因放开了 limit, 召回仍从 2→20(更多词面匹配)。**要兑现真语义红利, 日慈这类客户需补跑 knowledge 索引/re-embed**(独立于本取材层改造)。

---

## 3 · business_intro 全项目覆盖 (M3, 集成检测实测)

| 客户 | 改造前(项目覆盖) | 改造后 | 实测 chunk |
|---|---|---|---|
| CFFC | 6 / 11 | **11 / 11** | business_intro 55 段 |
| 日慈 | 6 / 9 | **10 / 10** | business_intro 48 段 |

→ 去掉 `project_terms[:6]`, 每项目 per-project 语义召回 + tasks/复盘/会议结构化源 + 空项目占位。**全部项目都进叙事, 不再丢项目。** 注意: 孤立测 retriever 时日慈 business_intro=0(通用关键词没命中), 但集成管线靠 per-project + 结构化 + 占位救回 10/10。

---

## 4 · 真实 LLM before/after 文本对比 (qwen2.5:7b 真跑)

### CFFC · business_intro (最强对比)
- **before** (输入 0 chunk, 41字): "根据提供的资料，无法编写关于该客户的"业务介绍"。如需帮助，请提供相关事实和信息。" — **等于没有**。
- **after** (输入 20 chunk, 234字): "…主要业务活动成本预算为1294.72万元，实际执行为944.78万元，执行比例为72.97%；管理费用预算为109.29万元…通过"互联网公益公众监督"项目…全员战略工作坊、管理层共识沟通会议…" — **真实预算数字 + 真实项目 + 真实活动**。
- 评估: 具体度↑↑ / 完整度↑↑ / 证据性↑↑ / 新增有效信息≈全部 / 幻觉风险低(都来自召回原文)。

### CFFC · essence
- before(2 chunk,167字): 偏单一(只讲政策倡导)。
- after(20 chunk,186字): 含机构地址、联系方式、互联网公益公众监督行动、行业生态网络等多面。具体度↑。

### 日慈 · essence (兜底路径也有增益)
- before(2 chunk,224字): 已不错(心灵魔法学院等项目)。
- after(20 chunk,303字): 更具体——"成立于2013年12月"、注册地、"积极心理学/SEL"理论基础、"服务超过70万名、500万人次"、FTI2024满分。完整度↑。
- 说明: 日慈语义空, 此增益来自 LIKE 召回 2→20 段(更多原文), 非真语义。

### 日慈 · business_intro (诚实失败点)
- before/after 均"无法编写"(孤立 retriever 通用关键词 + 语义空, 双落空)。
- 但集成管线(M3 per-project)对日慈 business_intro 覆盖 10 项目(见 §3) — 孤立测低估了它。根因仍是日慈未索引 + business_intro 通用关键词弱。

---

## 5 · next_steps 全源改造 (M4)

| 项 | 改造前 | 改造后 |
|---|---|---|
| 会议待办时间窗 | **30 天硬窗口**(31天前永久取不到) | 去掉(days=3650) |
| 来源 | tasks + commitments + action_items + 会议(30天) | + **event_lines.next_step**(主线衍生待办) |
| pulse 并行实现 | **只读 tasks**(漏 commitments/会议待办) | 补 commitments + action_items + event_lines.next_step |
| 排序/去重 | 紧迫度排序 + fingerprint dedup | 保留 |

→ 注: main.py 的 `/next-steps` 一行改动在我的分支, main.py 当前 B 占用(BackgroundTasks 区), 我用 OVERLAY 错开 /next-steps 区; **合 main 时需与 B 协调该文件**(已 inbox-B 知会)。

---

## 6 · 检测评分 (100 分制, 诚实自评)

| 维度 | 分值 | 得分 | 依据 |
|---|---|---|---|
| 语义检索统一层 | 20 | 20 | 统一 retriever, client 隔离, 语义+兜底, 来源标注, CFFC sem=20 实证 |
| 输入覆盖提升 | 20 | 20 | 2→18-20 实测(10×) |
| business_intro 全项目覆盖 | 15 | 15 | 6→11/10, 集成检测实证 |
| next_steps 全源改造 | 15 | 13 | 去30天+event_lines+pulse补源; 未纳 clarifications/data_gaps/approvals(设计上不算"待办") |
| token budget + 证据标注 | 15 | 13 | chunks 预算驱动+caps放开+来源标注; 是字符预算非完整 NarrativeTokenBudget 类, 文档读600字非全文 |
| before/after 输出质量 | 15 | 11 | CFFC强/日慈essence强; 日慈语义空仅兜底增益, 日慈business_intro孤立测仍空 |
| **合计** | **100** | **92** | **过通过线 90** |

**检测结论: 通过 (92 ≥ 90)。** 取材层改造成功, 可进入下一轮(前端展示优化)。

---

## 7 · 诚实 caveat (必须知道)

1. **日慈类客户需补索引**: 语义红利只在已建 surrogate/Qdrant 索引的客户(如 CFFC)兑现; 日慈语义层近空, 当前靠 LIKE 兜底(仍比改造前强, 但非真语义)。**建议下一步: 对全部 13 客户跑一轮 knowledge ingest/re-embed**, 这是独立的数据工程任务, 不属本取材层。
2. **main.py 改动待合并协调**: M4 的 `/next-steps` 去窗口在我分支; main.py 被 B 占用, 合 main 需与 B 协调(区域不重叠, 风险低)。
3. **未合 main / 未 push**: 全部改动在隔离 worktree feature 分支, 已本地 commit, 等顾源源 review 后再 PR 合并(合 main 影响产线)。

---

## 8 · 改动文件 + 后续建议

```
新增 backend/app/services/strategic_narrative_semantic_retriever.py   (M1 统一取材层)
改   backend/app/services/narrative_collector.py                      (M2 语义接线 / M3 全项目 / M5 放开caps)
改   backend/app/services/narrative_generator.py                      (M5 chunks 预算驱动 + 来源标签)
改   backend/app/services/todo_aggregator.py                          (M4 +event_lines.next_step)
改   backend/app/services/client_strategic_pulse.py                   (M4 +commitments/会议待办/主线衍生)
改   backend/app/main.py                                              (M4 /next-steps 去30天窗口, 1行)
新增 scripts/run_m6_before_after.py                                   (M6 对照脚本, 可复跑)
新增 docs/E_STRATEGIC_NARRATIVE_{M0_BASELINE_REPRO,SEMANTIC_RETRIEVAL_IMPLEMENTATION,SEMANTIC_RETRIEVAL_AFTER}_REPORT.md
新增 docs/E_M6_BEFORE_AFTER_RAW.json                                  (原始 before/after 数据)
```

**后续建议优先级**:
1. (数据工程) 全客户 knowledge re-index/re-embed → 让日慈类客户也吃到真语义。
2. (协调) 与 B 协调合并 main.py /next-steps 改动。
3. (前端) 战略陪伴页用上来源标注(retrieval_path/source_doc_id 已带), 让用户看到"这段来自哪份文件"。
4. (调优) business_intro 通用关键词兜底偏弱, 可补维度同义词扩展; 长文档读全文片段而非 600 字。
