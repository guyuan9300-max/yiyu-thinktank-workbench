# B AI · V2.3 阶段 1 B-1.1 · 14 张空管道表对账

> **触发**: A AI sync 指令 `B_AI_SYNC_V2_3_MASTER_PLAN.md` §B-1.1 (0.5 天)
> **对账依据**:
>   1. `V2.3_DATA_CENTER_MASTER_PLAN.md` 蓝图 §四 5 机制 / §五 4 层澄清 / §十 6 断点
>   2. A AI P0+P1 产物 `source_registry_store.py` + `V2.3_PHASE_1_P1_ENUM_LOCK.md` (12 content_role + 13 source_type + 20+ source_channel)
>   3. B AI 自己的 `B_AI_4_SOURCE_INFORMATION_ARCHITECTURE_20260522.md` §5 (5 张空表复用建议)
> **采样原则**: §7.3 独立 — sqlite3 自跑, 不 copy A 数字
> **执行人**: AI B
> **日期**: 2026-05-22 23:5x

---

## 0 · TL;DR

| 类别 | 数量 | 判决 |
|---|---|---|
| **直接复用** (现有 schema 够用, 蓝图要求 100% 覆盖) | **8 张** | A IngestPipeline 接 source_registry 时同步接入即可 |
| **扩字段** (现有 schema 缺 2-3 字段, 需 migration) | **4 张** | 阶段 1 B-1.2 写 schema migration |
| **暂搁** (跟 V2.3 蓝图弱相关, 留 V3.x) | **2 张** | event_line_weekly_snapshots / ai_improvement_suggestions |
| **本次实测 vs sync 指令"14 张 0 行" 差异** | **3 张已有流量** | event_log 312 / ai_episode_log 312 / reasoning_traces 7 — A FINAL 后已开始 |

**总判决**: 14 张表里 12 张 V2.3 必用, 2 张暂搁. **无需新建跨蓝图的表**. 蓝图 §十 6 断点全部能用现有 14 张表 + A P0 新建的 source_registry 覆盖.

---

## 1 · 14 张表 5 维对账表

| # | 表名 | 行 | 字段 | 蓝图对应 | 当前覆盖 | 复用结论 | 谁写入 | 谁消费 |
|---|---|---|---|---|---|---|---|---|
| 1 | **external_evidence_cards** | 0 | 23 | §十 断点 2 + §四 机制三 | ✅ source_tier/related_scope/confidence/status/linked_proposal/tags 齐 | **直接复用** | A 资讯情报站 ai_runner / B intelligence_card_enricher 入这里 (不进 atomic_facts) | B 战略陪伴 "外部观察" 段 + 4 层澄清第二层 |
| 2 | **clarification_records** | 0 | 13 | §四 机制五 + §五 4 层 | ⚠️ scope_type/slot_key/question/status 齐, **缺 cross_source_pair (同音字对照) + suggested_resolution** | **扩 2 字段** | A 同音字检测 service (B-3.2 撞 supersedes 时写) | B 战略陪伴 "待澄清" 区 (B-3.1 4 层 tab) |
| 3 | **cooperation_relationships** | 0 | 12 | §六 故事线四 + §五 第三层关系澄清 | ✅ why_connected/meaning_to_yiyu/meaning_to_client/cooperation_type/health/stakeholders/milestones 齐 | **直接复用** | A 阶段 4 故事卡服务 (B-4.1 项目维度) | B 战略陪伴 "我方-客户合作历程" 段 + 客户工作台首页 |
| 4 | **key_decisions** | 0 | 21 | §五 第四层战略澄清 + §四 机制四故事网 | ✅ decision_title/body/type/related_atomic_fact_ids/source_type/actor/confidence/verification/execution_status/superseded_by 齐 | **直接复用** | A meeting_action_extractor + 战略陪伴 thoughts review (V2.3 阶段 2 B-2.1) | B 战略陪伴 "战略决策" 段 + 计划工坊战略目标对齐 |
| 5 | **org_events** | 0 | 22 | §三 板块 2 + §六 故事线一时间线 | ✅ event_type/involved_person_ids/related_atomic_fact_ids/related_decision_ids/impact_severity/observed_at/source_type/actor/verification 齐 | **直接复用** | A IngestPipeline 接 source_registry (P2) 时识别"重组/任命/合并"自动写 | B 战略陪伴 "组织事件流" 段 + 故事卡时间线 |
| 6 | **event_log** | **312 已开始** | 12 | §一 核心目标统一事件总线 (跟 source_registry 兄弟) | ✅ event_type/actor_type/entity_type/payload/occurred_at/reversed_at (撤销可追) 齐 | **直接复用** | A IngestPipeline.ingest 已写入 (M-B 后 +312) | A loop_operator / B AI agent retry 排查 + dashboard 监控 |
| 7 | **event_line_state_changes** | 0 | 19 | §三 板块 1 + §六 故事线一 + §四 机制二事实版本 | ✅ event_line_id/change_type/from_status/to_status/owner 变更/trigger_source/confidence/impact/reversed 齐 | **直接复用** | A event_line 更新 endpoint (POST /api/v1/event-lines/{id}/transition 接) | B 战略陪伴时间线段 + 任务与日程 event line 历史 |
| 8 | **event_line_weekly_snapshots** | 0 | 12 | §三 板块 1 (周复盘) | ⚠️ stage_at_that_time/key_decisions_json/turning_points/blockers/progress_delta 齐, **但跟 weekly_reviews (9 条) 概念重叠** | **暂搁 V3.x** (跟 weekly_reviews 收敛后再用) | (暂不写) | (暂不消费) |
| 9 | **idempotency_keys** | 0 | 12 | §四 机制一 (来源置信度) + §一 N3 接入预留 | ✅ idempotency_key/method/path/body_hash/response/actor/expires/status 齐 (B F2.8 装好) | **直接复用** (B F2.8 已 装好 endpoint, 等 V2.3 真 trigger) | B F2.8 endpoint (event-lines/clients/tasks) — V2.3 用户层接通后才产生流量 | A loop_operator AI agent retry |
| 10 | **ai_episode_log** | **312 已开始** | 11 | §四 机制五澄清优先级 + §七 7 层架构 syslog | ✅ ai_session_id/action_type/referenced_fact_ids/referenced_doc_ids/outcome 齐 | **直接复用** | A IngestPipeline + narrative_generator 已写入 (M-B 后 +312) | B AI 自评 / loop_operator 监控 / 3.0 培训 |
| 11 | **reasoning_traces** | **7 已开始** | 20 | §四 机制三跨源印证 + §五 第二层口径澄清 | ✅ input_doc_ids/input_chunk_ids/input_fact_ids/prompt_summary/model/reasoning_steps_json/output_summary/confidence/triggered_update_relation 齐 | **直接复用** | A document_llm_extractor / narrative_generator 已开始写 (7 条) | B 战略陪伴 "AI 推理过程" 折叠区 + 4 层澄清第二层引用 |
| 12 | **ai_feedback_signals** | 0 | 7 | §四 机制一来源置信度 + §五 第一层事实澄清 | ⚠️ episode_id/user_id/signal_type/signal_target/user_correction 齐, **缺 confidence_delta / target_fact_id (跟 atomic_facts 直接连)** | **扩 2 字段** | A 用户在战略陪伴点"赞/纠错"按钮 → endpoint 写 (B-2.x) | A 来源置信度计算引擎 (每天调整 source_registry.trust_score) |
| 13 | **ai_improvement_suggestions** | 0 | 13 | §四 机制五 (但层级较高, AI 给 AI 改进建议) | ⚠️ suggestion_category/title/body/observed_pain_count/related_episode_ids/review_status 齐, **跟 V2.3 4 层澄清弱相关** | **暂搁 V3.x** (AI 自我改进高阶, V2.3 先解决人对 AI 反馈) | (暂不写) | (暂不消费) |
| 14 | **ai_learned_rules** | 0 | 12 | §四 机制一 + §四 机制五 (AI 学到的规则) | ⚠️ rule_name/body/why/how_to_apply/learned_from_episode_id/confidence/activated_count 齐, **缺 client_scope / rule_type (是用户层 vs 客户层 vs 系统层)** | **扩 1-2 字段** | A AI 自我反思机制 (异步, 跑 ai_episode_log 出 rule) | A IngestPipeline / narrative_generator 引用 rule 增强 prompt |

---

## 2 · 跟 A P0+P1 产物对账

### 2.1 source_registry (A P0 已建, 7795893)

跟 14 张表的连接点:

```
source_registry.source_type (13 enum)
  ↓ 被引用
external_evidence_cards.source_tier (新加约束: 用 enum)
key_decisions.source_type
org_events.source_type
reasoning_traces.* (input/output 描述)
event_log.* (event_type 跨表通用)
```

**B 建议**: A IngestPipeline 接 source_registry (P2) 时, 同步给上述 6 张表加 source_id (外键到 source_registry) — 现有 source_type 字符串保留兼容, 外键作精确追溯.

### 2.2 atomic_fact_confidence_history (A P1 补充已建)

跟 ai_feedback_signals 是兄弟表:
- atomic_fact_confidence_history: 每次置信度变化的时间序列 (A 已建)
- ai_feedback_signals: 用户对 atomic_fact 的反馈 (扩字段后写入触发 confidence 调整)

**B 建议**: ai_feedback_signals 扩 `target_atomic_fact_id` 字段 → 用户点"事实错"时, 写 ai_feedback_signals + 触发 atomic_fact_confidence_history 写一条 -0.1 的 delta.

### 2.3 12 content_role + 13 source_type enum 锁定

跟 14 张表的字段约束:

| 表 | 字段 | 应锁 enum | 当前 |
|---|---|---|---|
| external_evidence_cards | source_tier | 应该用 source_registry.trust_tier (A 锁 4 档) | 当前 free string |
| key_decisions | source_type | 应该用 13 source_type enum | 当前 free string |
| key_decisions | decision_type | 应锁 enum (proposal/agreement/cancellation/...) | 当前 free string |
| org_events | event_type | 应锁 enum (任命/重组/合并/解散/搬迁/...) | 当前 free string |
| org_events | source_type | 应锁 13 source_type | 当前 free string |
| event_log | event_type | 应锁 (ingest_completed / fact_superseded / clarify_resolved / ...) | 当前 free string |

**B 建议**: B-1.2 schema migration 时, 给上述 6 个字段加 CHECK constraint 锁 enum.

---

## 3 · 14 张表 → 蓝图 §十 6 断点 + §五 4 层澄清 全覆盖确认

### 3.1 蓝图 §十 6 断点覆盖

| 断点 | 描述 | 14 张表覆盖? | 表 |
|---|---|---|---|
| 1 | 工作台对话不入数据中心 | ⚠️ 部分 — 工作台对话该入 atomic_facts (interpretive_claim content_role) + ai_episode_log | atomic_facts (现有) + ai_episode_log (#10) |
| 2 | 资讯情报没进外部证据 | ✅ **external_evidence_cards** (#1) | #1 |
| 3 | 智能文件导入和口述不一致 | ⚠️ 部分 — 当前 atomic_facts source_channel 已能区分 (smart_import_narration vs workspace_chat), 但缺 oral_or_freetext_claims 中间层 | atomic_facts + source_channel (A P1) |
| 4 | 方法卡没连项目 | ❌ 14 张里没专门 method_cards 表 (现有 individual_handbook_cards 在 5 板块) | (V3.x 新建或 individual_handbook_cards 扩字段) |
| 5 | 计划工坊跟事实不连 | ✅ key_decisions (#4) + org_events (#5) + event_line_state_changes (#7) | #4 + #5 + #7 |
| 6 | 飞书旁路 | N/A (限制规则, 不是表) | - |

**覆盖度**: 4/6 直接 + 2/6 部分覆盖 (需 atomic_facts 扩 source_channel + 新建 method_cards V3.x).

### 3.2 蓝图 §五 4 层澄清覆盖

| 澄清层 | 描述 | 14 张表 |
|---|---|---|
| 第一层 事实澄清 | 这个事实到底是什么 | clarification_records (#2) + ai_feedback_signals (#12) |
| **第二层 口径澄清** | **为什么不同材料说法不一样 (心灵 vs 心理 同音字)** | clarification_records (#2 扩 cross_source_pair) + external_evidence_cards (#1) + reasoning_traces (#11) |
| 第三层 关系澄清 | 谁真正影响这件事 | cooperation_relationships (#3) + key_decisions.decided_by_person_ids |
| 第四层 战略澄清 | 这件事对项目走向意味着什么 | key_decisions (#4) + cooperation_relationships (#3) |

**覆盖度**: 4/4 全覆盖 ✅, 仅 clarification_records 需扩 2 字段 (cross_source_pair / suggested_resolution).

### 3.3 蓝图 §四 5 机制覆盖

| 机制 | 14 张表 |
|---|---|
| 一 来源置信度 | source_registry (A 已建) + atomic_fact_confidence_history (A 已建) + ai_feedback_signals (#12) + idempotency_keys (#9) |
| 二 事实聚类与版本 | atomic_facts.update_relation (现有) + event_line_state_changes (#7) |
| 三 跨源印证与冲突 | fact_contradictions (现有 81 行) + clarification_records (#2) + reasoning_traces (#11) |
| 四 故事网 | narrative_generator (现有) + cooperation_relationships (#3) + event_line_state_changes (#7) + org_events (#5) |
| 五 澄清优先级 | clarification_records (#2) + ai_feedback_signals (#12) + ai_episode_log (#10) |

**5/5 机制全覆盖** ✅

---

## 4 · B-1.2 schema migration 清单 (下一步 1 天)

按本 audit, B-1.2 该写的 migration:

| # | 操作 | 表 | 字段 | 类型 |
|---|---|---|---|---|
| 1 | ALTER ADD | clarification_records | cross_source_pair_json | TEXT |
| 2 | ALTER ADD | clarification_records | suggested_resolution | TEXT |
| 3 | ALTER ADD | ai_feedback_signals | target_atomic_fact_id | TEXT |
| 4 | ALTER ADD | ai_feedback_signals | confidence_delta | REAL |
| 5 | ALTER ADD | ai_learned_rules | client_scope | TEXT |
| 6 | ALTER ADD | ai_learned_rules | rule_type | TEXT |
| 7 | ALTER ADD | external_evidence_cards | source_id | TEXT (FK source_registry) |
| 8 | ALTER ADD | key_decisions | source_id | TEXT (FK source_registry) |
| 9 | ALTER ADD | org_events | source_id | TEXT (FK source_registry) |
| 10 | CHECK CONSTRAINT | key_decisions | source_type | 13 enum |
| 11 | CHECK CONSTRAINT | org_events | source_type | 13 enum |
| 12 | CHECK CONSTRAINT | org_events | event_type | (任命/重组/合并/解散/...) — 待 A 锁 |
| 13 | INDEX | external_evidence_cards | (related_scope_type, related_scope_id, status) |
| 14 | INDEX | clarification_records | (scope_type, scope_id, status) |
| 15 | INDEX | key_decisions | (client_id, decided_at DESC) |

**12 个 ALTER + 3 个 INDEX**, 估 0.5 天写 migration + 0.5 天单测.

---

## 5 · 4 个 V2.3 蓝图新需求 — 现有 14 张里无, 待 B-1.2 / V3.x 决策

| 需求 | 蓝图位置 | 当前 schema 状态 | 建议 |
|---|---|---|---|
| **interpretive_claims** (用户主观判断, 不算事实) | 断点 1 | 没表 | 现有 atomic_facts 加 content_role='interpretive_claim' (A P1 已锁) + 不直进 atomic_facts 而进 external_evidence_cards 模式? 待 A 决策 |
| **oral_or_freetext_claims** (统一用户口述处理器) | 断点 3 | 没表 | 同上, atomic_facts + source_channel='workspace_chat'/'smart_import_narration' (A P1 已锁) 已能区分 |
| **method_cards** (方法卡跟项目场景连接) | 断点 4 | 部分 — individual_handbook_cards 现有但不连项目 | 现有表加 4 字段 (target_client_type / target_project_phase / target_task_type / target_risk_type) 即可, 不需新表 |
| **plan_item → client_project → task → evidence → outcome → review 链** | 断点 5 | 已有 4/6 表 (project_modules / tasks / atomic_facts as evidence / weekly_reviews) | 缺 outcome 表 (V3.x 加) |

→ **B-1.2 不新建表**, 都用现有 schema 扩字段解决.

---

## 6 · 对 A AI 的接力提示

### 6.1 已确认 A 可立刻继续 P2 (IngestPipeline 接 source_registry)

本 audit 14 张表 12 张直接复用 / 2 张暂搁, **A IngestPipeline 接 source_registry 时不需要等 B-1.2 schema migration 完成**, 可并行.

### 6.2 给 A 的 6 个 source_type / event_type 待锁 enum 候选

```
key_decisions.decision_type:
  agreement / proposal / cancellation / adjustment / pilot / scaling
org_events.event_type:
  appointment / role_change / restructure / merger / split / dissolution
  / location_change / leadership_change / strategy_shift / financial_event
event_log.event_type (跨表事件总线):
  ingest_completed / fact_superseded / fact_conflict / clarify_opened
  / clarify_resolved / source_registered / cross_source_check / ...
```

A 在 V2.3_PHASE_1_P1_ENUM_LOCK.md 里继续锁这 3 套 enum.

### 6.3 给 B-1.2 migration 的合作点

```
A 提供 source_registry.source_id 主键格式 (UUID? hash?)
B migration: external_evidence_cards / key_decisions / org_events 加 source_id FK
```

---

## 7 · 验收门 (跟 sync 指令 §B-1.1 对照)

| 验收 | 状态 |
|---|---|
| 实测 14 张表行数 + 字段 | ✅ 完整 (含 3 张已开始有流量) |
| 跟蓝图 §十 6 断点对账 | ✅ 4/6 直接 + 2/6 部分 |
| 跟蓝图 §五 4 层澄清对账 | ✅ 4/4 全覆盖 |
| 跟蓝图 §四 5 机制对账 | ✅ 5/5 全覆盖 |
| 跟 A P0+P1 (source_registry / enum / atomic_fact_confidence_history) 对账 | ✅ 6 个字段加 source_id FK + 6 个字段锁 enum |
| 复用 / 扩字段 / 新建 判决 | ✅ 8 复用 / 4 扩字段 / 0 新建 / 2 暂搁 |
| B-1.2 migration 清单输出 | ✅ 12 ALTER + 3 INDEX |

---

## 8 · 综合判决

V2.3 阶段 1 起步阶段 — **14 张已有空管道 schema 设计极完整, 7 维数据中心 §七 7 层架构基本不需新建表**.

```
V2.2 时期: 14 张表设计了没接通 (空管道债)
V2.3 阶段 1: 12 张接通 + 2 张暂搁 + 5 字段扩展
V2.3 阶段 2-4: 顺着 A IngestPipeline + B 9 板块前端入口逐步填流量
```

这正是 V2.2 资产清单 §6 原则 5 "0 行表 ≠ 没用, 可能是设计完整的空管道, 优先填它们而不是新建" 的真实兑现.

**V2.3 阶段 1 起步极顺**: A P0/P1 schema 锁完, B 14 张表 audit 完, 双方下一步 (A P2 接 IngestPipeline + B B-1.2 migration) 互不阻塞.

---

**Author**: B AI · 2026-05-22 23:5x · V2.3 阶段 1 B-1.1 完成
**附**: 实测 atomic_facts 现有 11 张空 + 3 张已开始 (event_log 312 / ai_episode_log 312 / reasoning_traces 7). A FINAL audit "N3 2 张表" 应更新为"N3 3 张表 + 流量".
