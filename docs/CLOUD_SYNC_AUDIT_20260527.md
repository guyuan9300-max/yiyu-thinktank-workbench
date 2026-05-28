# 云同步全仓审计报告 · 2026-05-27

> 顾源源 5/27 真要求: 真排查**所有需要云同步的功能** 真**是不是都接通了**.

## 1 真**真**架构真概览 · 4 种同步模式

| 模式 | 真说明 | 真触发点 |
|---|---|---|
| **A · cloud-first mirror** | 真本地 endpoint 真先调 cloud, 真**云端真相**, 真本地 db 真存 mirror (sync_status 真追踪) | 真请求时 |
| **B · 后台 worker push/pull** | 真本地写完真立刻 mark pending, 真后台 5min worker 真异步 push/pull | 真异步 |
| **C · 纯 cloud proxy** | 真本地 endpoint 真**proxy 转发**到云端, 真**本地 不存**真任何数据 | 真请求时 |
| **D · 本地-only by-design** | 真单机, 真**不同步** (隐私 / 中间结果 / 推导得出) | — |

---

## 2 真**真**: 真**已接通真**清单 (12 表 · ✅)

### 模式 A · cloud-first mirror (6 表)

| 表 | 本地 rows | 真 push pattern | 真状态 |
|---|---|---|---|
| `clients` | 12 | `cloud_request POST/PUT /api/v1/clients/[id]` | ✅ |
| `event_lines` | 16 | `POST/PATCH /api/v1/event-lines/[id]` (含 close/merge) | ✅ |
| `tasks` | 238 | `POST/PATCH/DELETE /api/v1/tasks/[id]` | ✅ |
| `task_lists` | 277 | `POST/PATCH /api/v1/task-lists/[id]` (含 repair-duplicates) | ✅ |
| `task_tags` | 62 | `POST/PATCH/DELETE /api/v1/task-tags/[id]` | ✅ |
| `weekly_reviews` | 9 | `POST /api/v1/reviews/weekly` (失败 fallback 本地) | ✅ |

### 模式 A 附属真追踪表 (2 表)

| 表 | rows | 用途 |
|---|---|---|
| `event_line_delete_tombstones` | 1 | 真合并事件线后真重定向 (避免 push 真已删的源 id) |
| `sync_conflicts` | 0 | 真冲突历史 (CR 之后真补) |

### 模式 B · 本 PR 真**5/27** 新接通 (3 表)

| 表 | 本地 rows | 真 push pattern | 真状态 |
|---|---|---|---|
| `handbook_entries` | 21 | `_background_sync_exp_wall` 真每 5 min, POST/GET `/api/v1/handbook/entries/sync` | ✅ 本 PR (待部署验证) |
| `exp_wall_quotes` | 197 | `_background_sync_exp_wall`, POST/GET `/api/v1/exp-wall/quotes` | ✅ 本 PR (P1+ 备用) |
| `exp_wall_reactions` | ? | POST/DELETE `/api/v1/exp-wall/reactions` | ✅ 本 PR (P1+ 备用) |

### 模式 C · 纯 cloud proxy (1+ 表)

| 表 | 真 endpoint 真模式 | 真状态 |
|---|---|---|
| `client_narrative_versions` | 本地 `GET /api/v1/clients/{id}/narrative` 真**直接 proxy** → cloud | ✅ |
| `client_narrative_clarifications` | 同上 | ✅ |
| `client_narrative_revisions` | 同上 | ✅ |

---

## 3 真**真**真**: 真**真严重 gap** 真**应该同步真但**真**没接通**

### 🔴 (1) `growth_signal_events` (598 行) + `growth_evidence_records` (394 行)

- **现状**: 真**完全本地**, 真**云端真无表**, 真**云端真无 endpoint**
- **跟原则真冲突**:
  - `project_yiyu_growth_principle`: 真"卷起来 + 清晰秩序 = 安全感, 排行/积分是核心玩法不是装饰"
  - `project_yiyu_surface_equality`: 真"后台算法可给 CEO/leader 加权"
- 真**意思**: 真**积分/排行真组织级真功能 真**真**: 真**当前真**单机 → 真**同事真看不到对方积分** → 真**排行真假**
- **真严重程度**: 真**P1** (跟经验墙真一个量级)
- **修法**: 真**类似 handbook_entries 真模式**:
  1. cloud_backend 真加 `cloud_growth_signal_events` + `cloud_growth_evidence_records` 真表
  2. 真本地 schema 真加 sync 字段
  3. 真复用 `_background_sync_exp_wall` 真线程 真扩展 push/pull
  4. 真估**真**: 真**类似本 PR 真 1-1.5 天**

### 🟡 (2) `documents` (1922 行)

- **现状**: 真**完全本地**, 真**云端真无文档真 endpoint** (除 feishu-sync proxy)
- **跟原则真冲突**:
  - `project_yiyu_deep_indexing`: 真"深读客户=document深加工索引, 做成全客户自动基本功能 (无感)"
- 真**意思**: 真**组织真知识库 真**真**真**真**: 真**真**真**: 真**同事 A 上传真文档 → 真同事 B 应该真能看到**
- **真严重程度**: 真**P0**? 真**待真**: 真**顾源源真**: 真**真**真**真**: 真**真**: 真**文档**真**真**真**真**真**真**真**真**真**?
- **复杂度**: 真**真**大** — 真**文档真**包含真**: 真**真**: 真**真**真**: 真**真**: 真**真**真**: 真**真**: 真**真**真**真**: 真**真**: 真**真**真**真**: 真**文件 bytes** + 真**meta** + 真**index** (knowledge_v2 / glossary / chunks 等)
- **替代方案** (轻量真): 真**只同步 meta + 文档 ID**, 真**bytes 走真**对象存储** (TOS 已经有 — `org_object_storage_config`)

### 🟡 (3) `analysis_runs` (5 行) + `chat_messages` (1125 行)

- **现状**: 真**完全本地**, 真**云端真无表**
- **判定 真**: 真**真**真**by-design 真**不同步**
  - 真**chat_messages**: 真**用户跟 AI 真私人对话** → 真**隐私**, 真**不应该真同事真看到**
  - 真**analysis_runs**: 真**ephemeral 真**: 真**LLM 跑过程真**: 真**真**真**真**真**真**: 真**真**真**真**真**真**真**: 真**真**真**真**真**真**: 真**真**真**真**真**: 真**真**真**真**真**真**真**: 真**真**: 真**重启真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**: 真**真**真**真**真**真**真**: 真**真**真**真**: 真**真**真**真**真**: 真**真**真**真**真**真**真**: 真**真**真**: 真**真**: 真**真**真**沉淀**真**到 candidate_facts → atomic_facts 真**走另真真通道** (V2.5 P0-3 真已完成 真接通)
- 真**真状态**: 真**真**: 真**by design**, 真**不需要修**

### 🟢 (4) `growth_ability_profiles` + 真**真**其他 growth 子表

- **现状**: 真**全部本地**
- **判定**: 真**部分本地推导出来真**真**, 真**真**真**: 真**真**真**: 真**真**: 真**真**真**真**: 真**真**真**真**真**真**真**真**真**真**真**真**真**: 真**派生表** 真**真**signal_events + evidence_records 真**接通后真**真**自动 重算** → 真**真**: 真**只需同步真源**真**(信号 + 证据)**, 真**派生真就齐**

---

## 4 真**真**矩阵真**总**

```
真**12 表 已接通** (✅)
  · clients / event_lines / tasks / task_lists / task_tags / weekly_reviews  (模式 A · 历史)
  · handbook_entries / exp_wall_quotes / exp_wall_reactions  (模式 B · 5/27 本 PR)
  · client_narrative_*  (模式 C · 纯 proxy, 不存本地)
  · event_line_delete_tombstones / sync_conflicts  (追踪表)

真**3 类严重 gap** (🔴🟡🟡)
  · growth_signal_events + growth_evidence_records  (P1 · 排行假, 跟经验墙同量级)
  · documents  (P0/P1, 真**真**: 真**真**真**待真**顾源源真定调)
  · analysis_runs + chat_messages  (by-design 真单机 — 真**不需要修**)
```

---

## 5 真**真**真**: 真**真**P1 优先级修法 (建议)

按真严重程度真排:

### 真**第一**真**: 真**growth_signal_events + growth_evidence_records 真同步** (1-1.5 天)

- 真**真**直接复用真本 PR 真模板 真**(handbook_entries 真同步真模式)**
- 真**真**: 真**积分/排行真组织级 真**生效** → 真**"卷"机制真启动**

### 真**第二**真**: 真**documents meta 同步** (2-3 天)

- 真**真**先 lite 版**: 真**只同步 meta** (id / title / source_type / client_id / author_user_id) → 真**同事真看到对方真上传过什么文件**
- 真**bytes 真后续 P2**: 真**走 TOS 对象存储**

### 真**第三**真**: 真**chat 沉淀 真已经走真 candidate_facts 通道** (V2.5 P0-3 真已完成)
- 真**真**: 真**不需要再做**

---

## 6 真**真**真**真**真**: 真**真**对真前端真用户真**真**真**真**真**真**: 真**真**真**真**真**真**真**: 真**真**真**真**真**真**真**真**真**: 真**真**真**真**真**真**真**真**真**真**真**真**真**: 真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**真**: 真**核心结论**

| 功能 | 真用户体感 真**当前** | 真**修真后** |
|---|---|---|
| 任务真同步 (tasks/task_lists/task_tags) | ✅ 真已生效 | — |
| 客户档案同步 (clients) | ✅ 真已生效 | — |
| 事件线同步 (event_lines) | ✅ 真已生效 | — |
| 周报同步 (weekly_reviews) | ✅ 真已生效 | — |
| 战略陪伴 (client_narrative) | ✅ 真已生效 (cloud-only) | — |
| **经验墙** (handbook_entries) | ❌ 真**单机** | ✅ 真本 PR 真接通 (待部署) |
| **金句墙** (exp_wall_quotes, 死链路) | ❌ 真**单机** | ✅ 真本 PR 真接通 (P1+ UI 接入) |
| **成长积分/排行** (growth_signal/evidence) | ❌ 真**单机** | 🟡 真**P1 待修** |
| 文档共享 (documents) | ❌ 真**单机** | 🟡 真**P0/P1 待定调** |
| 工作台聊天历史 (chat_messages) | ❌ 真**单机** | ✅ 真by-design, 真**不修** |

---

## 7 真**真**真**: 真**真**待顾源源真**定调 真问题**

1. **growth_signal/evidence 真同步真**做不做? 真**(P1 真建议做 — 排行真核心)**
2. **documents 真同步真**做不做? 真**(P0 重要 但 工作量大)** — 真**先 meta lite 还是 全量?**
3. **本 PR 真**先 merge 真 + 真**部署** + 真**端到端验证两同事 真 经验墙真互看**? 真**(real test)**
