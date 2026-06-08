# 主仓库全量只读审计 · 遍1 (2026-06-08)

> 方法:14维度多agent检测 → 为何存在过滤(杀假问题) → 独立agent对抗式交叉验证 → P0优先合成。43 agent/2.7M tokens。只读不动代码。
> 这是**遍1**(广扫)。遍2深钻根因相关代码/表,遍3钉铁证。仓库正被并行AI churn,file:line 为当前快照。

## 计数: P0=0 P1=18 P2=16 P3=4 共38(去重后6个P1根因簇)

## 合成报告(P0优先,6簇)

Verified db.py:78 and the schema-version comment. The confirmed JSON is internally consistent. Producing the synthesized report.

---

# 全仓审计报告 — 遍1（P0优先合成）

**一句话总览**：本遍三关幸存确证发现共 **15 条**，去重后归并为 **6 个独立根因簇**；无真正 P0（无数据已删/不可逆破坏），但有 **2 个 P1 级"立即崩溃"根因**（本地身份表 schema 漂移、移动端离线任务永久卡死）和 **2 个 P1 级"数据静默丢失"根因**（云同步失败无重试、会议处理链整条未激活），均需在发版前处理。

**各级计数**：P0 = 0 ｜ P1 = 6（簇）｜ P2 = 0 ｜ P3 = 0

> 说明：原始 15 条确证项中 9 条指向同一 `local_identities` schema 漂移根因，已合并为簇 A；4 条会议链 issue 同根，合并为簇 D。

---

## P1

### A. `local_identities` schema 漂移 —— 手机/本地登录注册在生产库上即崩溃
- **严重级**：P1（最高实际影响，生产环境注册/登录全路径崩溃）
- **根因**：`db.py` 的 `CREATE TABLE local_identities` 定义与生产库结构分叉。代码侧用 `phone_number`，生产库实为 `phone` + `phone_normalized TEXT UNIQUE`；且生产库另有 `primary_role / account_status / local_organization_id / is_department_lead` 等 7 列，`CREATE TABLE` 完全缺失，并且**没有任何 `_ensure_column` 迁移**为既有库补列或为新库补全。`BACKEND_SCHEMA_VERSION=20260607` 注释声称已并入 `local_identities(20260605)`，但实现未跟进 → schema 回归。
- **铁证**：
  - `app/db.py:78`（`phone_number TEXT`，已亲验）/ `app/db.py:97`（索引建在 `phone_number` 上）
  - `app/db.py:75-95`（CREATE TABLE 仅 16 列，缺 7 列；已亲验范围）
  - `app/db.py:13`（schema 版本注释声称已合并，实未合并）
  - `app/main.py:30889`、`app/main.py:30942`（`SELECT ... WHERE phone_number = ?` → `no such column`）
  - `app/main.py:30899-30904`（INSERT 列含 `phone_number` → `table ... has no column named phone_number`）
  - `app/main.py:5328`（`row["phone_number"]` → sqlite3.Row 抛 `IndexError`，注册/登录响应构建崩溃）
  - PRAGMA：生产库 `.../YiyuThinkTankWorkbench2/app.db` 实为 `phone` + `phone_normalized UNIQUE`，25 列；新库 19 列
  - `grep '_ensure_column.*local_identities'` 为空（无迁移路径）
- **所属维度**：schema_migrations / auth_identity_org

---

### B. 移动端离线任务在 5 次重试后被永久卡死（不区分错误类型）
- **严重级**：P1（用户离线建任务联网后永久丢失，已在 6/4 记忆中标记 unfixed）
- **根因**：`sync-engine.ts:566` 的重试/`needs_attention` 决策只看重试次数、不看错误类型。网络错误与永久服务端错误被同等消耗 `MAX_OP_RETRIES=5`；一旦 `retryCount>=5` 即标 `needs_attention`，此后 `pushPendingOps` 在第 467 行 check 处永久跳过该 op，联网恢复也不再重试。`mapSyncErrorToReasonCode()`(565) 已提取错误类型却未用于决策。
- **铁证**：
  - `mobile/lib/sync-engine.ts:46`（`MAX_OP_RETRIES=5`）
  - `mobile/lib/sync-engine.ts:467-472`（`retryCount>=5` → `needs_attention` 并 continue）
  - `mobile/lib/sync-engine.ts:563-570`（catch 块丢弃 `reasonCode`）
  - `mobile/lib/sync-engine.ts:565`（`reasonCode` 提取但从不参与条件分支）
- **所属维度**：tasks_calendar_eventline

---

### C. 云同步失败记录永久卡死（无重试机制）
- **严重级**：P1（`failed` 成为数据库"暗物质"，需手工改库恢复）
- **根因**：`sync_status='failed'` 的记录永不被 worker 重扫。push 路径硬编码 `WHERE sync_status='pending'`，一旦 HTTP 错误/异常置 `failed` 即永不再试——无 `attempt_count`、无时间退避、无独立重试队列。worker 每 5 分钟只 push 一次，无重试逻辑。
- **铁证**：
  - `app/services/handbook_sync.py:87`（`SELECT WHERE sync_status='pending'`）
  - `app/services/growth_sync.py:149`（同上）
  - `app/main.py:3323-3328`（worker 每周期仅 push 一次，无重试）
- **所属维度**：cloud_sync_bridge

---

### D. `meeting_minute_processor` 整条数据链未被激活（端点从未被前端调用）
- **严重级**：P1（V2.5 R2-B 新功能框架完整但全链产出为 0，4 条 issue 同根）
- **根因**：`/meeting-minutes/process` 端点从未被前端触发 → `process_meeting_minute` 永不执行 → 其下游所有写入（治理表、event_line、strategic_thought_insight）全部为 0。代码本身完整正确，问题是**功能未激活**。附带 anti-pattern：治理表 schema 仅在 `log_agent_run_start` 首次调用时惰性创建，启动流程未显式调用 `ensure_governance_schema`，端点不被调用则表永不存在。
- **铁证**：
  - `app/services/agent_governance.py:59-113`（`ensure_governance_schema` 完整定义）/ `:140`（仅在 `log_agent_run_start` 内惰性触发）
  - `app/main.py:3720`（startup 块无 `ensure_governance_schema` 调用）
  - `app/services/meeting_minute_processor.py:417-437`（INSERT `event_line_activities` source_type='meeting_minute'，DB count = 0）
  - `app/services/meeting_minute_processor.py:300-327`（INSERT `strategic_thought_insights` insight_type='meeting_judgment'，DB count = 0）
  - DB：`.tables` 无 `agent_run_log`/`approval_queue`
- **所属维度**：meetings

---

### E. 成长 evidence 因 signal/evidence 推送顺序无屏障导致 FK 违约 → evidence 永久卡死
- **严重级**：P1（与簇 C 叠加构成确定性数据丢失路径）
- **根因**：push 函数虽按 signal→evidence 顺序顺序调用，但**无技术屏障**保证 signal 全部同步成功后才推 evidence。若 signal 推送返回 `failed`（如 HTTP 500），这些 signal 永不到云；evidence 携带指向不存在云端 signal 的 `signal_id` FK 被推送，云端 400 拒绝，evidence 标 `failed` 永久卡死（叠加簇 C 无重试）。`growth_sync.py:213` 注释承诺"signal 先 push"，代码无校验/屏障。
- **铁证**：
  - `app/services/growth_sync.py:212-223`（push_evidence 假设 signal_id 已在云，但不校验）
  - `app/main.py:3322`（注释承诺 signal 先行，代码不强制）
  - `app/services/growth_sync.py:156-162`（`extra_required_field` 仅本地 NOT NULL 校验，不验云端存在性）
- **所属维度**：cloud_sync_bridge

---

### F. `local_identities` 缺关键列定义且无迁移补列（onboarding/迁移层面）
- **严重级**：P1（与簇 A 同根的迁移面，单列出以便遍2系统修复迁移路径）
- **根因**：`db.py` CREATE TABLE 缺 `primary_role / account_status / is_department_lead / local_organization_id` 等列（生产库均有 NOT NULL + 默认值），且无 `_ensure_column` 为既有库补列。`db.py` 对 `v2_chunks/entities/documents` 等表有大量 `_ensure_column`，唯独 `local_identities` 零迁移。新装得到不完整 schema，既有库无法升级。
- **铁证**：
  - `app/db.py:75-95`（缺 7 列）
  - `app/db.py:2583-2608`（其他表大量 `_ensure_column` 对照）/ `:5126`（`_ensure_column` 方法定义）
  - `grep '_ensure_column.*local_identities'` 为空
  - `organization/schema.py:74-77`（`mirror_users` 才是 org 数据正典存储，部分查询经 `org_members_v` 视图——见 `bot_members.py:197-220`——故新库部分查询仍可走，掩盖了漂移）
- **所属维度**：schema_migrations / auth_identity_org

---

## 遍2 该深钻的根因相关代码/表

1. **`app/db.py:75-97` `local_identities` 整段 + 缺失的迁移层**：确认 `phone_number` 是否为代码侧统一笔误，还是生产库经历过 `phone/phone_normalized` 去重迁移而 `db.py` 未跟进；并补 `_ensure_column`（phone/phone_normalized/primary_role/account_status/local_organization_id/is_department_lead）。需对照 `app/main.py:30889/30900/30942/5328` 全部读写点统一列名。
2. **`mobile/lib/sync-engine.ts:46/467-472/563-570`**：在重试决策中引入 `reasonCode` 分支（transient vs permanent），并为 `needs_attention` op 增加 NetInfo 联网重连 requeue 触发。
3. **`sync_status` 状态机（`handbook_sync.py:87` + `growth_sync.py:149`）+ 同步表**：为 push 查询补 `failed` 重扫 / `attempt_count` / 退避队列；同步排查 `signals`/`evidence` 两表及其 `signal_id` FK 推送屏障（`growth_sync.py:212-223`）。
4. **`meeting_minute_processor.py:300-327 / 417-437` 全链 + `/meeting-minutes/process` 端点前端调用缺失**：确认端点是否需前端 UI 暴露；并在 `app/main.py:3720` startup 显式调用 `ensure_governance_schema(state.db)`,移除惰性建表 anti-pattern。涉及表：`agent_run_log`、`approval_queue`、`event_line_activities`、`strategic_thought_insights`。
5. **`organization/schema.py` `mirror_users` 与 `local_identities` 的职责边界**：确认 org 正典数据是否应全部走 `mirror_users`，从而判定 `local_identities` 是否本就该"稀疏"（仅本地认证），以收敛簇 A/F 的修复范围（补列 vs 设计性精简）。

相关文件绝对路径：
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/db.py`
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/main.py`
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/handbook_sync.py`
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/growth_sync.py`
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/agent_governance.py`
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/meeting_minute_processor.py`
- `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/mobile/lib/sync-engine.ts`

---
## 全部确证发现明细(未去重,供遍2核对)
### P1 (18)
- **phone_number vs phone column mismatch** [schema_migrations]
  - 根因: db.py:78 defines CREATE TABLE with phone_number TEXT, but production database has phone TEXT + phone_normalized TEXT UNIQUE. Code at main.py:30889,30942 queries with WHERE phone_number = ?, which fails on production DB with 'no such column: phone_number'. Additionally, main.py:5328 accesses row["phone_number"] which raises KeyError on production.
  - 证据: db.py:78 (CREATE TABLE local_identities with phone_number TEXT); main.py:30889,30942 (SELECT...WHERE phone_number = ?); main.py:5328 (row["phone_number"]); PRAGMA table_info on /Users/guyuanyuan/Library/Application Support/YiyuThinkTankWorkbench2/app.db shows columns: phone TEXT, phone_normalized TEXT UNIQUE (not phone_number); sqlite3 direct query 'SELECT id FROM local_identities WHERE phone_number = ?' returns 'no such column: phone_number'
- **Missing critical columns: primary_role, account_status, local_organization_id, is_department_lead** [schema_migrations]
  - 根因: db.py:75-95 CREATE TABLE local_identities omits columns that exist in production: primary_role (line 6 in prod), account_status (line 7 in prod), local_organization_id (line 10 in prod), is_department_lead (line 18 in prod). These are NOT NULL columns with defaults in production but completely absent from CREATE TABLE statement. No _ensure_column calls add these columns for fresh databases. The org_members_v view in bot_members.py:197-220 selects primary_role and account_status from mirror_users, not local_identities, so fresh DB queries still work via the view. However, direct queries to local_identities for these columns will fail.
  - 证据: db.py:75-95 (CREATE TABLE - missing primary_role, account_status, local_organization_id, is_department_lead); PRAGMA table_info(local_identities) on production DB shows these columns with NOT NULL + DEFAULT values; No _ensure_column calls in db.py:2500-4200 range for local_identities columns; organization/schema.py:74-77 defines these columns in mirror_users (the canonical storage for org data)
- **Schema version mismatch: fresh vs production database structure** [schema_migrations]
  - 根因: db.py:13 BACKEND_SCHEMA_VERSION = 20260607 claims to include 'local_identities(20260605)' merge, but _init_schema at lines 75-97 does not create phone_normalized, primary_role, account_status, or local_organization_id columns that exist in production. Fresh databases created with current code diverge from production: fresh has phone_number, missing phone/phone_normalized/primary_role/account_status/local_organization_id/is_department_lead. This is a schema migration regression, not a forward compatible enhancement.
  - 证据: db.py:13 (BACKEND_SCHEMA_VERSION with comment about local_identities merge); db.py:75-97 (CREATE TABLE missing 7 production columns); PRAGMA table_info comparison (production has 25 columns including phone/phone_normalized/primary_role/account_status/local_organization_id/is_department_lead; fresh DB has 19 columns, missing those 7, and has phone_number instead of phone). No ALTER TABLE or _ensure_column calls to bridge this gap.
- **Missing ensure_column migration for local_identities critical columns** [schema_migrations]
  - 根因: db.py implements extensive _ensure_column calls (lines 2583-2608 and beyond) for other tables to add columns to existing databases. However, local_identities has ZERO _ensure_column calls. Grep for '_ensure_column.*local_identities' returns no results. Existing production databases cannot be upgraded to have primary_role, account_status, etc. because there is no migration code. Fresh databases get the incomplete schema from lines 75-97, perpetuating the divergence.
  - 证据: db.py:2583-2608 show extensive _ensure_column calls for v2_chunks, entities, documents, etc.; grep -n '_ensure_column.*local_identities' returns empty; db.py:5126 defines _ensure_column method; no calls to ensure phone/phone_normalized/primary_role/account_status/local_organization_id/is_department_lead for local_identities table
- **Failed sync records permanently stuck (no retry mechanism)** [cloud_sync_bridge]
  - 根因: sync_status='failed' records are never re-scanned by worker. Both push_pending_entries_to_cloud (handbook_sync.py:87) and _push_table_to_cloud (growth_sync.py:149) use hardcoded 'WHERE sync_status = 'pending'' query. Once HTTP error or exception sets status='failed', the record is never attempted again. No attempt_count field, no time-based retry, no separate retry queue.
  - 证据: backend/app/services/handbook_sync.py:87 (SELECT WHERE sync_status='pending') / backend/app/services/growth_sync.py:149 (SELECT WHERE sync_status='pending') / backend/app/main.py:3323-3328 (worker only calls push once per 5min cycle, no retry logic)
- **Growth evidence FK violation risk due to unordered signal/evidence push** [cloud_sync_bridge]
  - 根因: While push functions are called sequentially (signal first, evidence second at main.py:3323-3328), there is NO TECHNICAL BARRIER ensuring signals are fully synced before evidence is pushed. If push_gs returns with 'failed' records (e.g., signal HTTP 500), those signals never reach cloud. Evidence push then executes with pending evidence records containing signal_id FK references to non-existent cloud signals. Cloud rejects with 400 FK error, evidence marked 'failed', permanently stuck (no retry). The comment at growth_sync.py:213 says 'signal先push' but code has no validation/barrier.
  - 证据: backend/app/services/growth_sync.py:212-223 (push_evidence assumes signal_id exists in cloud but doesn't verify) / backend/app/main.py:3322 (comment promises signal first, but code doesn't enforce) / backend/app/services/growth_sync.py:156-162 (extra_required_field check only verifies NOT NULL locally, not cloud existence)
- **[P1] local_identities schema mismatch: phone_number vs phone + phone_normalized** [auth_identity_org]
  - 根因: The CREATE TABLE definition in db.py declares column 'phone_number' (line 78), but the actual production database has two separate columns: 'phone' (col 2) and 'phone_normalized' (col 3). Code queries against the non-existent 'phone_number' column, causing runtime errors. PRAGMA table_info confirms actual schema. Fresh databases created from db.py will have 'phone_number' (wrong), but existing production DBs have 'phone'/'phone_normalized' (correct).
  - 证据: db.py:78 declares 'phone_number TEXT'; main.py:30889,30942 queries 'WHERE phone_number = ?'; main.py:5328 reads 'row["phone_number"]'; actual DB PRAGMA shows columns 2='phone', 3='phone_normalized'; SQL query test confirms 'no such column: phone_number' error
- **[P1] local_identities INSERT uses wrong column name phone_number** [auth_identity_org]
  - 根因: main.py:30900 INSERT statement includes 'phone_number' in column list, which does not exist in the actual database. When executed, SQLite throws 'table local_identities has no column named phone_number' error immediately. The code cannot create new local accounts.
  - 证据: main.py:30899-30904 INSERT explicitly names columns including 'phone_number'; SQLite test: 'INSERT...phone_number failed: table local_identities has no column named phone_number'; actual DB has 'phone' and 'phone_normalized' not 'phone_number'
- **[P1] Phone duplicate check queries wrong column name** [auth_identity_org]
  - 根因: main.py:30889 queries 'WHERE phone_number = ?' but actual DB column is 'phone_normalized'. The duplicate phone detection completely fails—the query throws 'no such column' error instead of checking for duplicates. Two registrations with same phone could both succeed (if the code path were fixed to work).
  - 证据: main.py:30889 'SELECT id FROM local_identities WHERE phone_number = ?' vs actual DB schema with phone_normalized UNIQUE constraint (PRAGMA index_info(sqlite_autoindex_local_identities_3) shows UNIQUE on col 3 'phone_normalized')
- **[P1] Reading phone from database row silently fails** [auth_identity_org]
  - 根因: main.py:5328 accesses row['phone_number'] which does not exist in actual DB. SQLite Row object raises IndexError when accessing missing key (not KeyError as claimed). This causes registration/login response to crash when trying to populate phone field in SessionUserRecord.
  - 证据: main.py:5328 'phone=str(row["phone_number"] or "") or None'; Test shows: 'Traceback: IndexError: No item with that key' when accessing row['phone_number']; actual DB column is 'phone' (col 2)
- **[P1] local_identities missing column definitions: primary_role, account_status, is_department_lead, local_organization_id** [auth_identity_org]
  - 根因: db.py CREATE TABLE statement (lines 75-95) defines only 16 columns for local_identities, but actual production database has 25 columns including 'primary_role', 'account_status', 'is_department_lead', and 'local_organization_id' with NOT NULL defaults. These migration columns were added to the actual DB but the schema definition in db.py was never updated. Fresh databases created from db.py will be incomplete.
  - 证据: db.py:75-95 lists 16 columns; PRAGMA table_info shows 25 total columns including col 6='primary_role' (default 'admin'), col 7='account_status' (default 'approved'), col 18='is_department_lead' (default 0), col 10='local_organization_id' (NOT NULL, no default visible); db.py does not include these in CREATE TABLE
- **Mobile offline sync permanently blocks tasks after 5 retries regardless of error type** [tasks_calendar_eventline]
  - 根因: sync-engine.ts line 566 makes retry/needs_attention decision based only on retry count, not error type. Network errors are treated identically to permanent server errors - both consume MAX_OP_RETRIES=5. Once retryCount >= 5, any error marks op as needs_attention (line 468), and future pushPendingOps iterations skip it entirely (line 467 check), so the op never retries again even when network is restored. The mapSyncErrorToReasonCode() at line 565 extracts the error type but it's ignored for retry logic decision.
  - 证据: mobile/lib/sync-engine.ts:46 (MAX_OP_RETRIES=5); mobile/lib/sync-engine.ts:467-472 (retryCount>=5 check marks needs_attention and continues); mobile/lib/sync-engine.ts:563-570 (catch block ignores reasonCode when determining nextStatus); mobile/lib/sync-engine.ts:565 (reasonCode extracted but never used for conditional logic)
- **Issue #2: agent_run_log和approval_queue表不存在,ensure_governance_schema从未被调用** [meetings]
  - 根因: 设计缺陷+启动流程漏洞。ensure_governance_schema(db)在agent_governance.py:59-113定义完整,但启动流程未显式调用。虽log_agent_run_start(line 140)内部会自动调用ensure_governance_schema(db),BUT关键缺口:meeting-minutes/process端点从未被前端触发→log_agent_run_start永不执行→表永不创建。表创建延迟(on first call)在normal use case下可接受,但当端点本身残留未被调用时,表创建机制变成死代码。启动流程应显式调用ensure_governance_schema确保表一定存在。
  - 证据: database: sqlite3 .tables无agent_run_log/approval_queue | backend/app/services/agent_governance.py:59-113(ensure_governance_schema完整定义含CREATE TABLE) | backend/app/services/agent_governance.py:140(log_agent_run_start第1行:ensure_governance_schema(db)) | backend/app/main.py:3720(startup block无ensure_governance_schema调用) | git grep ensure_governance_schema无startup路径
- **Issue #3: event_line_activities零来自meeting_minute_processor的时间线事件** [meetings]
  - 根因: 同根issue#2:meeting-minutes/process端点未被前端调用。backend/app/services/meeting_minute_processor.py:417-437代码完整(INSERT INTO event_line_activities WITH source_type='meeting_minute'),但第417行执行权在try-except内,且这整个Phase 9b(line 390-440)只有process_meeting_minute被调用才能reach。由于端点从未被触发,新增的event_line_activities数始终为0(除非derive_all派生,但文档明确说meeting本身她直写ela,line 392注释)。
  - 证据: database: SELECT COUNT(*) FROM event_line_activities WHERE source_type='meeting_minute' → 0 | backend/app/services/meeting_minute_processor.py:417-437(INSERT ela代码完整) | backend/app/main.py:3570+(端点完整但前端无调用) | 同issue#2:端点未被激活
- **Issue #4: strategic_thought_insights的meeting_judgment类型从未被写入** [meetings]
  - 根因: 同根issue#2/#3:meeting_minute_processor整条链未被激活。backend/app/services/meeting_minute_processor.py:300-327(Phase 6)代码完整(INSERT strategic_thought_insights WITH insight_type='meeting_judgment'),但执行require process_meeting_minute被调用,即require /meeting-minutes/process端点被前端触发,但未发生。SELECT COUNT WHERE insight_type='meeting_judgment' → 0验证此链路未激活。
  - 证据: database: SELECT COUNT(*) FROM strategic_thought_insights WHERE insight_type='meeting_judgment' → 0 | backend/app/services/meeting_minute_processor.py:300-327(INSERT insight代码完整) | 同issue#2:端点未被调用导致Phase6未execute
- **离线建任务丢失 - 网络错误耗尽MAX_OP_RETRIES后无自动恢复触发** [mobile]
  - 根因: sync-engine采用固定重试上限(MAX_OP_RETRIES=5),网络超时(DEFAULT_REQUEST_TIMEOUT_MS=45s)导致op标记为'needs_attention',此后仅依赖定时器(前台2分钟/后台15分钟)或用户手动操作恢复,无网络状态变化触发机制
  - 证据: /Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/mobile/lib/sync-engine.ts:46(MAX_OP_RETRIES=5),api.ts:106(DEFAULT_REQUEST_TIMEOUT_MS=45s),sync-engine.ts:467-472(前台2分钟检查),sync-engine.ts:697(后台15分钟),sync-engine.ts:563-567(网络失败流程),local-db.ts:1925(retry_count自增),system-health.ts:270(requeueOp手动触发)
- **同步引擎不监听网络状态变化 - 无NetInfo集成** [mobile]
  - 根因: sync-engine.ts仅通过AppState.addEventListener监听应用前后台状态,未集成@react-native-community/netinfo,无法感知网络连接类型变化(WiFi↔蜂窝数据)或完全离线状态
  - 证据: /Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/mobile/lib/sync-engine.ts:24(仅import AppState),sync-engine.ts:269(仅AppState监听),package.json:20-52(dependencies无NetInfo),sync-engine.ts:660-670(handleAppStateChange仅处理active/background)
- **咨询云镜像表基本为空 - 桌面publish端点零调用,生产侧断路** [mobile]
  - 根因: 云端POST /api/v1/mobile/knowledge-mirror/publish端点完整实现(_upsert_cloud_mirror_item逻辑成熟),但桌面端从未调用此端点,手机端读取GET /api/v1/consultation/knowledge-requests时无数据来源,镜像表完全空转
  - 证据: /Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/cloud_backend/app/main.py:14900(publish endpoint存在),api.ts:534-539(fetchConsultationKnowledgeRequests仅读GET,无publish调用),grep mobile/lib -rn 'knowledge-mirror/publish'(返回空,无移动端发布逻辑),cloud_backend/app/main.py:14915-14930(_upsert_cloud_mirror_item核心逻辑完整但无生产调用)

### P2 (16)
- **Path optimization high failure rate + disabled** [data_center_supply]
  - 根因: generate_local_model_json method was never implemented in AiService (全仓无定义), causing 100% historical failure of path_optimization tasks (57/59 errors = AttributeError). Root emergency response: disabled autoEnqueuePathOptimization (2026-05-28). Root technical fix: rewrote _process_path_optimization_task to use real _qwen_generate method (2026-05-30, commit b4713d4), added _DOCUMENT_PATH_SCHEMA, added test coverage. Current state: fix is complete & tested, but feature remains administratively disabled (autoEnqueuePathOptimization=False), so no new tasks queued after 2026-05-30 for production validation.
  - 证据: /Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/local_model_optimizer.py:47-49 (root cause comment + disabling setting), line 49 (autoEnqueuePathOptimization=False), line 777-854 (_process_path_optimization_task fixed code), database query result (59 failed vs 29 completed pre-fix), /Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/backend/tests/test_path_optimization_processor.py (fix validation tests), git commit b4713d4 (2026-05-30 fix implementation), git commit 828a5eb (2026-05-28 emergency disable), database confirmed 0 attempts on 9 queued tasks created post-fix
- **Prompt context budgets hardcoded with fixed token allocations** [data_center_consume]
  - 根因: In build_chat_answer_context (workspace answer generation), evidence_char_budget=28000 is hardcoded at line 22028 with no parameters to dynamically adjust based on context headroom or field complexity. The curated evidence selection caps at 24 items (line 22026) regardless of how many high-signal evidence items are available. Additionally, evidence_limit and excerpt_limit are fixed (lines 22026-22027), not responsive to Qwen 32K context window availability.
  - 证据: /backend/app/main.py:22026-22028 hardcoded evidence_limit=24, excerpt_limit=1400, evidence_char_budget=28000 with no dynamic adjustment mechanism; lines 22043-22056 use these fixed allocations to filter evidence without considering available context headroom or evidence richness per field
- **No observability into which data source contributed to final answer (v1 vs v2 distinction missing)** [data_center_consume]
  - 根因: EvidenceItem model (models.py:1130-1159) includes sourceType='knowledge_chunk'|'knowledge_document' and retrievalStage='master_index'|'surrogate'|'raw_chunk'|'state_pool', but lacks sourceDataCenter field to distinguish legacy knowledge_documents (v1 index) from v2_documents index. When evidence is retrieved via retrieve_knowledge_bundle, it queries knowledge_master_index joined to knowledge_documents without tagging which underlying collection (v1 vs v2) the master entry originated from. retrieval_summary (main.py:14797-14805) logs queryPrompt/clientDnaHintTerms/answerIntent/expansionTerms but not source_stage distinction.
  - 证据: /backend/app/models.py:1130-1159 EvidenceItem class has sourceType, retrievalStage, isFallback, documentId, path fields but NO sourceDataCenter field; /backend/app/services/knowledge_base.py:3837-3846 retrieve_knowledge_bundle queries knowledge_master_index JOIN knowledge_surrogates without joining to v2_documents or tracking collection origin; /backend/app/main.py:14797-14805 retrieval_summary dict includes sourcePrompt, clientDnaHintTerms, answerIntent, retrievalExpansionTerms but not data_center/collection_origin metadata
- **Handbook entries stuck in sync_status='local'** [cloud_sync_bridge]
  - 根因: mark_entry_pending() exception at db.conn.commit() silently caught and logged without retry. Most likely cause: Database object corruption, connection closed, or concurrent access locking. When exception occurs, sync_status remains 'local' since UPDATE+COMMIT is atomic and fails together.
  - 证据: backend/app/main.py:56250-56253 (exception caught but merely logged) / backend/app/services/handbook_sync.py:69-75 (mark_entry_pending calls db.conn.commit() which can fail)
- **Exp wall quotes and handbook entries dual-track design creates redundancy** [cloud_sync_bridge]
  - 根因: Both exp_wall_service.py (quotes sync) and handbook_sync.py (entries sync) are fully active and called in parallel (main.py:3305-3321). They have independent sync state machines, independent push/pull logic, and separate 'failed' record accumulation. Per the comment in handbook_sync.py:8, handbook_entries is the 'real' frontend data source as of 5/27, but exp_wall_quotes sync still runs. This creates: (1) duplicate failed record backlog (2) maintenance burden (3) potential data consistency issues if both are written to.
  - 证据: backend/app/main.py:3305-3321 (both push_pending_quotes_to_cloud and push_pending_entries_to_cloud called) / backend/app/services/handbook_sync.py:8 (comment: 'handbook_entries 才是前端真数据源') / backend/app/services/exp_wall_service.py:570-622 (complete independent sync implementation)
- **[P2] Registration INSERT omits required columns with NOT NULL defaults** [auth_identity_org]
  - 根因: main.py:30899-30904 INSERT statement specifies only 13 columns out of 25 in actual DB. Columns like 'primary_role', 'account_status', 'is_department_lead' have NOT NULL defaults in the actual schema, so the INSERT would succeed (defaults applied), but the db.py schema definition doesn't include these columns at all. This creates a mismatch between code expectations and actual database structure.
  - 证据: main.py:30899-30904 INSERT lists 13 columns: id, email, phone_number, full_name, password_hash, local_organization_name, organization_mode, pending_invite_code, pending_department_id, job_title, manager_name, current_focus, membership_status; actual DB has 25 columns with defaults for missing ones
- **[P2] Schema divergence: local_identities vs cloud_backend employee_accounts** [auth_identity_org]
  - 根因: Local authentication uses 'pending_department_id' without FK constraint, while cloud backend uses 'department_id' with FK to org_departments. Local uses 'organization_mode' branching logic instead of proper org FK. Actual DB has 'local_organization_id' column (col 10) that is never used in code. This indicates incomplete consolidation of two parallel auth schemas.
  - 证据: db.py:83-84 uses pending_department_id (no FK); PRAGMA shows col 10 'local_organization_id TEXT NOT NULL' with no default; code uses organization_mode string, never references local_organization_id; cloud_backend uses proper department_id FK
- **Task data center ingest missing cross-day time range handling** [tasks_calendar_eventline]
  - 根因: record_task_writeback() function only extracts and passes 'due_date' field to memory_facts, ignoring scheduled_start_at and scheduled_end_at. The memory_facts schema has valid_from/valid_to columns and they are actively used in queries to filter time-bound facts, but record_task_writeback never populates them. This means cross-day tasks are recorded in memory_facts with incomplete temporal information.
  - 证据: backend/app/services/data_center_ingest.py:1452 (record_task_writeback call passes only due_date); backend/app/services/memory_foundation.py:1689-1701 (upsert_memory_fact called without valid_from/valid_to parameters); backend/app/db.py:1470-1471 (memory_facts schema has valid_from/valid_to); backend/app/main.py:8269 (valid_to used in filtering queries); backend/app/services/memory_foundation.py:667-680 (upsert_memory_fact signature supports valid_from/valid_to but record_task_writeback doesn't pass them)
- **14 orphaned growth_signal_events reference non-existent handbook_entry records** [growth_expwall]
  - 根因: No FOREIGN KEY constraint on growth_signal_events.source_id allows handbook_entry deletions to leave orphaned signals. The signals remain because the system embeds context_json at creation time rather than relying on future handbook_entries lookups.
  - 证据: backend/app/db.py:2289-2302 (no FK on source_id); database query confirms 14 growth_signal_events with source_id NOT IN (SELECT id FROM handbook_entries); 21 growth_evidence_records linked to orphaned signals via growth_signal_events.id
- **Lack of worker pool size limits could cascade thread creation** [perf_power_workers]
  - 根因: The codebase spawns daemon threads unconditionally from 25 different locations in main.py with no global ThreadPoolExecutor, semaphore, or thread count limit. While individual operations have their own throttling (in_flight flags, TTL gates), the Thread objects themselves accumulate in memory. Under high user activity (many task creates, client syncs, attachment uploads happening simultaneously), thread count could grow significantly. Python's GIL somewhat mitigates this, but file descriptor exhaustion is possible.
  - 证据: backend/app/main.py shows 25 Thread(...).start() calls with no pooling or semaphore; grep shows calls at lines 3832, 3865, 3881, 8389, 24313, 24356, 26981, 27142, 30209, 30726-30727, 31211-31212, 31236-31237, 31757, 37680, 37753, 48234, 51476, 51484, 53206, 53539, 53603, 54296; no ThreadPoolExecutor usage found; line 57 imports only Event and Lock, no pool tools
- **rawListTasks recreated every render without memoization** [frontend_renderer]
  - 根因: rawListTasks is computed inline on every render without useMemo wrapper at line 12020, causing its object reference to change even when underlying data hasn't changed. This feeds into listTasks dependency array (line 12028-12048), which cascades to visibleListTasks (12049-12052), executionTaskGroups (12054-12057), and other downstream useMemo computations. Commit 8ed37a7 (5/29) explicitly fixed activeProjectStructure and taskProjectFlowOptions memoization but did NOT address rawListTasks.
  - 证据: src/renderer/App.tsx:12020-12027 (rawListTasks computed inline, no useMemo); src/renderer/App.tsx:12028 (listTasks depends on rawListTasks); git commit 8ed37a7 shows only activeProjectStructure and taskProjectFlowOptions were memoized, rawListTasks not touched
- **sync_freeze_core设计不完整 - 网络不可用未被视为硬冻结** [mobile]
  - 根因: SyncFreezeState类型仅定义5个硬冻结状态(integrity/scope_mismatch/migration_failure/auth),无'blocked_by_network'状态;network_unavailable错误仅映射为普通reason_code而非冻结触发器;sync-engine仅在401时调用setSyncFreezeState('blocked_by_auth'),完全网络中断时performSync仍会每2分钟徒劳执行
  - 证据: /Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/mobile/lib/types.ts:560-566(SyncFreezeState缺network状态),sync-freeze-core.ts:3-4(isSyncFreezeBlocked仅识别5种硬冻结,不含network),sync-errors.ts:13(network_unavailable返回普通reason_code),sync-engine.ts:573-574(仅401触发冻结)
- **pending_ops状态机缺乏自动恢复路径 - markOpFailed后无指数退避** [mobile]
  - 根因: markOpFailed仅自增retry_count并设status为'needs_attention',无指数退避(exponential backoff)机制;恢复唯一路径是requeueOp()硬重置retry_count=0,需UI主动触发;pushPendingOps(:467)直接判retry_count>=MAX_RETRIES跳过,无gradual degradation策略
  - 证据: /Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/mobile/lib/local-db.ts:1916-1933(markOpFailed无backoff逻辑),local-db.ts:1935-1950(requeueOp需手动清零retry_count),sync-engine.ts:467-472(pushPendingOps直接判skip,无增量退避),system-health.ts:268-275(requeueOp由UI profile.tsx:810调用,发现路径不明显)
- **P1: Schema version mismatch between electron main and backend runtime** [electron_main_packaging]
  - 根因: REQUIRED_BACKEND_SCHEMA_VERSION (20260420) in main.ts:39 is a stale constant set at initial release and never updated as backend schema evolved. Backend currently runs 20260607, real database is 20260604. The check at main.ts:1398 implements one-way validation (only warns if DB schema < minimum required) but does NOT detect forward-incompatible changes (when DB schema > what the bundled backend code expects).
  - 证据: src/main/main.ts:39 REQUIRED_BACKEND_SCHEMA_VERSION=20260420 (never updated since initial commit 054373f); backend/app/db.py:13 BACKEND_SCHEMA_VERSION=20260607 (incremented from 20260526→20260527→...→20260607 across 11+ commits); real db PRAGMA user_version=20260604 (from 2026-06-04); check logic at main.ts:1398-1399 only validates schemaVersion < REQUIRED_BACKEND_SCHEMA_VERSION (downgrade detection only); warning logged at line 2625 but does NOT block app (promise still resolves at line 2627)
- **narrative_synthesis_runner module does not exist** [dead_code_orphans]
  - 根因: TASK_TYPE_NARRATIVE_SYNTHESIS is registered in TASK_TYPES set and has dispatch code that attempts to import narrative_synthesis_runner, but the module was never implemented. This is a planned Phase 4 feature (N pages → 1 document) that was shelved. The dispatcher has a type: ignore[import-not-found] comment indicating awareness of the missing module.
  - 证据: backend/app/services/local_model_optimizer.py:27 (TASK_TYPE_NARRATIVE_SYNTHESIS defined), 33 (in TASK_TYPES set), 996-998 (dispatch with type: ignore[import-not-found]). Directory listing of backend/app/services/task_runners/ shows no narrative_synthesis_runner.py (verified 2026-06-08). Database query shows 0 narrative_synthesis tasks ever created (database contains 111 document_card, 97 path_optimization, 10 visual_ocr but 0 narrative_synthesis).
- **atomic_facts.source_v2_document_id FK Missing - 4 Orphan Records** [cross_table_integrity]
  - 根因: Schema omission: atomic_facts table defines source_v2_document_id TEXT column (db.py:2773) but lacks FOREIGN KEY constraint to v2_documents(id). relationship_triples table (db.py:2750) correctly implements this FK, proving the pattern was known. The omission appears to be accidental, originating in commit 49ebe82 that created atomic_facts without the FK, while later commits only added it to relationship_triples.
  - 证据: db.py:2763-2781 (atomic_facts CREATE TABLE — column defined at line 2773, FK constraints at 2778-2780 only cover client_id/subject_entity_id/source_v2_chunk_id, no FOREIGN KEY for source_v2_document_id); db.py:2750 (relationship_triples correctly has 'FOREIGN KEY(source_v2_document_id) REFERENCES v2_documents(id) ON DELETE SET NULL'); sqlite3 PRAGMA foreign_key_list(atomic_facts) output confirms zero FK for source_v2_document_id; database audit yields 4 orphans (IDs: acc6f3bb-d672-495f-9c79-6c0c99d68839, 39120e4b-827a-4c46-b2a8-af21d148929f, 274b345d-ed48-4f11-aeb9-edd10f7105e6, ff67d068-2584-4aba-8a0c-51437a35c526) with deleted v2_documents (v2doc_sysdoc_90000a17cab636da94a2, v2doc_sysdoc_65ff5fe1ca9c6b33e1c5, v2doc_doc_8868a506ea)

### P3 (4)
- **[P3] local_organization_id column never used in code** [auth_identity_org]
  - 根因: PRAGMA shows col 10 'local_organization_id TEXT NOT NULL DEFAULT '''' in actual DB, but zero grep results for 'local_organization_id' in main.py or other backend files. All organization logic uses 'organization_mode' string and 'local_organization_name'. Column was likely added in v2.1 experiment phase and abandoned but never removed from schema.
  - 证据: Actual DB PRAGMA: col 10 local_organization_id TEXT NOT NULL; grep -n 'local_organization_id' /backend/app/main.py yields no results; all org logic uses organization_mode and local_organization_name
- **TasksView component size and useEffect count claims are significantly misstated** [frontend_renderer]
  - 根因: Incorrect measurements in the original claim: (1) TasksView spans lines 10998-20158 (~9,160 lines), NOT 19,800+ lines as claimed; (2) TasksView contains 44 useEffect statements, NOT 159 as claimed. The 159 figure is the TOTAL for the entire App.tsx file, not just TasksView. However, the underlying concern is valid: TasksView at ~9,160 lines DOES violate the coding-style.md rule of max 800 lines per file.
  - 证据: src/renderer/App.tsx:10998 (TasksView start); src/renderer/App.tsx:20158 (TasksView end, closing brace of useMemo); sed-based count shows 44 useEffect in lines 10998-20158; entire file has 159 total useEffect calls
- **Console logging statements in production code** [frontend_renderer]
  - 根因: App.tsx contains 42 console.warn/console.error/console.info statements scattered throughout (lines 8167, 8310, 8374, 8538, 9025, 9034, 9110, 9114, 9181, 9185, 9207, 9214, 9220, 9391, 9522, 9651, 9654, 9800, 10119, 10131, 10336, 11281, 11382, 11510, 11578, 12967, 13067, 13091, 13123, 13580, 13602, 13605, 13634, 20392, 21021, 21025, 27837, 27846, 28023, 28032, and others). All statements have debug-scoped prefixes like '[bootstrap]', '[pollRun]', '[task-modal]', etc.
  - 证据: grep shows 42 console.* statements in src/renderer/App.tsx; typescript/coding-style.md rule states 'No console.log statements in production code'; all located statements have [bracketed] debug prefixes
- **EventLineReportPanel.tsx.bak backup file present** [dead_code_orphans]
  - 根因: Backup file EventLineReportPanel.tsx.bak (151KB, 3137 lines) from component refactoring dated 2026-05-18 14:55:22 is committed to the repository but not imported or referenced anywhere in the codebase. The current EventLineReportPanel.tsx (149KB, 2026-05-22 12:58:37) is actively imported in App.tsx and used in production.
  - 证据: src/renderer/components/tasks/EventLineReportPanel.tsx.bak exists with 3137 lines (verified via wc). App.tsx imports EventLineReportPanel (not .bak) at src/renderer/App.tsx line containing 'import EventLineReportPanel from'. grep -r 'EventLineReportPanel.tsx.bak' returns zero results across entire codebase. File dates show backup is 4 days older than current version (2026-05-18 vs 2026-05-22).
