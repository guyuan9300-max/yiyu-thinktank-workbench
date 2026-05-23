# B AI · V3.0 Data Gap API 接口契约 (B-2)

> **触发**: V3.0 P0a 最关键接口 (12 docs §3 + B 辅助理解 §3 原则三)
> **作用**: 数据中心从"被动数据源"变"主动缺口发现器" — 这是 AI 公司操作层能真正工作的起点
> **目的**: 给 A 实现 backend service 提供明确接口契约, 不撞车不返工
> **执行人**: AI B
> **日期**: 2026-05-23

---

## 1 · 核心理念

```
2.0 现状: 数据中心 → 展示给页面 → 人类自己看 → 人类判断
3.0 目标: 数据中心 → 主动产出"我不知道什么" → AI 选工具去补 → 不确定的问人
```

→ **Data Gap = 数据中心的"自检报告"**, 不是用户主动查询, 是系统主动产出.

---

## 2 · DataGap 数据结构 (pydantic)

```python
# backend/app/services/data_gap_analyzer.py (新建, A 实现)

from typing import Literal
from pydantic import BaseModel, Field

GapType = Literal[
    "missing_authoritative_value",   # 多版本无 user_confirmed
    "missing_external_evidence",     # 内部说但无 internet_official 印证
    "missing_time_anchor",           # 重要 fact 没时间锚
    "missing_entity_unify",          # entity 散落 (同音字 / 同义近义)
    "missing_commitment_status",     # commitment 过期未关闭
    "stale_recent_activity",         # event_line_activities > 30 天没新增
    "missing_strategic_insight",     # strategic_thought_insights < 3 条
]

Priority = Literal["high", "medium", "low"]


class DataGap(BaseModel):
    """数据中心识别的一处缺口."""
    gap_id: str                          # 稳定 ID (基于内容 hash, 同一缺口反复 detect 不变)
    gap_type: GapType
    client_id: str
    description: str                     # 人读描述
    suggested_tools: list[str]           # 对应 Tool Registry tool_name, 优先级排序
    priority: Priority
    impact: str                          # 影响说明 (e.g. "影响对外材料和客户沟通口径")
    evidence_fact_ids: list[str]         # 触发本 gap 的 atomic_facts ID
    evidence_doc_ids: list[str] = []     # 关联 v2_documents
    detected_at: str                     # ISO timestamp
    metadata: dict = {}                  # gap_type 特定字段 (各类型不同)
```

---

## 3 · 7 类 gap_type 详细 spec

### 3.1 `missing_authoritative_value`

**触发条件**:
```sql
-- 同 client + 同 subject_text + 同 attribute, 有 2+ 不同 value_text,
-- 且最高 confidence 的那条 verification_status != 'user_confirmed'
SELECT subject_text, attribute,
       COUNT(DISTINCT value_normalized) AS variants,
       MAX(confidence) AS max_conf
FROM atomic_facts
WHERE client_id = ?
  AND status = 'active'
  AND validity_status != 'superseded'
GROUP BY subject_text, attribute
HAVING variants >= 2
  AND NOT EXISTS (SELECT 1 FROM atomic_facts af2
                  WHERE af2.subject_text = ... AND af2.verification_status = 'user_confirmed')
```

**suggested_tools**: `["workbench.ask_user", "clarification.create"]`

**priority**: high (如果跟 commitment / 对外材料相关)

**metadata 字段**:
```json
{
  "subject_text": "心盛计划",
  "attribute": "项目预算",
  "variants": ["50 万", "30 万"],
  "evidence_per_variant": {
    "50 万": ["af_xxx (旧版方案, 2025-03)"],
    "30 万": ["af_yyy (5/19 会议纪要)"]
  }
}
```

### 3.2 `missing_external_evidence`

**触发条件**:
```sql
-- 同 client + 同 subject + 同 attribute, 来源全是 client_internal_doc/collaboration_task,
-- 没有 internet_official / internet_media 印证
SELECT subject_text, attribute
FROM atomic_facts
WHERE client_id = ?
  AND status = 'active'
GROUP BY subject_text, attribute
HAVING NOT EXISTS (... source_type IN ('internet_official', 'internet_media'))
  AND COUNT(*) >= 2  -- 至少有 2 条内部 fact 才值得查外部
```

**suggested_tools**: `["intel.search", "external_evidence.write"]`

**priority**: medium

**metadata 字段**:
```json
{
  "subject_text": "心灵魔法学院",
  "internal_sources": ["client_internal_doc (9 条)", "collaboration_task (2 条)"],
  "external_sources": [],
  "search_keywords_suggestion": ["心灵魔法学院", "心灵魔法学院 日慈基金会"]
}
```

### 3.3 `missing_time_anchor`

**触发条件**:
```sql
-- decision / commitment / risk role 的 atomic_facts 没有 time_anchor
SELECT id, subject_text, attribute, value_text
FROM atomic_facts
WHERE client_id = ?
  AND content_role IN ('decision', 'commitment', 'risk')
  AND time_anchor IS NULL
  AND status = 'active'
LIMIT 10
```

**suggested_tools**: `["workbench.ask_user", "clarification.create"]`

**priority**: medium

**metadata 字段**:
```json
{
  "facts_missing_time": ["af_xxx", "af_yyy"],
  "estimated_count": 5
}
```

### 3.4 `missing_entity_unify` ★ 关键 (心灵 vs 心理同音字)

**触发条件**:
```sql
-- 同 client 内 entity_name 有 pinyin/embedding 相似度 ≥ 0.85 的散落 entity
-- 需要 cross_source_check service (B 4-source arch §4 设计的 2.0 同音字检测层)
```

**suggested_tools**: `["cross_source.check_same_object", "clarification.create"]`

**priority**: **high** (跨源印证的核心障碍)

**metadata 字段**:
```json
{
  "candidate_pairs": [
    {
      "entity_a": "心灵魔法学院",
      "entity_b": "心理魔法学院",
      "match_type": "pinyin",
      "score": 0.95,
      "occurrences_a": 9,
      "occurrences_b": 1,
      "suggested_canonical": "心灵魔法学院 (按 9:1 多数)"
    }
  ]
}
```

### 3.5 `missing_commitment_status`

**触发条件**:
```sql
-- commitments 表里 due_at 过期但 status 仍 'open'
SELECT id, committer, content, due_at
FROM commitments
WHERE client_id = ?
  AND status = 'open'
  AND due_at < datetime('now')
```

**suggested_tools**: `["workbench.ask_user", "task.create_draft"]`

**priority**: high (承诺过期影响客户信任)

### 3.6 `stale_recent_activity`

**触发条件**:
```sql
-- event_line_activities 最近 30 天没新增
SELECT MAX(happened_at) AS last_activity
FROM event_line_activities
WHERE client_id = ?
HAVING last_activity < datetime('now', '-30 days')
```

**suggested_tools**: `["workbench.ask_user", "weekly_review.generate", "intel.search"]`

**priority**: low (除非客户重要等级 high)

### 3.7 `missing_strategic_insight`

**触发条件**:
```sql
-- strategic_thought_insights < 3 条 (客户故事卡 next_steps 段不够厚)
SELECT COUNT(*) FROM strategic_thought_insights WHERE client_id = ? HAVING COUNT(*) < 3
```

**suggested_tools**: `["strategy.refresh", "story_card.generate"]`

**priority**: medium

---

## 4 · API endpoint 规范

### 4.1 `GET /api/v1/clients/{client_id}/data-gaps`

**Headers**:
```
X-Actor-Type: human / internal_ai_agent / external_ai_agent
X-Actor-Id: <user_id or agent_id>
```

**Query params**:
- `priority` (optional): filter by `high` / `medium` / `low`
- `gap_type` (optional): filter by 7 类
- `limit` (optional, default 20)

**Response 200**:
```json
{
  "client_id": "rici",
  "client_name": "日慈基金会",
  "scanned_at": "2026-05-23T08:50:00Z",
  "total_gaps": 5,
  "gaps_by_priority": {"high": 2, "medium": 2, "low": 1},
  "gaps": [
    {
      "gap_id": "gap_a1b2c3...",
      "gap_type": "missing_entity_unify",
      "client_id": "rici",
      "description": "...",
      "suggested_tools": ["cross_source.check_same_object", "clarification.create"],
      "priority": "high",
      "impact": "...",
      "evidence_fact_ids": ["af_xxx", "af_yyy"],
      "detected_at": "2026-05-23T08:50:00Z",
      "metadata": {...}
    }
  ]
}
```

**Response 404**: client not found
**Response 422**: invalid filter params

### 4.2 `POST /api/v1/clients/{client_id}/data-gaps/{gap_id}/resolve`

用户/AI 处理完 gap 后, 标记 resolved.

**Body**:
```json
{
  "resolution_type": "user_confirmed_authoritative" / "external_evidence_found" / "manually_dismissed",
  "resolved_by": "user_yyy or agent_xxx",
  "notes": "...",
  "linked_clarification_id": "clar_xxx (if any)"
}
```

---

## 5 · A 实现接口契约 (合规要求)

### 5.1 必填行为

| 行为 | 要求 |
|---|---|
| **不写副作用** | `GET /data-gaps` 只读, 不写任何表 |
| **可缓存** | 同 client_id 在 5 分钟内重复调返回相同 gap_id 集合 (避免每次都扫全表) |
| **稳定 gap_id** | `gap_id = hash(client_id + gap_type + sorted(evidence_fact_ids))`, 同一 gap 反复 detect 不变 |
| **跨客户隔离** | 严格按 client_id 过滤, 不能串 |
| **空缺口返回空数组** | 数据完整客户返回 `gaps: []`, 不是 404 |
| **suggested_tools 用 Tool Registry 名** | 不能写 free string, 必须匹配 `agent_tools` 表 tool_name |

### 5.2 性能要求

- 单客户扫描 < 2 秒 (基于 atomic_facts < 5000 行)
- 跨全部客户 < 10 秒
- 缓存 5 分钟 (cache key = client_id + last_atomic_facts_update_time)

### 5.3 跟 Tool Registry 联动

`suggested_tools` 字段值必须是 Tool Registry 注册过的工具名. 没注册的工具不能出现在 suggested.

→ Data Gap API 跟 Tool Registry 是**相互依赖**的, A 实现时应该同步.

---

## 6 · DataGap → Goal/Plan/Run 联动 (V3.0 P1)

外置 agent 工作流:

```bash
# Step 1: 拿到客户当前缺口
gaps=$(curl -X GET ".../data-gaps?priority=high")

# Step 2: 把 gap 当 goal 输入
yiyu agent goal create \
  --text "处理客户 X 的高优先级数据缺口" \
  --client-id X \
  --constraint resolve_gap_ids="${gap_ids}"

# Step 3: plan 自动按 gap.suggested_tools 拆步骤
# Step 4: run 按 plan 执行
# Step 5: gap.resolve 标记完成
```

→ Data Gap 不只是"显示给用户", 是**直接驱动 AI 工作的输入**.

---

## 7 · R2 测试场景 (B-3 测试脚本会用)

### 测试客户: 日慈基金会 (1014 facts, 已有"心灵 vs 心理"同音字案)

**预期 gaps**:
- 1 个 `missing_entity_unify` high (心灵 vs 心理魔法学院)
- 1 个 `missing_external_evidence` medium (internet_official source_type 0 行)
- 0-1 个 `missing_authoritative_value` (取决于 prod db 真实多版本)
- 0-1 个 `missing_strategic_insight` (取决于 strategic_thought_insights 是否 < 3)

**R2 验收**:
- `GET /data-gaps?client=rici` 返回 ≥ 3 gaps ✅
- gaps[0].gap_type 是预期类型 ✅
- gaps[0].suggested_tools 至少 1 个能被 yiyu agent run 调用 ✅
- gap_id 稳定 (同一 client 5 分钟内 2 次调返回相同 gap_id) ✅

---

## 8 · 跟 V2.4 P0-1/2/3/4 + V2.5 P0-1/2/3/4 关系

| A 已有 service | DataGapAnalyzer 复用 |
|---|---|
| `atomic_fact_semantic_deriver.py` (V2.4 P0-1) | 派生输出后, DataGapAnalyzer 检查派生表 row count |
| `formal_conflict_detector.py` (V2.4 P0-2) | conflict 输出直接关联 gap_type `missing_authoritative_value` |
| `time_anchor_normalizer.py` (V2.4 P0-3) | 检查 atomic_facts.time_anchor 字段格式 |
| `user_correction_handler.py` (V2.4 P2-7) | verification_status='user_confirmed' 是 gap 解锁信号 |
| `chat_message_reverse_ingester.py` (V2.5 P0-3) | chat 流量大时多触发 missing_authoritative_value gap |
| `ingest_pipeline.py` v25 trigger | ingest 后异步触发 gap analyzer (5 分钟内的 dedupe) |

→ DataGapAnalyzer **不需要新写抽取逻辑**, 全部基于现有派生器输出 + 跨表 JOIN 查询.

工作量预估: **A 1-2 天** (含 7 类 SQL + endpoint + 缓存 + 测试).

---

## 9 · 风险点 (B 提前 flag)

| 风险 | 影响 | 缓解 |
|---|---|---|
| pinyin/embedding 相似度计算依赖外部库 | gap_type `missing_entity_unify` 卡 | A 可先用 jieba.pinyin (Python 标准库) + embedding 留 V3.1 |
| 全表扫描慢 (atomic_facts 2310) | 单客户 > 5 秒 | 加索引: `(client_id, status, validity_status)` + `(client_id, subject_text, attribute)` |
| 缓存 key 设计错 | 同一 gap 重复 detect 不同 gap_id | 严格用 `hash(client_id + gap_type + sorted_fact_ids)` |
| 不可达 client_id 返回 404 vs 200 + 空 | 外置 agent 处理路径不清 | 推荐 200 + `gaps: []`, 404 仅在 client_id 完全不存在 |

---

**Author**: AI B · 2026-05-23
**给 A 接力**: 本契约 + Tool Registry 注册 12 个 tool 同步做. A 1-2 天可完工, B 等 endpoint 暴露后跑 R2 验收.
