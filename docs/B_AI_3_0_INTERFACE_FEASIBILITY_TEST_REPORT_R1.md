# B AI · 3.0 接口化可行性测试报告 (第一轮 · §A+§B)

> **触发**: 顾源源 2026-05-23 钦定《3.0 接口化可行性测试方案》§A 静态扫描 + §B Tool Registry
> **数据基础**: 主仓库 backend (`~/openclaw/workspace/yiyu-thinktank-workbench/backend/`) 实测 grep + sqlite3 + V2.4 P0-1/2/3/4 commits
> **范围**: 本报告只覆盖 §A (静态扫描) + §B (Tool Registry 草案), §C (Headless) + §D (前后对比) 等顾源源批准再跑
> **执行人**: AI B
> **日期**: 2026-05-23

---

## TL;DR

**3.0 接口化可行性等级判定: 🟢 B 级 (部分模块可行, 需先补 AI agent context 绑定层)**

| 项 | 数字 | 状态 |
|---|---|---|
| 主仓库 backend services | **175 个** | ✅ 服务化基础就位 |
| 主仓库 main.py endpoint | **579 个** (232 GET + 282 POST + 65 其它) | ✅ HTTP 接口丰富 |
| 8 板块有归属 endpoint | **388 个** (66% 覆盖) | ✅ 板块化清晰 |
| 服务无 HTTP endpoint 暴露 (deriver/detector 类) | **A V2.4 P0-1/2 deriver/detector** | ⚠️ service 层有, endpoint 没暴露 |
| 带 X-Actor-Type AI agent context 的 endpoint | **仅 2/579 = 0.3%** | 🔴 AI agent 绑定层缺 |
| Idempotency-Key 接通 endpoint | **3/579** (event-lines/clients/tasks) | 🔴 retry 容错基础设施未铺开 |
| 写入操作需要 client_id 上下文 | ✅ 大部分有 | ✅ 安全边界基础 |
| 危险动作有 approval 队列 | 🔴 没找到 ApprovalQueue 设计 | 🔴 硬门槛 4 未通 |
| AgentRun Log | ✅ ai_episode_log 312 行已开始 | ⚠️ 基础就位, 但不绑 endpoint |

**核心判断**:
- 接口**有**, 数量足 (579 endpoint)
- **绑定层缺** (X-Actor-Type / Idempotency-Key 覆盖率 < 1%)
- A V2.4 P0-1/2 的语义派生器/冲突检测器是 **service-level**, 没 HTTP 暴露 → AI 直接调不到

→ **B 级判定**: 模块基本能脱离 UI 调, 但需要先补 "AgentCommandGateway 统一加 actor/idempotency/approval 三层壳", 之后才能做 3.0.

---

## §A · 8 板块静态扫描盘点

### A.1 主仓库 backend 真实形态

```
backend/app/services/              175 个 *.py
backend/app/main.py                54885 行 (closure endpoint 全在里面)
backend/app/db.py                  5154 行 (217 表 schema)

main.py endpoint 总数:             579
  GET:    232
  POST:   282
  PUT/DELETE/PATCH: 65
```

### A.2 8 板块 endpoint × service 盘点 (6 维度)

#### 01 · 任务与日程

| 维度 | 状态 |
|---|---|
| 已有 backend services | 10 个 (`action_suggestion_service` / `agent_worklogs` / `meeting_action_extractor` / `review_analysis` / `review_narrative` / `review_rollup` / `review_simulation` / `task_context_brief_engine` / `task_runners` / `weekly_review_material_pack`) |
| main.py endpoint | **56 个** |
| 关键样本 | `POST /api/v1/tasks` (TaskPayload), `POST /api/v1/tasks/ai-parse`, `POST /api/v1/event-lines` (B F2.8) |
| 能脱离 UI 调? | ✅ POST 接 pydantic payload, 不依赖 session cookie |
| 写数据? | ✅ tasks/event_lines/commitments/weekly_reviews |
| 需人工确认? | ⚠️ 当前没 approval, AI 直接 POST 会立刻产任务 |
| 审计日志? | ⚠️ event_log 312 行 (跨表, 不完整覆盖 task 写入) |
| **当前缺口** | task.create_draft (草稿态) endpoint 没有, 当前 POST /tasks 直接是正式任务 |

#### 02 · 客户工作台

| 维度 | 状态 |
|---|---|
| 已有 backend services | 14 个 workspace_* + answer_layer/chat_intent/client_profile/client_strategic_pulse |
| main.py endpoint | **145 个** ★ 最多 |
| 关键样本 | `POST /api/v1/clients/{id}/chat` (工作台对话), `GET /api/v1/clients/{id}/fact-bundle` (L2 共识) |
| 能脱离 UI 调? | ⚠️ **部分** — workspace_chat_multipass 依赖 `get_cached_session_user()`, AI agent 无 session |
| 写数据? | ✅ chat_messages 1125 / atomic_facts (部分) |
| 需人工确认? | ❌ 当前没 |
| 审计日志? | ⚠️ ai_episode_log 312 (跟 narrative_generator 关联, 不绑 workspace) |
| **当前缺口** | session_user 依赖 → 必须改成 `X-Actor-Type: ai_agent + X-Actor-Id` 通路 |

#### 03 · 战略陪伴

| 维度 | 状态 |
|---|---|
| 已有 backend services | 8 个 (`narrative_collector` 1192 行 / `narrative_generator` 1156 / `digital_asset_*` / `clarification_*` / `strategic_context`) |
| main.py endpoint | **31 个** |
| 关键样本 | `POST /api/v1/clients/{id}/digital-assets/narrative/refresh` ✅ 跟 AI 直接调风格匹配 |
| 能脱离 UI 调? | ✅ refresh endpoint 接 `client_id` 直接调 |
| 写数据? | ✅ 触发 narrative 重新生成 |
| 需人工确认? | ⚠️ "让 AI 重新理解" 用户已经手动触发, AI 自动触发可能扰动用户 |
| 审计日志? | ⚠️ reasoning_traces 7 行 (V2.4 P0-1/2 后才开始) |
| **当前缺口** | clarification.create 没有公开 endpoint (clarification_records 0 行) |

#### 04 · 资讯情报站

| 维度 | 状态 |
|---|---|
| 已有 backend services | **15 个 intelligence_* + internet_crawler** (含 `intelligence_candidate_supply` 7111 行最长) |
| main.py endpoint | **65 个** |
| 关键样本 | `POST /api/v1/intelligence-radar/...` 焦点指令 + 转任务 |
| 能脱离 UI 调? | ✅ 大部分 POST 接 payload |
| 写数据? | ✅ intelligence_candidate_items 1703 |
| 需人工确认? | ⚠️ 转任务时该确认, 当前不强制 |
| 审计日志? | ⚠️ 部分 |
| **当前缺口** | external_evidence_cards 0 行 — 爬虫数据没接 IngestPipeline |

#### 05 · 成长中心

| 维度 | 状态 |
|---|---|
| 已有 backend services | 4 个 (`growth_engine` 4870 / `badge_engine` / `exp_wall_service` / `experience_story_engine`) |
| main.py endpoint | **12 个** |
| 关键样本 | `POST /api/v1/growth/...` 成长信号写入 |
| 能脱离 UI 调? | ⚠️ 依赖 user_id 主体, AI agent 没 user 身份 |
| 写数据? | ✅ growth_signal_events 598 |
| **当前缺口** | ai_learned_rules 0 行 — 个人手册方法卡不能反哺 AI |

#### 06 · 智能文件导入

| 维度 | 状态 |
|---|---|
| 已有 backend services | **11 个** (`smart_file_import` 1358 + `link_material_import` / `document_decomposition` / `fact_extractor` / `entity_extractor` / `relation_extractor` / 等) |
| main.py endpoint | **16 个** |
| 关键样本 | `POST /api/v1/smart-file-import/sessions` (创建会话) → `POST .../narration` (加讲述) → `POST .../commit` (提交) |
| 能脱离 UI 调? | ✅ session 模型支持 backend 直接 POST, 不依赖 modal |
| 写数据? | ✅ documents 1922 / atomic_facts 2310 |
| **当前缺口** | smart_file_import:1002 直接 INSERT atomic_facts 没经 IngestPipeline (B K-3 异议 1 标记的错层) |

#### 07 · 数据中心

| 维度 | 状态 |
|---|---|
| 已有 backend services | **20 个 data_center_* + ingest_pipeline + idempotency_store + source_registry_store + atomic_fact_semantic_deriver + formal_conflict_detector + time_anchor_normalizer** |
| main.py endpoint | **36 个** |
| 关键样本 | `GET /api/v1/clients/{id}/fact-bundle` (L2 共识), `POST /api/v1/event-lines` (B F2.8 含 X-Actor-Type) |
| 能脱离 UI 调? | ✅ 数据中心 endpoint 都是 RESTful 风格 |
| 写数据? | ✅ atomic_facts 2310 / event_log 312 / ai_episode_log 312 |
| 需人工确认? | ⚠️ 部分 |
| 审计日志? | ✅ event_log 312 + ai_episode_log 312 + reasoning_traces 7 (V2.3 phase 1 + V2.4 P0 后) |
| **当前缺口** | A V2.4 P0-1 AtomicFactSemanticDeriver / P0-2 FormalConflictDetector / P0-4 StoryCardGenerator v2 **service-level 无 HTTP endpoint 暴露**, AI 直接调不到, 只能从 IngestPipeline 内部 trigger |

#### 08 · 组织计划工坊

| 维度 | 状态 |
|---|---|
| 已有 backend services | 4 个 (`module_dna` / `project_portrait_builder` / `proposal_approval` / `proposal_execution`) |
| main.py endpoint | **27 个** |
| 能脱离 UI 调? | ⚠️ 部分 |
| 写数据? | ⚠️ project_modules 4 (极少), proposal_records 0 |
| **当前缺口** | 整个板块的"task ↔ plan_item ↔ client_project ↔ outcome" 链路没接通 |

### A.3 总盘点表 (跟测试方案 §A 第一步要求格式对齐)

| 模块 | 后端服务 | 是否能脱离 UI | 是否写数据 | 是否需确认 | 当前缺口 |
|---|---|---|---|---|---|
| 01 任务与日程 | 10 services + 56 endpoint | ✅ | ✅ | ❌ 当前没 | task.create_draft 草稿态 |
| 02 客户工作台 | 14 services + 145 endpoint | ⚠️ session 依赖 | ✅ | ❌ | session_user → ai_agent 通路 |
| 03 战略陪伴 | 8 services + 31 endpoint | ✅ | ✅ | ⚠️ | clarification.create endpoint |
| 04 资讯情报站 | 15 services + 65 endpoint | ✅ | ✅ | ⚠️ | external_evidence_cards 接通 |
| 05 成长中心 | 4 services + 12 endpoint | ⚠️ user 主体 | ✅ | ❌ | ai_learned_rules 反哺 |
| 06 智能文件导入 | 11 services + 16 endpoint | ✅ session 模型 | ✅ | ❌ | smart_file_import → IngestPipeline 切迁 |
| 07 数据中心 | 20 services + 36 endpoint | ✅ | ✅ | ⚠️ | V2.4 P0-1/2/4 deriver/detector HTTP endpoint 暴露 |
| 08 组织计划工坊 | 4 services + 27 endpoint | ⚠️ | ⚠️ | ❌ | task ↔ plan ↔ project ↔ outcome 链路 |

→ **5/8 板块 (01/03/04/06/07) 能脱离 UI 调** ✅
→ **3/8 板块 (02/05/08) 部分需要补 service 层** ⚠️

→ 接口可调用性 (满分 20): 估 **14/20**

---

## §B · Tool Registry 草案

按测试方案 §B 要求, 每个 tool 包含 11 个字段.

### B.1 第一批 12 个 tool (按"会议纪要处理"场景拆)

| # | tool_name | module | input_schema (简化) | output_schema | required_context | writes_to | approval | audit | idempotency | rollback | current_status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `client.ingest_meeting_minutes` | workbench | `{client_id, project_id?, raw_text, meeting_date, source_type=meeting_minutes}` | `{document_id, chunk_ids[]}` | org_id/user_id/client_id | documents + v2_chunks + v2_documents | ❌ | ✅ event_log | ✅ idempotency_key | ✅ delete document_id | **partial** (smart_file_import session 模式, 需包装) |
| 2 | `facts.extract_from_note` | data_center | `{document_id, client_id, mode=llm}` | `{atomic_fact_ids[], entity_ids[]}` | client_id/source_id | atomic_facts + entities + entity_mentions | ❌ | ✅ reasoning_traces | ✅ document_id 幂等 | ✅ status=archived | **existing** (DocumentLLMExtractor V2.4 P0-1 派生) |
| 3 | `facts.derive_semantic` | data_center | `{client_id, atomic_fact_ids[]}` | `{event_line_activities[], risk_signals[], commitments[], strategic_thought_insights[]}` | client_id | event_line_activities + risk_signals + commitments + strategic_thought_insights | ❌ | ✅ ai_episode_log | ⚠️ 暂无 | ⚠️ | **partial** (A V2.4 P0-1 deriver 代码就位, 没 HTTP endpoint) |
| 4 | `task.create_draft` | task | `{client_id, project_id?, title, body, due_at, deriving_atomic_fact_ids[]}` | `{task_id, status=draft}` | client_id/user_id | tasks (status=draft) | ✅ (草稿→正式需确认) | ✅ event_log | ✅ | ✅ delete task_id | **missing** (POST /api/v1/tasks 直接正式, 没草稿态) |
| 5 | `risk.create_candidate` | data_center | `{client_id, risk_text, severity, source_fact_id}` | `{risk_signal_id, status=candidate}` | client_id | risk_signals | ⚠️ candidate→active 需确认 | ✅ | ✅ | ✅ | **partial** (risk_signals schema 已有, endpoint 缺) |
| 6 | `commitment.create_candidate` | data_center | `{client_id, committer, content, deadline, source_fact_id}` | `{commitment_id, status=candidate}` | client_id | commitments | ⚠️ | ✅ | ✅ | ✅ | **partial** (commitments schema 已有, endpoint 缺) |
| 7 | `clarification.create` | strategy | `{scope_type, scope_id, slot_key, question, suggested_resolution?}` | `{clarification_id}` | client_id/scope_id | clarification_records | ❌ (创建不需要) | ✅ | ✅ | ✅ | **missing** (clarification_records 0 行, endpoint 缺) |
| 8 | `cross_source.check_same_object` | data_center | `{client_id, subject_text, attribute}` | `{candidates: [{fact_id, match_type, score, suggested_action}]}` | client_id | (read only) | ❌ | ⚠️ | ✅ | N/A | **missing** (B 4-source arch §4 设计的同音字检测, 未实现) |
| 9 | `strategy.refresh` | strategy | `{client_id, force=false}` | `{narrative_id, sections[], confidence}` | client_id | digital_asset_narrative_snapshots | ⚠️ AI 自动调可能过频 | ✅ ai_episode_log | ✅ Idempotency-Key | ⚠️ | **existing** (`POST /api/v1/clients/{id}/digital-assets/narrative/refresh`) |
| 10 | `story_card.generate` | strategy | `{client_id, version=v2}` | `{card_json, segment_sources[], segment_confidences[]}` | client_id | (in-memory) | ❌ | ✅ | ✅ | N/A | **partial** (A V2.4 P0-4 StoryCardGenerator v2 代码就位, 无 HTTP) |
| 11 | `intelligence.create_focus_directive` | intelligence | `{client_id, directive_text, scope}` | `{directive_id}` | client_id | intelligence_search_intents | ❌ | ✅ | ✅ | ✅ | **existing** |
| 12 | `external_evidence.write` | data_center | `{client_id, source_url, source_tier, fact_excerpt, summary, tags, related_scope}` | `{evidence_card_id}` | client_id | external_evidence_cards | ❌ | ✅ | ✅ | ✅ | **missing** (external_evidence_cards 0 行, endpoint 缺) |

### B.2 当前状态统计

```
existing  (可用):   3 个 (#2/#9/#11)
partial   (需包装/无 HTTP): 5 个 (#1/#3/#5/#6/#10)
missing   (完全缺): 4 个 (#4/#7/#8/#12)
```

→ 12 个核心 tool 里 **25% existing / 42% partial / 33% missing**.

### B.3 Approval 队列分析

按测试方案 §九 硬门槛 4 (危险动作必须进入确认队列):

| 动作 | 危险级 | 当前有 approval 队列? |
|---|---|---|
| 创建正式任务 (非草稿) | 高 | 🔴 没有 |
| 更新权威事实 | 高 | 🔴 没有 |
| 关闭澄清 | 中 | 🔴 没有 (clarification_records 0 行) |
| 标记客户已确认 | 中 | ⚠️ 现有 verification_status='user_confirmed' 但靠前端按钮 |
| 对外发送材料 | 极高 | ⚠️ 暂无对外发送通道 |
| 推送飞书 | 极高 | ⚠️ feishu_sync 有, 但没 approval gate |
| 覆盖旧版本 | 高 | 🔴 没有 (V2.2 update_relation=supersedes 2 条, 没 approval) |

→ **approval 队列基础设施完全缺**, 是 3.0 推进的硬门槛阻塞.

---

## §C+§D · Headless 测试与数据库前后对比 (待批准)

按测试方案 §三原则二, 真实客户数据写入需保护策略 (test_run_id + 草稿 + 不可逆禁止). 这部分需要顾源源批准后跑.

### 准备好的 Headless 测试脚本结构 (待写, 不实际执行)

```python
# scripts/run_v23_headless_3_0_test.py (待写)
def test_meeting_minutes_pipeline():
    TEST_RUN_ID = f"headless_test_{uuid.uuid4().hex[:12]}"

    # Step 1: 写会议纪要 → workbench
    doc_id = call_tool("client.ingest_meeting_minutes", {
        "client_id": "client_xxx",
        "raw_text": MEETING_TEXT,
        "source_type": "meeting_minutes",
        "test_run_id": TEST_RUN_ID,  # 保护标记
    })

    # Step 2: 抽 atomic_facts
    fact_ids = call_tool("facts.extract_from_note", {
        "document_id": doc_id, "test_run_id": TEST_RUN_ID,
    })

    # Step 3-7: ... (剩余 5 步)

    # 检查前后数据库差异
    assert_db_diff(before, after, expected_tables=[...])

    # 回滚 test_run_id 标记的所有写入
    rollback(TEST_RUN_ID)
```

**先不跑**, 等顾源源批 §C/§D 再做.

---

## 6 维度评分 (按测试方案 §八)

| 维度 | 满分 | 实得 | 理由 |
|---|---|---|---|
| 接口可调用性 | 20 | **14** | 5/8 板块脱离 UI 可调, 3 板块需补 |
| 操作计划质量 | 15 | **N/A** | 没真跑 §C, 待 LLM 执行 |
| 多模块调度能力 | 20 | **N/A** | 没真跑 §C |
| 数据中心升级质量 | 20 | **8** | A V2.4 P0-1 派生器代码就位但没 HTTP, 实测 risk_signals/commitments/strategic_thought_insights 仍少 |
| 人工确认与安全边界 | 15 | **4** | X-Actor-Type 2/579 = 0.3% / approval 队列 0 / 跨客户隔离基础有但没专测 |
| 用户可感知价值 | 10 | **N/A** | 没真跑 |

**静态分: 26/55 = 47%** (动态 §C/§D 待跑)

---

## 6 项硬门槛预判 (按测试方案 §九)

| 门槛 | 静态扫描判断 |
|---|---|
| 1 AI 不能直接写数据库 | ✅ 多数 endpoint 走 service 层, 不暴露 SQL |
| 2 没有上下文绑定不能写入 | ⚠️ client_id 大部分有, 但 actor_type/actor_id/source_id 不全 (X-Actor-Type 2/579) |
| 3 不能只写 atomic_facts | ⚠️ A V2.4 P0-1 派生器代码就位, 但 endpoint 缺, AI 直接调只能进 atomic_facts |
| 4 危险动作必须进确认 | 🔴 ApprovalQueue 完全没有 |
| 5 必须有 Agent Run Log | ⚠️ ai_episode_log 312 行 ✅ + reasoning_traces 7 行 ✅ + 但不跟具体 endpoint 绑定 |

→ **5 硬门槛 1 ✅ / 3 ⚠️ / 1 🔴 = 第一轮静态扫描预判不通过**.

---

## §十一 评分结论

### A. 当前 3.0 接口化可行性等级

**🟢 B 级** — 部分模块可行, 需先补 AI agent context 绑定层

**理由**:
- 接口数量充足 (579 endpoint, 5/8 板块脱离 UI 可调) → 不是 C/D 级
- 但 AI agent context (X-Actor-Type/Idempotency-Key) 覆盖率 < 1% → 不是 A 级
- A V2.4 P0-1/2/4 service-level service 代码就位但没 HTTP endpoint → 派生器/检测器对 AI 透明
- ApprovalQueue 完全缺 → 3.0 安全边界硬门槛阻塞

### B. 最适合第一批 AI 接管的模块 (1-5 排序)

1. **会议纪要处理** → 06 智能文件导入 (smart_file_import session 模式天然支持 AI 调)
2. **任务草稿生成** → 01 任务与日程 (POST /tasks 已存在, 加 status=draft 参数即可)
3. **风险候选识别** → 07 数据中心 (risk_signals schema 就位, 缺 endpoint)
4. **澄清问题生成** → 03 战略陪伴 (clarification_records schema 就位, 缺 endpoint)
5. **战略陪伴刷新** → 03 战略陪伴 (`POST .../narrative/refresh` 已有 ✅)

### C. 当前最大阻碍 (按优先级)

| # | 阻碍 | 影响 | 工作量 |
|---|---|---|---|
| 1 | **AI agent context 绑定** (X-Actor-Type/X-Actor-Id) 覆盖 < 1% | 所有 endpoint 都不知道是 AI 还是 human 调的 | A 1-2 天 (统一 middleware) |
| 2 | **ApprovalQueue 基础设施完全缺** | 危险动作没法标 requires_human_approval | A 2-3 天 (新建表 + endpoint + 前端 UI) |
| 3 | A V2.4 P0-1/2/4 deriver/detector 没 HTTP endpoint | AI 调不到派生器, 只能从 IngestPipeline 内部 trigger | A 0.5 天 (加 endpoint wrap) |
| 4 | task.create_draft 草稿态缺失 | AI 创建任务等于直接发布 | A 0.5 天 (加 draft status + endpoint) |
| 5 | clarification.create 公开 endpoint 缺 | clarification_records 0 行的根 | A 0.5 天 |
| 6 | external_evidence.write 公开 endpoint 缺 | external_evidence_cards 0 行的根 | A 0.5 天 |
| 7 | workspace_chat session_user 依赖 | AI 调工作台对话需要绕开 session | A 1 天 |
| 8 | cross_source.check_same_object 完全缺失 | 同音字 (心灵 vs 心理) 没检测 | A V2.4 P1 1-2 天 |

总工作量: **~7-10 天 A 干, B 做集成测试**.

### D. 下一阶段建议 (根据测试结果反推)

按测试方案 §十三 "测试结束后我们怎么看结果" 的 4 种情况:

**当前判定: 情况一/二的混合**
- 大部分模块已有后端服务 ✅ (情况一)
- 但写入后只进 atomic_facts, 不派生 ⚠️ (情况二)

**建议下一步路径 (按优先级)**:

```
P0 (1-3 天): A 加 X-Actor-Type middleware 统一 579 endpoint
              + V2.4 P0-1/2/4 deriver/detector 加 HTTP endpoint 暴露
              → 解开"硬门槛 2/3" 阻塞
P1 (2-3 天): A 建 ApprovalQueue 基础设施 + 4 个 missing tool endpoint
              (task.create_draft / clarification.create / risk.create_candidate /
               external_evidence.write)
              → 解开"硬门槛 4" 阻塞
P2 (1 天): A 加 cross_source.check_same_object service (同音字检测)
            → 解开 B 4-source arch §4 设计的 2.0 检测层
P3 (1-2 天): B 写 Headless 测试脚本 + 跑 §C 真实场景
              → 拿到动态分 (操作计划质量/多模块调度/用户可感知价值)
P4 (1 天): B 跑 §D 前后对比 + 写 R2 完整报告 → 顾源源拍板 3.0 起步与否
```

总周期: **~7-10 天 P0-P4 跑完, 拿到 R2 完整 100 分制评分**.

---

## §C+§D 准备工作 (本报告未跑, 等批准)

### 真实客户候选 (跟 09 评估报告 §九对齐)

| 类型 | 客户 | 现状 |
|---|---|---|
| A 资料丰富 | 日慈基金会 | facts 1014 / chats 507 |
| B 正在推进 | 益语智库 | tasks 55 (推进活跃) |
| C 信息稀疏 | 善加基金会 | facts 26 / chats 66 |

### Headless 测试脚本待写
`scripts/run_v23_headless_3_0_test.py` (估 1 天)
- 含 test_run_id 保护标记
- 调 12 个 tool (#1-#12)
- 前后 11 张表 diff 对比
- 自动回滚

### 风险与保护

按测试方案 §三原则二:
- ✅ test_run_id 统一标记
- ✅ 草稿/候选状态
- ✅ 不发送/不推送/不删除
- ✅ 可回滚

---

## 总评

**3.0 接口化可行性: 🟢 B 级 (部分模块可行)**

接口**有**, 数量足, 服务化基础就位. **绑定层缺** (actor context / idempotency / approval), 这是 V2.4 P1/P2 该补的 P0-1/2/3/4 之后的真正下一步.

**距离 A 级 (Agent Gateway 可立刻做) 还差 7-10 天 P0-P4 工作量**.

**第一批 AI 接管模块推荐**: 06 智能文件导入 (天然 session 模型) + 01 任务与日程 (POST /tasks 已存在) + 03 战略陪伴 (narrative/refresh 已有).

---

**Author**: AI B (Claude Opus 4.7)
**评估日期**: 2026-05-23
**数据基础**: 主仓库 backend grep + sqlite3 + V2.4 P0-1/2/3/4 commits (45c5a7a/7e42c52/020e464/1908882)
**测试方案**: 顾源源 2026-05-23 钦定《3.0 接口化可行性测试方案》(第一轮, §A+§B 静态扫描 + Tool Registry, §C/§D 待批准)
**下次重跑**: P0-P4 跑完后输出 R2 100 分制完整评分
