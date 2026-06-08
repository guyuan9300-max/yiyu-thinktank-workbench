I have all the confirmed findings from pass 1, pass 2, and the pass 3 technical settlements. Now I'll synthesize the final P0-prioritized, deduplicated, iron-clad audit.

# 主仓库审计【定版】报告 (三遍合成 · 2026-06-08)

> 方法:遍1 广扫(43 agent/2.7M tok)→遍2 深钻+对抗复核(13 agent/739K tok,6簇全 upheld 无证伪)→遍3 钉死 4 处技术未决(库铁证)。只读不动代码。仓库正被并行 AI churn,file:line 为当前快照。真库:`/Users/guyuanyuan/Library/Application Support/YiyuThinkTankWorkbench2/app.db`。

---

## ① 一句话总览 + 各级计数

**一句话总览**:6 个独立根因簇全部经直接库查 + 代码核证 + 对抗复核**确证无证伪**;无不可逆 P0 级数据已删,但有 **2 个会崩(A 本地登录读崩 / B 手机离线永久冻结)+ 3 个会静默丢数据(C 云同步 99.7% 卡死含上游 603 / E 跨表 FK 孤儿 / D 会议链整条不可达)+ 1 个厚数据严重欠消费(F)**,全部需发版前处理。其中 C/D/F 性质为 partial(半成品/未完成,非黑箱缺陷),已据此降级评估。

**各级计数(主根因簇)**:P0 = 0 ｜ **P1 = 6 簇(A/B/C/D/E/F)** ｜ 待用户拍板 = 2(见 ③)
**次生问题计数(枚举簇 A–F)**:P0 = 1(A 单点崩溃确定性)｜ P1 = 14 ｜ P2 = 12 ｜ P3 = 5

---

## ② 各根因簇(铁证根因 + 为何存在 + 严重级 + 精确修复范围 + 关键次生)

### 簇 A — `local_identities` 代码/真库 schema 漂移 → 本地登录/注册即崩

**铁证根因**:`db.py:75-95` 的 `CREATE TABLE local_identities` 定义 `phone_number`,但真库 `PRAGMA table_info` 实为 `phone`(col2)+`phone_normalized`(col3 UNIQUE),且多出 7 列(`primary_role` 真库默认 `'employee'`、`account_status`、`is_department_lead`、`local_organization_id` NOT NULL 无默认 等)。真库 25 列 / 新装库 19 列。`_ensure_column` 链覆盖 50+ 其他表却**独缺 local_identities**(`grep '_ensure_column.*local_identities'` 为空),既有库无法升级、新装库 schema 不完整。

**为何存在判定**:**real_problem**(漂移是 PRAGMA 物理事实,非理解偏差)。真库现存 1 行(chenzhenli@klngo.org)创建于 schema 变更前,打包版仍写 `phone_number` → 7 列系 **git 外手工 ALTER**(待用户确认,见 ③-A)。

**严重级**:**P1**(触发即必崩、阻断该用户登录,但不腐蚀数据)。

**精确修复范围**:
1. 先定来源(`git log` + 问用户),再二选一:保留 → `db.py:75-95` 补 7 列 CREATE 定义 + 补 `_ensure_column` 链(`db.py` ~2580);误操作 → 导出该行后回退删列。
2. `main.py:5328` `str(row["phone_number"] or "")` 无 try/except → 改 `row["phone"] if "phone" in row.keys() else ...` 容错(sqlite3.Row 用 `in row.keys()` 判存在,**禁用 `.get()`**——见用户 MEMORY)。
3. `main.py:30889`(重复校验)、`:30900`(INSERT)、`:30942`(查询)全部 `phone_number` 读写点统一改 `phone`/`phone_normalized`。
4. `db.py:96-97` 索引 `idx_local_identities_phone(phone_number)` 须随表定义同步改列名。
5. `local_organization_id` 真库 NOT NULL 无默认 → 注册 INSERT 补齐或改 `DEFAULT ''`。

**关键次生**:补 `_ensure_column` 给老库 ALTER 时,默认值别覆盖既有值(真库 `primary_role='employee'` vs db.py 拟用 `'admin'`);改 5328 后须确认 `SessionUserRecord.phone` 取 `phone`(原始)还是 `phone_normalized`。**次生最高 P0**:就 `main.py:5328` 单点而言,从真库读 `phone_number` 触发 `sqlite3.Row IndexError`,注册/登录响应构建 100% 崩溃。

---

### 簇 B — 手机端离线任务 5 次重试后永久冻结(不区分错误类型)

**铁证根因**:`sync-engine.ts:467` 在发任何请求**之前**先判 `op.retryCount >= MAX_OP_RETRIES`(`:45`=5)直接 `markOpFailed(...,"needs_attention")`;catch 块(`:563-582`)对**任意错误类型**(含瞬时 `network_unavailable`)一律递增 retry_count,`:566` 的 `nextStatus` 决策**只看 retryCount 阈值、不分流 reasonCode**(`:565` 已提取 reasonCode 却不参与分支)。`local-db.ts:1576` `getPendingOps` 用 `WHERE status != 'needs_attention'` 永久剔除已标记 op。`grep netinfo = 0`(确认无网络监听)→ 离线 5 次(每 2min)耗尽预算后永久冻结,重连无即时触发。`requeueOp`(`local-db.ts:1944`)正确 `retry_count=0` 仅靠 UI 手动触发。

**为何存在判定**:**partial**。"达上限→needs_attention 等人工"是有意终态;但"瞬时网络错也消耗预算"+"无重连触发"是设计缺口,非有意。

**严重级**:**P1**(用户离线建任务联网后永久丢失,6/4 记忆已标 unfixed)。

**精确修复范围**:
1. (P1)catch 块按 reasonCode 分流:`network_unavailable` 不增 retry_count、保持 `queued`(`sync-engine.ts:563-582`)。
2. (P1)`AppState` 订阅(`:268`)后加 NetInfo 监听,`unavailable→available` 立即 `void performSync()`。
3. (前置)确认 `requeueOp` 的 `retry_count=0` 已部署(库注释证实在位)。
4. 配指数退避防瞬时错"无限留 queued"轮询风暴(次生 P2)。

**关键次生(并入遍3-④)**:分流正确性**强依赖 `mapSyncErrorToReasonCode` 的完备性**——经遍3 核证该函数有**分类断层**:`mobile/lib/types.ts:47-57` 定义 10 个 `SyncReasonCode`,但 `sync-errors.ts:4-14` 仅生成 7 个,`thermal_blocked`/`model_unavailable` **永不可达**(types 定义 + UI 格式化但无生成逻辑);404/410/429/500/502/503/504 全部塌缩为 `server_rejected`(`:11` catch-all)→ 丢失"404 该终态 / 429·5xx 该重试"的语义。**风险**:若 B 新逻辑误判 4xx 业务拒绝为可重试,坏数据无限重试;误判可恢复网络错为终态,可恢复数据被永久冻结。
- 修复(B 簇 P2 范围,低风险):`sync-errors.ts` 显式补 404/410→`validation_failed`,429/5xx→`server_rejected`(保持重试);对 `file_missing`/`thermal_blocked`/`model_unavailable` 加注释说明非本函数生成(`file_missing` 实为 `record-note-service.ts` 的 legacy upload 语义,与 task sync 同名跨域污染)。
- **唯一入口确证**:`sync-engine.ts:565→567 markOpFailed→569 setTaskRemoteState`,无其他路径生成 task 的 reasonCode。

**次生(7)**:无 NetInfo(P1)、网络错耗满预算(P1)、getPendingOps 排除 needs_attention 阻断手动同步(P1)、reasonCode 提取后不分支(P1)、markOpFailed 无条件 needs_attention(P1)、无指数退避(P2)、后台 fetch 不随连接态自适应(P2)。

---

### 簇 C — 成长/手册云同步 failed 永不重扫 + 上游 603 local 永不进 pending

**铁证根因(两个独立断点)**:
- **断点①(下游 failed 死锁)**:`growth_sync.py:149` `WHERE sync_status='pending'` 排除 'failed';HTTP 错误(`:178-181`)与缺 `signal_id`(`:156-162`)均标 'failed' **不可逆**,无 'failed'→'pending' 转态、无 retry_count/backoff/admin API。`handbook_sync.py:87` 同构。**库铁证:`growth_signal_events` = 71 failed / 603 local / 2 synced(成功率 0.3%)**,failed 跨 5/28~6/05 连续 8 天。evidence push 以云端 `signal_id` 存在为先决(`:209-223` + 云端 `main.py:19874-19879` 严检)→ signal 失败级联 evidence 失败死锁。
- **断点②(上游 603 local 永不进 pending,遍3 钉死)**:**机制 1(591 条历史记录)**:`growth_signal_events` 自 3/25 建表起持续产生记录,`sync_status` 列经 `_ensure_column` 于 5/27(commit 0b3f9b7)以 `DEFAULT 'local'` 补入,591 条 5/13~5/26 的旧记录继承 'local' 但从无 `mark_signal_pending()` 回填(`updated_at=''` 证实从未运行),**无 backfill 迁移**。**机制 2(7+ 条新记录吞异常)**:5/27 后 7 条(5 task_context_candidate + 2 review_insight_pending)经 `growth_engine.py:3118-3123`/`badge_engine.py:1147-1153`/`local_memory.py:327-332` 三处 try/except 仅 log warning;`mark_signal_pending()` 任何抛错(db lock/事务/连接)被静默吞,INSERT 成功但 `growth_sync.py:39-45` 的 UPDATE 永不发生 → 永久停在 DEFAULT 'local',无重试。

**为何存在判定**:**partial**。failed 是可观察终态(注释 `:8-9` 状态机)但**无显式人工干预 API**;吞异常是真缺陷(非有意)。

**严重级**:**P1**(99.7% 阻断 + FK 级联 + 8 天无自愈 + 云为权威源 + 用户无 UI 自救)。

**精确修复范围(四层 + 两个上游修复)**:
- **L1 立即**:`growth_sync.py:149`/`handbook_sync.py:87` 改 `sync_status IN ('pending','failed')`,**只扩扫描不做 failed→pending 自动转态**(无数据丢失)。
- **L2**:加 `attempt_count`/`max_attempt_count`/`last_attempt_at` + 退避(5/15min/手工),幂等 UPSERT。
- **L3 FK 屏障**:evidence push 前筛出对应 signal 仍 failed/local 的,defer 跳过本轮不标 failed,杜绝级联(`growth_sync.py:209-223`)。
- **L4 监控**:`GET /api/v1/admin/sync-status` + 告警(`main.py:3322-3331` 日志)。
- **上游修复 #1(backfill,治 591 条)**:app 启动 schema 迁移后一次性 `UPDATE growth_signal_events SET sync_status='pending', pending_sync_action='upsert', updated_at=<now> WHERE sync_status='local' AND last_synced_at IS NULL`,settings 表置 flag 保证只跑一次。位置:`main.py` `init_database_with_migration_guard()` / post-schema-init hook。
- **上游修复 #2(治吞异常,防未来 local 陷阱)**:推荐 **Option A 快速失败**——移除 `growth_engine.py:3118-3123`/`badge_engine.py:1147-1153`/`local_memory.py:327-332` 三处 try/except 让异常传播暴露问题;或 Option B 加 `pending_mark_failed` 标志位 + 后台重试 worker。

**关键次生**:L1 扩 failed 重扫后,确定性失败(payload schema 不合)会每轮刷日志 → **必须 L2 的 attempt_count 上限同时上**,否则把"永久卡死"换成"永久重试"。

**次生(4)**:handbook 同构隐患(P2)、evidence 本地侧无 signal-synced 预检(P2)、FK 不对称成孤儿(P3)、云端 growth 表无 sync_status/幂等字段(P3)。

---

### 簇 D — 会议链后端完成、前端从未接(整条数据链不可达)

**铁证根因**:后端三层完整(`agent_governance.py` 建表、`meeting_minute_processor.py:147-486` 端到端、双层 log),端点 `/api/v1/meeting-minutes/process` 在 `main.py:39354` 确实存在。但 **`grep "meeting-minutes/process" src/renderer/ = 空**(核证)**,src/renderer 无 Meeting*/minute* 组件,mobile 无相关字面量**。真库 `agent_run_log`/`approval_queue` 两表均不存在(sqlite_master 无返回),`event_line_activities` source_type='meeting_minute' = 0、`strategic_thought_insights` insight_type='meeting_judgment' = 0。根因双重:① 前端从不调端点;② `ensure_governance_schema` 仅惰性触发(`agent_governance.py:140` `log_agent_run_start` 内),startup worker(`main.py:3720`)未显式调 → 表永不创建。git 确认 code 自 5/23 即在 main,前端 UI 始终未跟进。

**为何存在判定**:**partial**(有意建好的 R2 能力,前端未接是**未完成**而非缺陷)。

**严重级**:**P1**(整条价值链不可用;若判定"刻意暂缓上线"则降 P2,需用户拍板,见 ③-D)。

**精确修复范围**:
1. `src/renderer/lib/api.ts` 新增 `processMeetingMinutes()` 调 `/api/v1/meeting-minutes/process`。
2. src/renderer 增会议纪要处理 UI 组件。
3. startup worker(`main.py:3720`)显式调 `ensure_governance_schema(state.db)`,移除惰性建表 anti-pattern。

**关键次生**:不前移建表的话,前端首次触发 process 时 `ensure_governance_schema` 在生产首调发生 schema 写,**并发首调存在建表竞态**;且首调前任何 join `agent_run_log` 的查询会 `no such table`。

---

### 簇 E — `atomic_facts.source_v2_document_id` 缺 FK → 文档删除留孤儿(跨表完整性)

**铁证根因**:`db.py:2763-2781` `CREATE TABLE atomic_facts` 定义 `source_v2_document_id TEXT`(`:2773`)但 FK 仅覆盖 client_id/subject_entity_id/source_v2_chunk_id,**独缺 `FOREIGN KEY(source_v2_document_id) REFERENCES v2_documents(id) ON DELETE SET NULL`**。`relationship_triples`(`:2750`)正确实现了同款 FK,证明模式已知,遗漏系意外(始于 commit 49ebe82)。`main.py` 三处 `DELETE FROM v2_documents` 触发其他表 CASCADE 但**不清理 atomic_facts**。**库铁证:4 条孤儿**(acc6f3bb.../39120e4b.../274b345d.../ff67d068...,指向已删 v2_documents);**另 25 条孤儿在 `document_recycle_bin.original_v2_document_id`**(`db.py:2875-2896` 无 FK)。

**为何存在判定**:**real_problem**(库查 4+25 孤儿是物理事实)。

**严重级**:**P1**(已发生数据完整性丢失:facts 失去文档溯源)。

**精确修复范围**:
1. `db.py:2780` 后补 `FOREIGN KEY(source_v2_document_id) REFERENCES v2_documents(id) ON DELETE SET NULL`。
2. 迁移清理 4 条 atomic_facts 孤儿(先评估分析价值,有值则归档后删)。
3. `db.py:2895` 后补 `document_recycle_bin.original_v2_document_id` FK(`ON DELETE CASCADE`),清 25 条孤儿。
4. `key_decisions`(`db.py:3475`)、`org_events`(`:3517`)补 `source_v2_document_id` FK(当前 0 孤儿但 schema 不一致允许未来违约)。

**次生**:`narrative_synthesis_runner` 模块缺失但被 `local_model_optimizer.py:997` import(`type:ignore[import-not-found]`,无 enqueue 路径故当前无害,未来 enqueue 会崩,P2)。

---

### 簇 F — 数据中心消费侧厚数据严重欠消费(硬编码定额 + 固定 top-N)

**铁证根因**:消费端多层硬截断:
- (1)**1800 字符硬编码**(`understanding_builder.py:37`、`ai.py:2568/4911`、`review_narrative.py` 等 12+ 处),约 450-500 汉字。
- (2)**固定 top-N**(`narrative_collector.py:338-351`):`atomic_fact_limit=200`(CFFC 883 facts → 截 77.3%)、`person_limit=60`(CFFC 137 人 → 截 56%)、`document_limit=60`(CFFC 249 文档)、time_anchor_limit=30、activity_limit=80。
- (3)**向量检索降级 LIKE 无 rerank**(`strategic_narrative_semantic_retriever.py:139-150`)。
- (4)**module_budget 动态截断**(`workspace_data_center_adapter.py:1649-1650`):最多 4 个 DNA 模块 × 1800 = 7200 字符上限,6 模块时各 1200。
- 根本:本地 LLM token 预算有限,设计者"先冻结为待拆规则"硬卡(`understanding_builder.py:335` 注释),未实现动态预算/优先级 rerank。

**为何存在判定**:**partial**(feature 未全量铺开 + 设计性硬卡,非代码缺陷;但厚数据利用率严重不足)。

**严重级**:**P1**(叙事质量直接受损:CFFC 77.3% facts、56% 人物被丢)。

**精确修复范围(5 处)**:
1. `understanding_builder.py:200/346`:`atomic_fact_limit` 200→客户实际(冻结 883 max),`person_limit` 60→137。
2. `workspace_data_center_adapter.py:1649-1650`:content_budget/module_budget 改基于 prompt 复杂度动态计算。
3. `narrative_collector.py:338-350`:各层 limit 参数化,calibrate 云端 token 预算(`:1615` max_chars=18000)。
4. `evidence_selector.py:167`:硬裁剪改基于语义覆盖率(coverage_targets_for_focus)动态选取。
5. `ai.py:_qwen_generate()` max_tokens 与 context 长度联动。

**次生**:narrative_generator 消费层缺可观测性(用户无法判断用了 883 facts 的 22.6% 还是 100%,P2)、CFFC 深读索引只覆盖 CFFC 其他客户回退 v2_instant 薄索引(P2)。

---

## ③ 需顾源源拍板的 2 个决策

**决策 A — 真库 7 个孤列是手工 ALTER 还是工具迁的?**
- **背景**:真库 `local_identities` 有 7 列(phone/phone_normalized + primary_role/account_status/is_department_lead/local_organization_id 等)是 `db.py` CREATE TABLE 没有、`_ensure_column` 链没补的,且打包版仍写 `phone_number`。这 7 列只可能是 git 外手工 ALTER 或某外部工具迁入。
- **互斥两路**:① 若是有意迁移 → **补列**:`db.py` 补 CREATE 定义 + 补 `_ensure_column`(给所有既有库 ALTER 补全),并改全部读写点列名;② 若是误操作/废弃实验残留(注意 `local_organization_id` 全仓 0 引用,疑 v2.1 实验弃用)→ **回退**:导出真库现存 1 行后删多余列,代码侧统一回 `phone_number`。
- **为何必须拍板**:两路互斥不能并存;补列方向的默认值还须避免覆盖既有 `primary_role='employee'`。请用户查 shell history / 确认是否手工 ALTER 过。

**决策 D — 会议链前端未接是"未完成"还是"刻意暂缓"?**
- **背景**:后端 `meeting_minute_processor` 全链(端点 `main.py:39354` + 治理表 + event_line + insight 写入)5/23 即在 main 且完整正确,但前端从无任何调用、无 UI 组件,治理表至今不存在。
- **影响**:① 若是"未完成"(本就要上) → 定 **P1**,立即投入前端工时接通(api.ts + UI 组件 + startup 显式建表);② 若是"刻意暂缓上线"(R2 能力先落后端、UI 待排期)→ 降 **P2**,本期只做 startup 显式 `ensure_governance_schema` 防竞态,前端排后续迭代。
- **为何必须拍板**:P1/P2 定级与是否立即投前端工时取决于产品意图,不可代为假设。

---

## ④ 建议修复优先级顺序

1. **簇 A(P1,会崩 + 阻断登录)** —— 但**先拍板决策 A** 再动手;`main.py:5328` 容错可立即先上(独立、低风险、止血单点 P0 崩溃)。
2. **簇 C(P1,99.7% 静默丢数据 + 8 天无自愈)** —— L1 扩扫描 + 上游 backfill(591)+ 上游吞异常 Option A 三者一起上;**L1 必须与 L2 attempt_count 同批**,否则"永久卡死"变"永久重试"。
3. **簇 B(P1,离线丢任务,6/4 已 unfixed)** —— catch 分流 + NetInfo,**前置依赖修 `mapSyncErrorToReasonCode` 分类断层**(404/410/429/5xx 补全)否则分流会误判。
4. **簇 E(P1,已有 4+25 孤儿)** —— 补 FK + 迁移清孤儿,纯 schema 修复风险低,可与上述并行。
5. **簇 D** —— **按决策 D 结果定**:判 P1 则随 A/B/C 同期接前端;判 P2 则本期只做 startup 显式建表防竞态。
6. **簇 F(P1 但 partial,质量类非崩/丢)** —— 放最后;先做 limit 参数化 + 可观测性(让用户看见消费率),再逐步动态预算。

**相关文件(绝对路径)**:
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/db.py`(:13/:75-97/:2580 _ensure_column/:2763-2781 atomic_facts/:2875-2896 recycle_bin/:3475/:3517)
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/main.py`(:5328 崩点/:30889/:30900/:30942/:3322-3331/:3720 startup/:39354 会议端点)
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/growth_sync.py`(:39-45/:149/:156-162/:178-181/:209-223)
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/handbook_sync.py`(:87)
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/growth_engine.py`(:3118-3124 吞异常)
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/badge_engine.py`(:1147-1153 吞异常)
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/local_memory.py`(:327-332 吞异常)
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/agent_governance.py`(:59-113/:140 惰性建表)
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/meeting_minute_processor.py`(:147-486/:300-327/:417-437)
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/understanding_builder.py`(:37/:200/:335/:346)
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/narrative_collector.py`(:338-351/:1615)
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/workspace_data_center_adapter.py`(:1649-1650)
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/mobile/lib/sync-engine.ts`(:45/:268/:467/:563-582/:565-569)
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/mobile/lib/local-db.ts`(:1576/:1944)
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/mobile/lib/sync-errors.ts`(:4-14)
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/mobile/lib/types.ts`(:47-57 SyncReasonCode)
- 真库:`/Users/guyuanyuan/Library/Application Support/YiyuThinkTankWorkbench2/app.db`