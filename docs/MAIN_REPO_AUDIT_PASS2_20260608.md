# 主仓库审计 · 遍2 深钻到铁证 (2026-06-08)

> 6个P1根因簇深钻+独立对抗复核,**全部upheld无证伪**。13 agent/739K tokens。只读。
> 注:合成时payload截断丢了E/F,此处从raw补全。

## 合成报告(A/B/C/D)

All load-bearing claims confirmed against live code and DB:
- B: `WHERE status != 'needs_attention'` (line 1576), zero NetInfo, retry budget hardcoded `"server_rejected"` at :467 (note: not even `reasonCode`-aware), requeue resets retry_count=0 with self-documenting comment.
- C: `WHERE sync_status = 'pending'` (line 149) excludes failed; HTTP-error path marks 'failed' irreversibly; evidence FK precondition documented in code.
- D: backend endpoint `/api/v1/meeting-minutes/process` exists (main.py:39354), frontend grep for that endpoint returns **empty** — confirming UI-not-wired.

One refinement to note: at sync-engine.ts:467 the `markOpFailed` call uses `op.reasonCode ?? "server_rejected"`, so it *does* carry a reasonCode — but the **branching decision** (`nextStatus`) at :566 still ignores reasonCode type, only thresholding retryCount. The root-cause claim holds.

---

# 主仓库审计【遍2】合成报告

**总览（一句话）：** 6 个根因簇经直接库查 + 代码核证 + 对抗复核后**全部 upheld**，无一被证伪降级为误报；其中真正"会崩/会丢数据"的硬故障集中在 A（本地登录读崩）、B（手机离线永久冻结）、C（成长云同步 99.7% 卡死），D（会议链后端做完前端从未接）为"半成品而非缺陷"，性质降为 partial。

**严重级计数（主根因，共 6 簇）：** P0 ×0 · P1 ×4（A/B/C/D）· P2 ×0 · 待定 ×2（E/F 因输入被截断，见末尾"遍3未决"）
**次生问题计数（已枚举簇 A–D，共 22 条）：** P0 ×1 · P1 ×11 · P2 ×7 · P3 ×3

---

## 簇 A — local_identities 代码/真库 schema 漂移

**铁证根因（已库查证实）：** `app/db.py:75-95` 的 `CREATE TABLE local_identities` 定义 `phone_number`，但真库 `PRAGMA table_info` 实际为 `phone`(col2)+`phone_normalized`(col3)，且多出 7 列（`primary_role`/`account_status`/`membership_rejected_reason`/`local_organization_id` NOT NULL 无默认/`is_department_lead` 等）。`app/main.py:5328` 处 `str(row["phone_number"] or "")` 无 try/except——从真库 fetchone 的行读 `phone_number` 会触发 sqlite3.Row 的 `IndexError: No item with that key`。`_ensure_column` 链覆盖 50+ 其他表却**独缺 local_identities**。真库现存 1 行（chenzhenli@klngo.org），创建于 schema 变更之前，包内打包版仍写 `phone_number` → 真库系 **git 外手工 ALTER**。

**real vs intentional：** real_problem，**upheld**。漂移是物理事实（直接 PRAGMA 比对），非理解偏差。
**严重级：P1**（仅特定路径——本地 session 读取——会崩，不腐蚀数据；但触发即必崩、阻断该用户登录，故不降 P2）。次生项里"main.py:5328 侵略性假设"标 P0 是**就该单点而言**的崩溃确定性，主簇按影响面定 P1。

**精确修复范围：**
1. 先定来源（git log + 问用户是否手工 ALTER），再决策：保留新列 → db.py 补 CREATE 定义 + 补全 `_ensure_column` 链（db.py ~2580）；误操作 → 导出该 1 行数据后回退。
2. `main.py:5328` 改 `row["phone"] if "phone" in row.keys() else row["phone_number"]` 容错（注意 sqlite3.Row 用 `in row.keys()` 判存在，不能 `.get()`——见用户 MEMORY）。
3. `db.py:96-97` 的 `idx_local_identities_phone(phone_number)` 索引须随表定义同步改列名，否则新建库建错索引。
4. `local_organization_id` 真库 NOT NULL 无默认 → 注册端点 INSERT 必须补齐或改 `DEFAULT ''`。

**新增次生问题：** 改 5328 容错后，下游 `SessionUserRecord.phone` 语义需确认取 `phone`（原始）还是 `phone_normalized`；若补 `_ensure_column` 给老库 ALTER 出 7 列，须保证默认值与真库现存行不冲突（real 库 `primary_role='employee'` 而 db.py 默认 `'admin'`，迁移别覆盖既有值）。

---

## 簇 B — 手机离线操作永久冻结

**铁证根因（代码核证）：** `sync-engine.ts:467` 在发任何网络请求**之前**先判 `op.retryCount >= MAX_OP_RETRIES` 直接 `markOpFailed(...,"needs_attention")`；catch 块（:563-582）对**任意错误类型**（含瞬时 `network_unavailable`）一律 `markOpFailed` 递增 retry_count，:566 的 `nextStatus` 决策**只看 retryCount 阈值、不分流 reasonCode**。`local-db.ts:1576` `getPendingOps` 用 `WHERE status != 'needs_attention'` 永久剔除已标记 op。`SYNC_INTERVAL_MS=120000`（:45），且 `grep netinfo = 0`（**确认无网络监听器**）→ 离线 5 次（每 2min）耗尽预算后永久冻结，重连无即时触发。`requeueOp`（local-db.ts:1944）正确 `retry_count=0` 且代码注释已自证此修复的必要性。

**real vs intentional：partial**，**upheld**。"达上限→needs_attention 等人工"是有意终态，但"瞬时网络错也消耗预算"+"无重连触发"是设计缺口，非有意。
**严重级：P1。**

**精确修复范围：**
1. （P1）catch 块按 reasonCode 分流：`network_unavailable` 不增 retry_count、保持 `queued`。
2. （P1）`AppState` 订阅（:268）后加 NetInfo 监听，`unavailable→available` 立即 `void performSync()`。
3. （前置 P0）确认 `requeueOp` 的 `retry_count=0` 已部署（库注释证实在位）。
4. 已落地的 system-health requeue UI 作人工兜底。

**新增次生问题：** 让瞬时错"无限留 queued"后，须防永不退避的轮询风暴 → 应配指数退避（次生第5条 P2）；区分 `validation_failed`/`server_rejected`（仍 needs_attention）与 `network_unavailable`（queued）的分类正确性依赖 `mapSyncErrorToReasonCode` 的准确度，分类错会让真正坏数据永远重试。

**次生（7 条）：** 无 NetInfo 监听(P1)、网络错耗满 5 次预算(P1)、getPendingOps 排除 needs_attention 阻断手动同步(P1)、reasonCode 提取后从不分支(P1)、markOpFailed 无条件 needs_attention(P1)、无指数退避(P2)、后台 fetch 不随连接态自适应(P2)。

---

## 簇 C — 成长/手册云同步 failed 永不重扫

**铁证根因（库查 + 代码核证）：** `growth_sync.py:149` `WHERE sync_status = 'pending'` 排除 'failed'；HTTP 错误（:178-181）与缺 `signal_id`（:156-162）均标 'failed' **不可逆**，无任何代码把 'failed'→'pending'，无 retry_count/backoff/admin 恢复 API。`handbook_sync.py:87` 同构。**库铁证：`growth_signal_events` = 71 failed / 603 local / 2 synced（成功率 0.3%）**，failed 跨 2026-05-28~06-05 连续 8 天。evidence push 以 `signal_id` 云端存在为先决条件（:209-223 + 云端 main.py:19874-19879 SELECT 严检）→ signal 失败级联 evidence 失败死锁。

**real vs intentional：partial**，**upheld**。failed 是可观察终态（注释 :8-9 状态机）但**无显式人工干预 API**，属"设计残留需补完重试"，非纯黑箱也非有意。
**严重级：P1**（99.7% 阻断 + FK 级联 + 8 天无自愈 + 云为权威源 + 用户无 UI 自救）。

**精确修复范围（四层）：** L1 立即——:149/:87 改 `sync_status IN ('pending','failed')`，**不做 failed→pending 自动转态、只扩扫描**（无数据丢失）；L2 加 `attempt_count`/`max_attempt_count`/`last_attempt_at` + 退避（5/15min/手工），幂等 UPSERT；L3 FK 屏障感知——evidence push 前筛出对应 signal 仍 failed/local 的，defer 跳过本轮不标 failed，杜绝级联；L4 监控告警 + `GET /api/v1/admin/sync-status`。文件：growth_sync.py(149/136-192/209-223)、handbook_sync.py(87/78-134)、main.py(3322-3331 日志)、云端无需改。

**新增次生问题：** L1 扩 failed 重扫后，若 failure 是确定性（payload schema 不合）会每轮重试刷日志 → 必须配 L2 的 attempt_count 上限同时上，否则把"永久卡死"换成"永久重试"。另注意 **603 local 根因在 badge_engine.py:1148-1153 try/except 吞异常导致从未进 pending**——L1/L2 不触及，是独立上游缺口（应在遍3并入）。

**次生（4 条）：** handbook 同构隐患(P2)、evidence 本地侧无 signal-synced 预检(P2)、validation/evidence FK 不对称成孤儿(P3)、云端 growth 表无 sync_status/幂等字段(P3)。

---

## 簇 D — 会议链后端完成、前端从未接

**铁证根因（库查 + grep 核证）：** 后端三层完整（`agent_governance.py` 建表、`meeting_minute_processor.py:147-486` 端到端、双层 log），端点 `/api/v1/meeting-minutes/process` 在 `main.py:39354` 确实存在。但 **`grep "meeting-minutes/process" src/renderer/ = 空**（核证）**，src/renderer 无 Meeting*/minute* 组件，mobile 无相关字面量。真库 `agent_run_log`/`approval_queue` 两表均不存在（已库查证实 sqlite_master 无返回），`clarification_records`/`meeting_minute` 来源的 ela count=0。根因在 `ensure_governance_schema` 仅惰性触发（agent_governance.py:140），而 startup worker（main.py:3720-3869）未调它，前端又从不调端点 → 表永不创建。git 历史确认 code 自 5/23 即在 main，前端 UI 始终未跟进。

**real vs intentional：partial**，**upheld**。后端是有意建好的 R2 能力，前端未接是**未完成**而非缺陷——故性质 partial、严重级因"无用户暴露面、无数据腐蚀"实质偏低，但因整条价值链不可用按 P1 记账。
**严重级：P1**（功能完全不可达；若判定为"刻意暂缓上线"则可降 P2，需用户确认意图）。

**精确修复范围（输入在此截断，依现有内容）：** ① `src/renderer/lib/api.ts` 新增 `processMeetingMinutes()` 调 `/api/v1/meeting-minutes/process`；② src/renderer 增会议纪要处理 UI 组件；③ startup worker 显式调 `ensure_governance_schema` 让治理表非惰性创建（否则首调前 join agent_run_log 的查询会"no such table"）。

**新增次生问题：** 一旦前端接通触发首次 process，`ensure_governance_schema` 惰性建表会在生产首调时发生 schema 写——并发首调存在建表竞态，应前移到 startup。

---

## 遍3 该钉死的最后未决点

1. **【簇 E / 簇 F 缺失】** 本次输入 JSON 在簇 D 的 fix 字段中途被截断（`增加会议纪要处理UI组`止），**原始 6 簇中的 E、F 两簇根因/铁证/修复完全未送达**——遍3 必须补齐 E、F 的输入再合成，当前报告对 E/F 只能标"待定"。
2. **【A 来源定性】** 真库 7 个孤列究竟是用户手工 ALTER 还是某外部工具——直接决定"补定义+迁移"还是"回退删列"两条互斥路径，必须先问用户/查 shell history 钉死，不能两路并存。
3. **【C 上游 603 local 真根因】** `badge_engine.py:1148-1153` try/except 吞异常导致 signal 从未进 pending，是与 :149 并列的第二独立断点；本簇 L1-L4 不覆盖它，遍3 须把它单列为子根因否则修完 failed 仍有 603 条永远不动。
4. **【B 分类正确性依赖】** `mapSyncErrorToReasonCode` 把 4xx 业务拒绝 vs 网络瞬时错的分类若有误判，新逻辑会让坏数据无限重试或让可恢复数据被永久冻结——遍3 须单独核证该映射函数的完备性。
5. **【D 意图确认】** 会议链前端未接是"未完成"还是"刻意暂缓"——P1/P2 定级与是否立即投入前端工时取决于此，须用户拍板，不可代为假设。

**相关文件（绝对路径）：**
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/db.py`（:75-95 表定义、:96-97 索引、~2580 _ensure_column 链）
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/main.py`（:5328 崩点、:39354 会议端点、:3720-3869 startup）
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/mobile/lib/sync-engine.ts`（:45/:467/:563-582）
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/mobile/lib/local-db.ts`（:1576/:1944）
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/growth_sync.py`（:149/:156-162/:178-181/:209-223）
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/handbook_sync.py`（:87）
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/badge_engine.py`（:1148-1153 吞异常）
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/agent_governance.py`（:140 惰性建表）
- 真库：`/Users/guyuanyuan/Library/Application Support/YiyuThinkTankWorkbench2/app.db`

---
## E/F 两簇(从raw补全)

### 簇 E_cross_table_integrity  (为何存在:real_problem 复核:P1)
- 根因: Missing FOREIGN KEY constraint on atomic_facts.source_v2_document_id at backend/app/db.py:2763-2781. The schema definition (CREATE TABLE IF NOT EXISTS atomic_facts) has source_v2_document_id TEXT field but only declares FOREIGN KEYs for client_id, subject_entity_id, and source_v2_chunk_id. Missing FK: FOREIGN KEY(source_v2_document_id) REFERENCES v2_documents(id) ON DELETE SET NULL. This allows orphan atomic_facts records when v2_documents are deleted via backend/app/main.py (lines containing "DELETE FROM v2_documents WHERE id = ?" and "DELETE FROM v2_documents WHERE document_id = ?") without cascading cleanup.
- 修复范围: 1. **Primary Fix** (backend/app/db.py:2763-2781): Add FOREIGN KEY constraint to atomic_facts.source_v2_document_id. Change line 2780 from FOREIGN KEY(source_v2_chunk_id) REFERENCES v2_chunks(id) ON DELETE SET NULL to add one more constraint: FOREIGN KEY(source_v2_document_id) REFERENCES v2_documents(id) ON DELETE SET NULL.

2. **Secondary Orphan Cleanup** (database migration required): Remove 4 orphan atomic_facts records with IDs: acc6f3bb-d672-495f-9c79-6c0c99d68839, 39120e4b-827a-4c46-b2a8-af21d148929f, 274b345d-ed48-4f11-aeb9-edd10f7105e6, ff67d068-2584-4aba-8a0c-51437a35c526 (created 2026-05-18 and 2026-05-31, source_v2_documents deleted or non-existent).

3. **Document Recycle Bin Integrity** (backend/app/db.py:2875-2896): Add FOREIGN KEY constraint to document_recycle_bin.original_v2_document_id. The table has 25 orphan records (original_v2_document_id pointing to deleted v2_documents). Add: FOREIGN KEY(original_v2_document_id) REFERENCES v2_documents(id) ON DELETE CASCADE after line 2895.

4. **Key Decisions & Org Events** (backend/app/db.py:3444-3518): Add FOREIGN KEY constraints to both tables for source_v2_document_id field (and source_v2_chunk_id for consistency). Currently have 0 orphans but missing constraints allow future violations. key_decisions line 3475, org_events line 3517.

5. **Data Preservation Strategy**: For the 4 atomic_facts orphans—determine if they have analytical value. If they were extracted from documents now deleted, consider archiving before deletion. If not valuable, delete them during migration.
- 次生:
  - [P2] narrative_synthesis_runner module missing but referenced | backend/app/services/local_model_optimizer.py:997 imports from app.services.task_runners.narrative_synthesis_runner which does not exist at backend/app/services/task_runners/narrative_synthesis_runner.py. Type annotation 'type: ignore[import-not-found]' indicates awareness of missing module. However, no code path enqueues TASK_TYPE_NARRATIVE_SYNTHESIS='narrative_synthesis' tasks (grep shows only definition and constant registration in TASK_TYPES set at line 33, no enqueue() calls). If task type is never enqueued, dead code path is harmless; if future code enqueues it, will crash at runtime.
  - [P1] 25 orphan records in document_recycle_bin table | True database query: SELECT COUNT(*) FROM document_recycle_bin WHERE NOT EXISTS (SELECT 1 FROM v2_documents WHERE v2_documents.id = document_recycle_bin.original_v2_document_id) returns 25. These are files recycled/deleted with v2_document references already gone. Root cause: missing FK constraint on original_v2_document_id (backend/app/db.py:2878, no FK defined)
  - [P1] relationship_triples has proper FK but key_decisions/org_events do not | backend/app/db.py line 2750 shows relationship_triples correctly has FOREIGN KEY(source_v2_document_id) REFERENCES v2_documents(id) ON DELETE SET NULL. But key_decisions (line 3448) and org_events (line 3506) define source_v2_document_id field without FK constraint. Currently 0 orphans detected, but schema is inconsistent and allows future violations. Semantically, these tables represent decisions and events derived from documents—losing document reference without cleanup is data loss.
  - [P1] v2_documents deletion pathways ignore atomic_facts cleanup | backend/app/main.py contains three DELETE FROM v2_documents statements (lines with 'DELETE FROM v2_documents WHERE id = ?' and 'DELETE FROM v2_documents WHERE document_id = ?'). These deletions trigger ON DELETE CASCADE for v2_sections, v2_chunks, entity_mentions (which have proper FKs), but DO NOT cleanup atomic_facts because the FK constraint does not exist. The comment on line 2748-2750 acknowledges FKs protect cascade; missing atomic_facts FK breaks this protection.

### 簇 F_data_center_consume  (为何存在:partial 复核:P1)
- 根因: 【硬编码 1800 字符定额 + 固定 top-N 限额】数据中心消费端对厚数据的利用存在多层硬截断:

(1) **understanding/prompt 中的 1800 字符硬编码** (文件:/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/understanding_builder.py:37,ai.py:2568/4911, review_narrative.py 等 12+ 处)
   → max_tokens=1800 对应约 450-500 汉字。但日慈客户有 988 个 atomic_facts + 1054 entities,CFFC 有 883 facts + 1855 entities。
   → understanding() 调用时最多消费 200 个 atomic_facts(collect_client_fact_bundle::atomic_fact_limit=200),其中 CFFC 有 883 条,被截 77.3%。

(2) **固定 top-N 限额** (narrative_collector.py:338-351)
   - person_limit=60 (CFFC 实际 137 人,截 56%)
   - time_anchor_limit=30
   - atomic_fact_limit=200 (最严重:CFFC 883 facts → 200, 683 条丢弃 = 77.3%)
   - activity_limit=80
   - document_limit=60 (CFFC 249 文档 → 60)
   - chunk_limit: 默认无,按模块预算动态截(workspace_data_center_adapter.py:1649-1680 content_budget=max(1800,...))

(3) **向量检索存在但 LIKE 回退有损** (strategic_narrative_semantic_retriever.py:139-150)
   → 有向量检索 (retrieve_knowledge_bundle), 但降级到 LIKE 关键词时用 _retrieve_top_chunks(), 缺排序(无向量得分 rerank)。

(4) **module_budget 动态截断** (workspace_data_center_adapter.py:1649-1650)
   ```python
   content_budget = max(1800, max_chars - sum(len(line) for line in blocks) - 80)
   module_budget = max(1800, content_budget // max(1, min(len(ordered_modules), 4)))
   ```
   → 最多 4 个 DNA 模块 × 1800 字符=7200 字符上限。6 个模块时平均每个 1200 字符。

根本原因: 本地 LLM (豆包/文心) token 预算有限, 设计者采用"先冻结为待拆规则"方式硬卡各层(understanding_builder.py:335 注释),未实现动态预算分配或优先级 rerank。
- 修复范围: 5 处修复:
① understanding_builder.py:200/346: atomic_fact_limit 从 200 扩至客户实际数量(冻结 883 max),person_limit 同理 60→137。
② workspace_data_center_adapter.py:1649-1650: content_budget/module_budget 改动态计算,based on prompt 复杂度(短 prompt→全数据,长 prompt→摘要)。
③ narrative_collector.py:338-350: 每层 limit 改参数化而非硬编码,calibrate against cloud token budget(文件:1615 max_chars=18000 字符=4500-6000 tokens)。
④ evidence_selector.py: 注释(line 167) "对读多少资料的硬裁剪" 改为基于语义覆盖率 (coverage_targets_for_focus) 的动态选取。
⑤ ai.py: _qwen_generate() 的 max_tokens 参数与 context_summary 长度联动(更长上下文→更高 token limit),而非固定。
- 次生:
  - [P1] atomic_facts 利用率严重不足 (CFFC 77.3% 数据被丢弃) | narrative_collector.py:1029-1054 LIMIT 200 固定 vs 实际数据: CFFC client_a4d1db29a7 有 883 atomic_facts, 日慈 988, 云南 147。collector 设 200 上限 → 平均丢弃 65% 中位以下的事实。真库查询证实:db 中 atomic_facts 表 2288 条,分布在 13 个客户,最大 988 条未被充分消费。
  - [P1] 人物/时间锚数据消费不对等 (person 限 60 vs 实际 137) | narrative_collector.py:952-1003 person_limit/time_anchor_limit 硬编码 60/30,但 CFFC 有 1855 entities (其中 person 137), 日慈 1054 entities。person_limit=60 时 CFFC 关键人物漏掉 56%。这直接影响 Layer 4 (people) 叙事质量,因为少了项目负责人/对接人的关联。
  - [P2] 向量检索降级到 LIKE 搜索时无 rerank (语义得分损失) | strategic_narrative_semantic_retriever.py:150 retrieve_knowledge_bundle 可用,但 LIKE 降级调用 _retrieve_top_chunks() 后无向量得分重排。dimension_chunks 虽含 score 字段,但 LIKE 回落时未按 BM25/TF-IDF 重新排序,只是顺序返回。结果: 叙事取材质量低于语义期望。
  - [P2] build_template_fill_context 文档摘要阶段性截断 (18000 字符=4500-6000 tokens) | workspace_data_center_adapter.py:1615-1708 DNA tool 模块定额法: max_chars=18000, content_budget=(18000 - blocks - 80), module_budget=(content_budget / 4). 最坏情况: 6 个模块各 1800 字符=10800 字符丢弃。如客户有 10 个差异化 DNA 模块,后 4 个完全消失。无法通过 prompt 复杂度或用户权限改动预算。
  - [P2] narrative_generator 消费层缺可观测性 (未见数据源品质评分) | narrative_generator.py 全 1200 行,接收 ClientFactBundle (已聚合), 向 LLM 喂数据时未标注: 该 bundle 覆盖率是否完整、哪些维度数据缺失、有多少 facts 被 atomic_fact_limit=200 丢弃。用户看到的 6 段叙事无法判断背后用了 883 facts 的 22.6% 还是 100%。
  - [P2] CFFC 深读索引只覆盖 CFFC,其他客户回退 v2_instant (稀疏索引) | memory 中记录: '深加工只对 CFFC 跑过(157),日慈等几乎全 0 只有 v2_instant 薄索引'。narrative_collector.py 没有按客户条件过滤深读索引使用,结果所有客户叙事都降级回薄索引。这是 feature 未全量铺开而非代码缺陷,但客户数据消费差异化严重。
