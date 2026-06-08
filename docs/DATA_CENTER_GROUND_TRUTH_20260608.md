# 数据中心 · 事实层底图(零判断 / 全实证)— 2026-06-08

> 用途:系统性改造的地基。本文件**只记钉死的客观事实**(真库 immutable=1 只读快照 + schema + FK + 进程实证),**不含任何判断/推断/方案**。判断层另起,且必须引用本文件的事实编号。
> 真库:`~/Library/Application Support/YiyuThinkTankWorkbench2/app.db`(277MB,采样时 mtime 推进中,见 F-LIVE)。
> 代码侧读写边账本:`scripts/data_flow_ledger.py --all` 产出(单独文件,本档不含)。

## F-DB-0 库规模
- 表 228 / 视图 7 / 索引 532。
- 有数据表 **174**,空表 **54**。
- 外键关系 **193 条**。

## F-DB-1 数据中心核心表行数(采样快照)
| 表 | 行数 | 客户覆盖(/13) |
|---|---|---|
| v2_chunks | 12459 | — |
| entity_mentions | 12292 | — |
| entities | 5025 | 10 |
| memory_facts | 4129 | 多作用域(见 F-DB-4) |
| atomic_facts | 2288 | 10 |
| v2_documents | 1125 | 12(顾源源=0) |
| knowledge_surrogates | 554 | 10 |
| client_glossary | 407 | 8 |
| fact_contradictions | 81 | 8 |
| commitments | 74 | 4 |
| client_dna_documents | 32 | 8(每户4条) |
| relationship_triples | 22 | 6 |
| risk_signals | 20 | 3 |
| meetings | 7 | 3 |
| organization_dna_documents | 4 | — |

## F-DB-2 atomic_facts 构成(共2288)
- **状态**:active 1712 / superseded 574 / deprecated 2。
- **来源 source_type**:llm_extracted 2002 / client_internal_doc 144 / collaboration_task 89 / client_official_doc 53。
- **按月 created_at**:2026-06=**2** / 2026-05=899 / 2026-04=284 / 2026-03=1103。
- **最新写入**:2026-06-05T07:30(为爱黔行 llm_extracted)。此后无新 fact。
- **客户Top**:日慈988 / CFFC883 / 云南儿童147 / 益语97 / 顾源源文章48。

## F-DB-3 v2_documents 构成(共1125)
- **canonical_kind**:raw_file 601 / task_doc 230 / internet_source_doc 153 / judgment_doc 38 / event_line_doc 27 / wechat_article_excerpt 14 / internet_fact_card 14 / review_entry_doc 13 / project_enrichment_doc 8 / meeting_doc 7 / calendar_doc 7 / review_doc 5 / project_doc 4 / event_line_update_doc 3 / policy_context_doc 1。
- **parse_status**:ready 1049 / failed 52 / completed 14 / partial_ready 10。
- **真实大批量导入在 3-5 月**:3/14 一次146篇、4/8 一次68篇、5/16 一次41篇…(imported_at 聚集)。
- 今日(6/8)的 imported_at/updated_at 推进**全是 task_doc**(见 F-LIVE)。

## F-DB-4 memory_facts 是多作用域记忆层(≠atomic_facts)
- **无 client_id 列**;靠 scope_type/scope_id 归属。
- scope_type:task 1895 / client 1623 / event_line 573 / person 22 / product 16。
- source_type:task 2819 / document_knowledge_backfill 450 / organization_notebook 191 / task_attachment 164 / document 135 / chat_extraction 112。
- visibility_scope:全 4129 = project_public。

## F-DB-5 per-client 厚度矩阵(钉死)
| 客户 | atomic | entities | rel | contra | surro | gloss | v2doc | dna | meet | commit | risk |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 日慈基金会 | 988 | 1054 | 10 | 15 | 148 | 82 | 249 | 4 | 1 | 41 | 2 |
| CFFC | 883 | 1855 | 3 | 34 | 159 | 58 | 188 | 4 | 5 | 0 | 0 |
| 云南儿童资助研究 | 147 | 775 | 6 | 3 | 82 | 62 | 128 | 4 | 0 | 0 | 0 |
| 益语智库 | 97 | 348 | 0 | 15 | 13 | 0 | 191 | 4 | 1 | 0 | 0 |
| 顾源源文章 | 48 | 34 | 0 | 1 | 6 | 0 | 26 | 0 | 0 | 0 | 0 |
| 为爱黔行 | 46 | 326 | 1 | 2 | 77 | 38 | 185 | 4 | 0 | 22 | 7 |
| 善加基金会 | 26 | 361 | 1 | 9 | 43 | 28 | 56 | 4 | 0 | 4 | 0 |
| 士平——足球 | 26 | 198 | 1 | 2 | 16 | 52 | 20 | 0 | 0 | 7 | 11 |
| 新思考 | 21 | 51 | 0 | 0 | 8 | 44 | 39 | 4 | 0 | 0 | 0 |
| 乡村发展基金会 | 6 | 23 | 0 | 0 | 2 | 43 | 37 | 4 | 0 | 0 | 0 |
| 汇丰 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 0 |
| 贝石基金会 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 0 |
| 顾源源 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
- 集中度:日慈+CFFC = 1871/2288 atomic_facts = **81.8%**。

## F-DB-6 汇丰/贝石"0 facts"真因(钉死)
- 汇丰 3 文档、贝石 3 文档,**全部 kind=task_doc**(md 长度 40-244 字符,各 1 chunk)。
- task_doc ∈ `LOW_INFORMATION_SYSTEM_KINDS`(代码 knowledge_v2.py:4780)→ **设计上不抽 facts**。
- 两户**从未上传任何 raw_file**。顾源源连 v2_documents 都为 0。
- → 非"parse失败"、非"管线死";是**无真实文档输入**。

## F-DB-7 各客户增量新鲜度(v2_documents last_import,排除今日task_doc噪声)
- 真实最近导入:新思考 5/31、乡村 5/21、顾源源文章 5/12;其余客户的真 raw_file 导入集中在 3-5 月。
- 顾源源:无任何导入(None)。

## F-DB-8 外键事实(摘关键)
- atomic_facts:client_id→clients(CASCADE)、source_v2_chunk_id→v2_chunks(SET NULL)、subject_entity_id→entities(SET NULL)。
- **atomic_facts.source_v2_document_id 无 FK**(对照 relationship_triples.source_v2_document_id→v2_documents 有 FK)→ 删 v2_documents 不清 atomic_facts(审计 E,客观成立)。
- 会议域 8 张表(action_items/agenda_items/ambiguities/decisions/risks/evidence_refs/meeting_sources/experience_story_drafts)全 FK→meetings(多数 CASCADE)。

## F-DB-9 local_identities schema 漂移(审计 A,钉死)
- 真库 **25 列**:id,email,**phone,phone_normalized**,full_name,password_hash,**primary_role,account_status,membership_status**,...,local_organization_id,local_organization_name,organization_mode,...,is_department_lead,bound_cloud_user_id,...。
- 仅 1 行:chenzhenli@klngo.org(乐乐),primary_role=employee,account_status=approved,membership_status=pending,local-pending-org。
- 代码 db.py:75-95 建表用 `phone_number`(真库无此列,真列是 phone/phone_normalized)。

## F-DB-10 视图(7)
- v_active_clients = clients WHERE stage!='frozen';v_pending_tasks = tasks status∈(todo,doing)。
- v_client_facts = 每客户聚合(active_event_count/open_commitments/pending_tasks/glossary_attribute_count,后者取自 glossary_attributes 808行)。
- v_searchable_knowledge = knowledge_master_index WHERE len(searchable_text)>0 AND client 活跃。
- **v_user_visible_clients LEFT JOIN mirror_client_related_users**(该表**空**)→ viewer_user_id 全 NULL。
- org_members_v、v_active_event_lines。

## F-DB-11 空表 54 张(性质)
- 被活表 FK 指向的仅:execution_tickets←execution_ticket_logs、proposal_records←execution_tickets(自包含 execution-ticket 功能簇,未用)。
- **mirror_* 本地镜像 4 张全空**:mirror_organizations(5列)/mirror_users(19)/mirror_departments(10)/mirror_client_related_users(5)。
- R4 相关空表:data_gaps、external_evidence_cards、data_center_proposal_drafts。
- 桥相关空表:**data_center_sync_outbox**(半拉子桥,无消费端)、sync_outbox、team_sync_state、sync_conflicts。
- 其余多为 ai_*/intelligence_*/event_line_*/workspace_*_review 等特性表未落数据。

## F-LIVE 真库正在被实时写入(改造期地动 — 必读)
- 采样期间真库 mtime:19:46 → 19:51:14 持续推进;WAL 4.2MB 活跃。
- **持有并写入进程 = pid 80870**(`runtime/backend-venv/bin/python`,YIYU_WORKBENCH_DATA_DIR=真 YiyuThinkTankWorkbench2),即**运行中的后端实例**(dev 已启动,Electron 61494 + uvicorn 61497/61507 同在)。
- 写入内容 = **task_doc**(v2_documents.updated_at 19:51:12/13/14 连续,全 task_doc);今日 data_center_ingest_events 14 条**全 source_type=task**(12 ready / 2 skipped_orphan_client)。
- **结论性事实**:当前"增量"100% 是运行中 app 的 task 派生 churn(设计不产 facts);真正产 facts 的 raw_file 导入 6/5 后停止。
- 操作纪律:审计/改造一律对真库用 immutable=1 只读快照;真库是活的,勿直接写。

---
*采集者:Claude(排+1 事实层)。代码侧读写边账本由 data_flow_ledger.py --all 产出后并入,判断层另起并引用本文件 F-编号。*
