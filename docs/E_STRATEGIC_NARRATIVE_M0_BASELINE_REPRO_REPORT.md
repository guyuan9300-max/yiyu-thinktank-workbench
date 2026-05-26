# E · M0 · 战略陪伴取材基线复现报告

- 作者: E 线程
- 日期: 2026-05-25
- 分支: `feat/strategic-narrative-semantic-retrieval`(隔离 worktree)
- 目的: 复现 49-E 报告基线 + 钉死每个限制的精确代码位置, 作为 M6 "改前/改后" 对比的锚点
- 数据源: 真生产库 `~/Library/Application Support/YiyuThinkTankWorkbench2/app.db`(256MB)
- 本里程碑**不改任何代码**

---

## 1 · 全库基线(复现)

| 指标 | 值 |
|---|---|
| clients | 12 |
| v2_documents | 998 |
| v2_chunks | 11998 |
| atomic_facts | 2310 |
| client_glossary | 407 |
| tasks / commitments / action_items / event_lines / meetings | 238 / 66 / 4 / 16 / 7 |

复现结论: 与 49-E 报告一致(同库),基线稳定可作对比锚点。

---

## 2 · 两个样本客户的可用数据量(复现)

| 客户 | 文档 | chunk | atomic_facts(可入) | 项目词 | 任务 | 承诺 |
|---|---|---|---|---|---|---|
| CFFC | 185 | 3861 | 883 | 11 | 3 | 0 |
| 日慈基金会 | 234 | 2916 | 1012 | 9 | 14 | 36 |

---

## 3 · 6 维度"关键词命中池 vs 现状实际取"(复现 — 核心证据)

现状取数靠固定关键词 SQL LIKE(`narrative_collector.py:622-633` `_DIMENSION_BASE_KEYWORDS`),每维度 `_retrieve_top_chunks` 实际只取 **2 个 chunk**。

### CFFC(共 3861 chunk)
| 维度 | 关键词命中池 | 现状实取 | 覆盖率 |
|---|---|---|---|
| essence | 1589 | 2 | 0.13% |
| cooperation | 1005 | 2 | 0.20% |
| people | 1578 | 2 | 0.13% |
| timeline | 740 | 2 | 0.27% |
| next_steps | 851 | 2 | 0.24% |

### 日慈基金会(共 2916 chunk)
| 维度 | 关键词命中池 | 现状实取 | 覆盖率 |
|---|---|---|---|
| essence | 654 | 2 | 0.31% |
| cooperation | 695 | 2 | 0.29% |
| people | 561 | 2 | 0.36% |
| timeline | 517 | 2 | 0.39% |
| next_steps | 725 | 2 | 0.28% |

**复现结论: 每段覆盖率 0.1%–0.4% 坐实。**

---

## 4 · 每个限制的精确代码位置(给 M1-M5 落地用)

| 限制 | 现状值 | 代码位置 | M 对应 |
|---|---|---|---|
| 检索方式 = SQL LIKE, 不走向量 | `content LIKE '%kw%'` | `narrative_collector.py:687-711`(`_retrieve_top_chunks`) | M1 |
| 固定维度关键词集 | 6 维各一组固定词 | `narrative_collector.py:622-633`(`_DIMENSION_BASE_KEYWORDS`) | M1/M2 |
| 每维度只取 2 chunk | `limit=2` / `max_per_doc` | `narrative_collector.py:_collect_dimension_chunks`(调用 `_retrieve_top_chunks limit=2`) | M5 |
| business_intro 只取前 6 项目 | `project_terms[:6]` | `narrative_collector.py:748` | M3 |
| atomic_facts 上限 60 | `atomic_fact_limit=60` | `narrative_collector.py:341,344,372` | M5 |
| documents 上限 25 + 只读 240 字摘要 | `document_limit=25` / `preview_text[:240]` | `narrative_collector.py:345,376` / `:1162` | M5 |
| persons/time/money/event/activity/task 硬上限 | 30/15/10/12/40/30 | `narrative_collector.py:338-345` | M5 |
| prompt 二次截断 | `facts[:6]` `activities[:15]` `tasks[:15]` `chunks[:6]` `excerpt[:480]` | `narrative_generator.py:501,534,542,666,671` | M5 |
| next_steps 会议待办 30 天硬窗口 | `days=30` | `main.py:28150`(`extract_recent_client_actions`) | M4 |
| next_steps 漏 event_lines.next_step | 未纳入 | `todo_aggregator.py`(只 union task/action/commit) | M4 |
| pulse 并行实现只读 tasks | 漏 commitments/action_items | `client_strategic_pulse.py:262` | M4 |
| 完全不查 Qdrant | 4 核心文件 0 引用 | grep 全程无 qdrant | M1 |

---

## 5 · 可复用的现成语义检索入口(M1 复用目标)

- `knowledge_base.retrieve_knowledge_bundle(db, data_dir, client_id, prompt) -> RetrievalBundle`(`knowledge_base.py:3779`): 混合检索(FTS `search_master_index_fts` + Qdrant `search_master_index_qdrant`), 按 `client_id` 隔离, 带 query-mode 识别(strategic/overview/intro/finance)。
- 向量库已 populated: `~/Library/Application Support/YiyuThinkTankWorkbench2/vector_store/client_*` 各客户独立 collection(含 `client_cffc` 等)。
- embedding: `embedding_provider.py` 支持 fastembed(本地) / 豆包(云) / hashed fallback。

**M1 策略: 复用 `retrieve_knowledge_bundle` 按维度 query 检索, 不重造向量检索。**

---

## 6 · M0 通过判定

| 验收项 | 目标 | 结果 |
|---|---|---|
| CFFC/日慈 基线复现 | 100% | 通过 |
| 6 维度都有 baseline | 100% | 通过 |
| 复现每段 2 chunks | 是 | 通过 |
| 复现 business_intro 前 6 限制 | 是 | 通过(`:748`) |
| 复现 next_steps 30 天窗口 | 是 | 通过(`main.py:28150`) |
| 每个限制定位到代码行 | 100% | 通过(见 §4) |

M0 完成。下一步 M1: 建 `strategic_narrative_semantic_retriever.py` 统一取材层。
