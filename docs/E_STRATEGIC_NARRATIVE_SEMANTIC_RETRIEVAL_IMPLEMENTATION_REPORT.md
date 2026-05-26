# E · 战略陪伴语义检索改造 · 实现报告 (M1 + M2, 停在 M2)

- 作者: E 线程
- 日期: 2026-05-26
- 分支: `feat/strategic-narrative-semantic-retrieval` (隔离 worktree, 未 push, 未 commit, 待 review)
- 范围: **顾源源指示"做到 M2 停"** — 本报告覆盖 M1 + M2; M3–M6 未做。

---

## 1 · 做了什么 (M1 + M2)

### M1 · 统一取材服务 (新文件)
`backend/app/services/strategic_narrative_semantic_retriever.py` (新增, ~230 行)

- **不再每维度各写一套 LIKE**, 抽出统一入口 `retrieve_dimension(db, client_id, dimension, ...)`。
- **语义优先**: 复用 `knowledge_base.retrieve_knowledge_bundle(db, data_dir, client_id, query)` (FTS + Qdrant 混合, 按 `client_id` 隔离), 不重造向量检索。
- **LIKE 兜底**: 通过**回调注入** `like_fallback_fn` (= `narrative_collector._retrieve_top_chunks`), 避免与 collector 循环 import。触发条件: 语义为空 / `coverage < 0.15` / 召回 < 8 段。
- **来源标注**: 每段产出 `RetrievedChunk(doc_title, excerpt, score, source_doc_id, source_chunk_id, source_path, retrieval_path)`, `retrieval_path ∈ {semantic, like_fallback}`。
- **可追踪**: `DimensionRetrieval` 带 `fallback_used` / `coverage` / `source_breakdown` / `warnings`。
- **不碰 main.py**: `data_dir` 由 `Database.db_path.parent` 推导 (`data_dir_for(db)`), 无需改签名 / 调用点。
- **强制 client 隔离**: 语义层 retrieve_knowledge_bundle 内部 `WHERE client_id=?`; LIKE 兜底回调同样带 client。
- `confidence_label` 字段为 candidate_facts / 3.0 预留 (默认 confirmed)。

### M2 · 6 维度语义意图 query + 接线
- `DIMENSION_SEMANTIC_QUERIES`: 6 段各一句"语义意图"(不是固定关键词)。例 essence = "这家机构是谁，它的核心定位、服务对象、长期关注的议题、独特价值、行业角色和影响力是什么？"。
- 重写 `narrative_collector._collect_dimension_chunks` (+47/-37):
  - essence / cooperation / people / timeline / next_steps → 全部走 `retrieve_dimension` (语义优先 + 原固定关键词降级为 LIKE 兜底关键词)。
  - business_intro → 语义总览 (文档 chunk 统一由语义负责) + 保留 per-project 的 tasks / 复盘 / 会议结构化源 (语义层覆盖不到的口语化记录)。
  - **输出类型不变** (`dict[str, list[DimensionChunk]]`), `narrative_generator` 消费侧零改动。
  - `DimensionChunk` 扩 4 个带默认值的来源字段 (score / source_doc_id / source_path / retrieval_path), 兼容旧构造。

---

## 2 · 关键设计权衡

| 点 | 选择 | 理由 |
|---|---|---|
| 检索复用 vs 重造 | 复用 retrieve_knowledge_bundle | 已是 FTS+Qdrant 混合 + client 隔离, 重造徒增风险 |
| 循环依赖 | 回调注入 LIKE fallback | collector→service 单向, service 不 import collector |
| data_dir 来源 | 从 db.db_path 推导 | 避免改 main.py (B 正占 main.py) |
| business_intro | 语义总览 + 结构化源; 暂留 `[:6]` | 全项目覆盖是 M3 的事, 本轮不越界 |
| 每段候选上限 | top_k=20 (候选), 入 prompt 仍受 generator `chunks[:6]` 限 | 真正放量 = M5 token budget, 本轮先把"召回"打开 |

---

## 3 · 一个必须知道的真发现: 语义层 populated 不均

实测向量/surrogate 层 (M1 验):
- **CFFC** (`client_a4d1db29a7`): 1.2M / 158 surrogate 文件 + master_index 162 → 语义层健康, 语义检索能真生效。
- **日慈** (`client_284afd836e`): 仅 244K / 2 文件 → **surrogate/Qdrant 层几乎空**, master_index 117 (FTS 可用)。

含义: 本次改造让 narrative **能**走语义检索, 但**语义红利的兑现取决于该客户 knowledge/surrogate 层是否已索引**。
- 日慈这类未充分索引的客户, 语义层会回 FTS / 触发 LIKE 兜底 (fallback_used=True), 仍比"固定关键词 2 chunk"强 (master-index 评分 + 覆盖词), 但拿不到向量语义的全部好处。
- **要吃满红利, 需对未充分索引客户跑一轮 knowledge ingest / re-embed** (独立于本取材层改造, 建议列入 M6 之后)。M6 的 before/after 会按客户量化这个差。

---

## 4 · 本轮没做 (停在 M2, 后续里程碑)

| 里程碑 | 状态 | 说明 |
|---|---|---|
| M3 全项目覆盖 | 未做 | business_intro 仍 `project_terms[:6]`; 去 [:6] + 全项目 per-project 语义召回留 M3 |
| M4 next_steps 全源 | 未做 | 需改 main.py(`/next-steps` 28106 30天窗口) + pulse.py — **main.py B 占着, 已 inbox-B 知会, 等 B 释放** |
| M5 token budget | 未做 | facts=60 / documents=240字摘要 / generator `chunks[:6]`/`facts[:6]` 等硬上限仍在; 改 token 预算驱动留 M5 |
| M6 真 before/after | 未做 | 需起 backend + LLM 真跑 CFFC/日慈 6 段对比 → 产出桌面 50-E |

---

## 5 · 验证状态 (诚实)

- ✅ **语法**: `python3 -m py_compile` 三文件通过。
- ✅ **静态**: 输出类型不变 (generator 零改动); client 隔离保留; 无循环 import; 不碰 main.py。
- ⏳ **运行时 / before-after**: **未跑** — 真实 LLM 输出对比是 M6 的事 (需后端+LLM 环境)。本轮**不声称**内容已变好, 只声称"取材通道已从 LIKE 升级为语义优先+兜底", 真实效果待 M6 量化。

---

## 6 · 改动文件

```
新增  backend/app/services/strategic_narrative_semantic_retriever.py
改    backend/app/services/narrative_collector.py  (+47/-37: DimensionChunk 扩字段 + _collect_dimension_chunks 重写)
新增  docs/E_STRATEGIC_NARRATIVE_M0_BASELINE_REPRO_REPORT.md
新增  docs/E_STRATEGIC_NARRATIVE_SEMANTIC_RETRIEVAL_IMPLEMENTATION_REPORT.md (本文件)
```
未 commit / 未 push, 在隔离 worktree, 等顾源源 review 后再决定继续 M3-M6 / 合并。
