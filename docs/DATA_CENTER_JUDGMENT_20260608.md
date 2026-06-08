# 数据中心 · 判断层(铁证)— 2026-06-08

> 基于 [DATA_CENTER_GROUND_TRUTH_20260608.md](./DATA_CENTER_GROUND_TRUTH_20260608.md)(DB事实)+ [CODEMAPS/data-flow/DATA_CENTER_LEDGER_20260608.md](./CODEMAPS/data-flow/DATA_CENTER_LEDGER_20260608.md)(机器读写边,eval通过)。每条判断挂 file:line / 真库数字。方法:gather全→judge→沿判断follow到根因。**推翻了旧记忆数处,逐条标注。**

## J1 采集侧:唯一活跃产facts路径=文档导入inline抽取;深读worker不产fact
- **inline 抽取链(活)**:`ingest_document_knowledge`(knowledge_v2.py:2114 / knowledge_base.py:2802)→ `persist_chunk_facts`(→atomic_facts)+`persist_chunk_relations`(→relationship_triples)+`upsert_surrogate_record`(→knowledge_surrogates)。**6 端点可达**:upload_task_attachment(53434)、create_client_document_from_text(49576)、event_line_report_snapshot(34329)、internet_pdf_worker、backfill_workspace_import(50039)、retry_parse_failures(42800)。
- **深读 worker(local_model_optimizer)——推翻旧"总阀门enabled=False永不产fact"**:worker 路径在代码里存在(`ingest←fact_extract_runner.process←run_due_local_model_tasks←local_model_optimizer_worker_loop`),且 local_model_tasks **107 completed**(跑过)。**但 task_type 实测只有 document_card_generation/document_path_optimization/visual_ocr,fact_extraction 任务数=0**——worker 活着但从不抽 fact。enabled 是 runtime 设置(:40 默认False,:953/1038 可 force)。
- **结论**:增量 facts 停(6月=2)≠管线死,=**inline 路径没新 raw_file 喂**(F-DB-3:真导入停在3-5月)。worker 这条对 fact 增厚无贡献。
- **会议/对话**:process_meeting_minute 有端点(39471);chat `_write_simple_atomic_fact←send_chat_message`(49220)活。

## J2 关系层 relationship_triples:写活·消费死
- 写边活(insert_triple←persist_chunk_relations,同 inline 链);**读边仅 1 个**(list_triples@relation_store.py:143,WHERE 动态)。22行(F-DB-1)。
- **判断**:关系三元组写进去**几乎无人消费**(唯一读者是 generic list),图谱/关联功能实质未用。低产(抽取率低)+ 无消费,双重死。

## J3 周复盘 + 任务理解 组织源:断(铁证·精确机制)
- **两套并存**:legacy `organization_dna_documents`(4行,**0写0读=代码层彻底孤儿**)+ legacy 取数函数 `list_organization_dna_modules()`(main.py:7163 `return []`);live `organization_dna_v2_items`(199行,refresh worker写,get_organization_dna_snapshot/build_organization_dna_tool_context 读)。
- **断点**:**7 处消费点全吃死的 legacy**:main.py 22483 / 24653 / 24666 / 26705 / **26838(周复盘 build_review_context_modules)** / 27268 / **31735(任务理解 org_dna_modules)**。review_narrative 用空 org_dna_modules 渲染"第一层组织DNA/组织背景"(:1885/:2506)→ **空**。
- live 的 v2_items(199)**只接到 1 个独立端点**(main.py:27890 org-DNA查看)+ intelligence,**没接周复盘/任务理解**。
- **判断**:周复盘组织栏 + 任务理解组织块**确实空**(旧判断正确)。根因=消费者指向已退役的 legacy 取数函数,未迁到 v2。修法=7 处重指向 get_organization_dna_snapshot。
- 注:report_context_builder(:380)走 `organization_notebook_snapshots`(13行,client级,活)是另一条线,与周复盘组织栏无关。

## J4 智能填表质量差:根因=user_confirmed 窄过滤饿死(铁证)
- build_template_fill_context(main.py:16786)读 atomic_facts WHERE `status='active' AND verification_status='user_confirmed'`。
- 真库:active facts 1712 中 **user_confirmed 仅 89 = 5.2%**(其余 1623 unverified)。
- **判断**:智能填表只能看到 5.2% 的事实,扔掉 94.8%。"质量差"≠没接数据中心,=**过滤器把厚数据卡成薄数据**(且无 user-confirm 流量使 user_confirmed 长期≈0)。这是旧记忆"唯一没查透"项的根因。

## J5 消费侧整体:接得很满,"薄"来自过滤/截断/输入,非断连
- 读边数(机器实证):atomic_facts **55**、v2_documents **81**、client_glossary **30**、knowledge_surrogates **24**。消费者覆盖:战略陪伴(narrative_collector)、桌面咨询(collect_data_center_context_for_consultation)、company_brain(qa/context_builder)、story_card、project_portrait、语义派生器(derive_risk/commitments/insights)、智能填表、清单优先级、冲突检测…
- **判断**:消费侧是数据中心**最稠密接入面**,远非"薄"。用户感知的薄,根因在 J4 类过滤、1800字符/top-N 截断(旧审计F)、J3 类指错源、以及输入侧 J1(无新料)。

## J6 客户级两极 + 空客户真因(铁证 F-DB-5/6)
- 日慈988+CFFC883=81.8% atomic_facts。汇丰/贝石/顾源源=0 facts。
- **汇丰/贝石**:仅 3 篇 task_doc(md 40-244字符),**无任何 raw_file**;task_doc∈LOW_INFORMATION_SYSTEM_KINDS 设计不抽。顾源源:0文档。→ 0 facts = **无真实输入**,非管线故障(推翻 agent"parse失败/冷启动断")。

## J7 手机全线:本地镜像空 + 桥零调用(DB再证)
- 本地 mirror_* 4 表全 0 行(F-DB-11);桥 publish 端点桌面侧零调用(历史)。
- understanding 读取侧云端镜像空→返回 status='missing' 无 fallback(cloud_backend:2382)。
- **判断**:手机工作台/cockpit/理解/咨询 读云镜像,镜像空→手机理解面板加载不出。最高杠杆断点(旧判断成立)。

## J8 已知技术债(本次 DB/FK 复证)
- **A schema 漂移**:local_identities 真库 25 列(phone/phone_normalized/primary_role/account_status…),代码 db.py:75-95 建表用 `phone_number`(真库无)。仅1行 chenzhenli@klngo.org。
- **E FK 缺失**:atomic_facts.source_v2_document_id **无 FK**(对照 relationship_triples 同列有 FK)→ 删 v2_documents 不清 atomic_facts。

---
## 推翻/修正的旧记忆
1. **深读 worker"总阀门 enabled=False = atomic_facts 永不增"** → 不准。worker 跑过107任务,但只做 card/path/OCR,**从不抽fact**;facts 走 inline 路径;增量停因无新 raw_file。(J1)
2. **agent"汇丰/贝石 parse失败/新客户冷启动断"** → 假。文档 ready,只是全是 task_doc 无 raw_file。(J6)
3. **agent"CFFC 0 DNA/0叙事结构错位"** → 假。narrative_suggestions 表不存在,CFFC 有 4 DNA。(上一轮已证)
4. **"周复盘组织栏断"** → 成立,且本次拿到精确机制(7处吃死legacy,v2_items未接)。(J3)
5. 新增根因:**智能填表质量差 = user_confirmed 5.2% 窄过滤**(J4);**关系层写活消费死**(J2)。

## 沿判断仍需 follow(下一轮 gather 目标)
- 桥/手机:knowledge_mirror_sync(被清)需重写并真打火山云灌数据(J7)。
- J3 修法:7 处重指向 v2 snapshot 的影响面(执行+1 收敛)。
- J4 修法:放宽 user_confirmed→confidence阈值的回归影响。
- 云侧 cloud_backend 账本未扫(本账本仅 backend/app)。
