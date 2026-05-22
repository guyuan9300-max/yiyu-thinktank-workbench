# B AI · 4 来源信息架构设计 · 按信息特质分通道处理

> **触发**: 顾源源 5/22 "你应该去设计的是 4 信息源进来的通路, 它们置信度有什么不一样, 信息质量和特点有什么不一样. 从功能板块出发, 排查 4 信息源所有信息种类和特质, 按特质决定数据中心怎么处理"
> **触发洞察**: "心灵魔法学院" vs "心理魔法学院" 同音字事件 — 不是 LLM 问题, 是 V2.2 数据架构没接住跨源印证
> **数据基础**: 刚跑过的 prod db 实测 + 9 板块 systematic inventory (commit `6cd753a`)
> **执行人**: AI B
> **日期**: 2026-05-22

---

## 0 · TL;DR

V2.2 当前架构错把"4 来源"当**枚举标签** (写在 source_type 字段), 实际**没按特质分通道处理**.

真正该做:
- 4 来源 = 4 套**信息特质组合** (权威性 / 时效性 / 同音字风险 / 立场偏见 / 可验证性)
- 按特质 → 4 处理通道 (高权威直入 / 中权威待验证 / 低权威 cross-check / UGC 隔离)
- 加 **2.0 同音字+同义近义检测层** (V2.2 致命缺失)
- 利用现有 14 张空管道 (external_evidence_cards / clarification_records / 等) 而非新建

---

## 1 · 从 9 板块出发: 4 来源真实信息种类清单

### 1.1 路径 1 · 工作台文件 (workbench_file) — 含 5 种实质信息

| 种类 | 实例 | 实测 atomic_facts 数 | 来自板块 |
|---|---|---|---|
| ★ 客户官方文件 | 合同 / 章程 / 官网公示 PDF / 监管公示 | 33 条 (1 doc) | 02 工作台 + 04 资讯情报 (爬到的官网) |
| ★ 客户内部文件 | 项目方案 / 会议纪要 / 内部邮件 / 数据报告 | 70 条 (1 doc) | 02 工作台 + 06 智能文件导入 |
| ★ 会议录音转文字 | 战略对齐会录音 → docx | 1998 条 (59 docs, 大头) | 02 工作台 + 06 |
| 客户对话截图 | 微信对话 / IM 群聊截图 OCR | 0 条 | 02 + 06 |
| 客户工具产出 | Excel 表格 / Notion 卡片 | 部分 | 02 |

### 1.2 路径 2 · 任务/复盘/协作 (task_review) — 4 种

| 种类 | 实例 | 实测 | 板块 |
|---|---|---|---|
| ★ 我方任务承诺 | tasks 表 "顾源源: 对齐心盛计划后续迭代方向" | 114 条 | 01 任务与日程 |
| ★ 我方周复盘 | weekly_reviews 9 条 | 部分 | 01 |
| ★ 我方会议纪要 | meetings 7 / agenda_items 10 / action_items 4 | 部分 | 01 |
| 我方文档批注 | 战略文档评论 | 0 (没接) | 03 战略陪伴 |

### 1.3 路径 3 · 互联网爬虫 (internet_crawler) — 4 种 **全部 0 条**

| 种类 | 实例 | 实测 | 设计板块 |
|---|---|---|---|
| ★★★ **客户官网真权威** | 日慈基金会官网"心灵魔法学院"项目页 | **0 条** ⚠️ | 04 资讯情报站 (有 intelligence_candidate_items 1703 条但不进 atomic_facts) |
| 政府公示 | 民政部社会组织信用记录 / 资助金额 | 0 条 | 04 |
| 主流媒体报道 | 人民网 / 新华网 等 | 0 条 | 04 |
| 公众号 / UGC | 公众号文章 / 微博 / 知乎 | 0 条 | 04 |

### 1.4 路径 4 · 手机 AI 朋友式聊天 (mobile_ai_chat) — 3 种 **全部 0 条**

| 种类 | 实例 | 实测 | 设计板块 |
|---|---|---|---|
| ★ 用户口述客户事实 | "强哥最近升副总" | **0 条** | 手机端 v2 (未启动) |
| 用户主观观察 | "我觉得张真这次态度变了" | 0 条 | 手机端 |
| 用户即时澄清 | AI 问"心理还是心灵?" 用户答"心灵" | 0 条 | 手机端 + clarification_records 表 (0 行) |

---

## 2 · 5 维信息特质矩阵

每种信息按 5 个轴打分 (1-5):

```
轴 1: 权威性     (1 = UGC, 5 = 政府/官网/已签合同)
轴 2: 时效性     (1 = 实时口述, 5 = 永久存档章程)
轴 3: 同音字风险  (1 = 文字稿/截图, 5 = 语音转文字/口述)
轴 4: 立场偏见   (1 = 中立数据, 5 = 媒体观点/AI 推断稿)
轴 5: 可验证性   (1 = 纯口述无原文, 5 = 有官方原文可追溯)
```

| source_type | 权威性 | 时效性 | 同音字风险 | 立场偏见 | 可验证性 | 综合特质 |
|---|---|---|---|---|---|---|
| **internet_official** (官网/政府) | **5** | 4 | 1 | 1 | **5** | ★★ 基准事实 |
| **client_official_doc** (合同/章程 PDF) | **5** | **5** | 1 | 1 | **5** | ★★ 长期基准 |
| **client_internal_doc** (项目方案/纪要) | 4 | 4 | 2 | 2 | 4 | ★ 中期权威 |
| client_verbal_meeting (录音→文字) | 3 | 2 | **5** ★ | 2 | 3 | ⚠️ **同音字高危** |
| internet_media (主流媒体) | 3 | 3 | 1 | 4 | 3 | 含立场 |
| collaboration_task (我方任务) | 3 | 2 | 2 | 3 | 4 | 我方视角 |
| collaboration_review (我方复盘) | 3 | 3 | 2 | 4 | 4 | 含后置反思 |
| user_observation (用户主观) | 2 | 1 | 2 | 5 | 2 | 主观高 |
| user_verbal_fact (用户口述客户事实) | 2 | 1 | **5** | 3 | 2 | ⚠️ **双重风险** |
| internet_ugc (公众号/微博) | 1 | 2 | 1 | **5** | 2 | UGC 立场强 |
| internet_ai_inferred (AI 分析稿) | 1 | 2 | 1 | **5** | 1 | ★ 最危险 |
| llm_extracted (LLM 抽出, 内部加工) | - | - | 继承源 | 继承源 | 继承源 | 应该**透明继承上游来源**, 现实是孤立写入 |

### 2.1 ★ 关键观察 (心灵/心理魔法学院案例)

按特质矩阵看真实数据 (atomic_facts 心灵/心理 魔法学院实测):

| 来源 | 内容 | 特质分析 | 应有处理 |
|---|---|---|---|
| client_internal_doc 9 条 "**心灵**魔法学院" | 项目方案 / 内部数据报告 | 权威 4 + 同音字风险低 2 | 应作**基准** |
| client_official_doc 1 条 "**心理**魔法学院" | 实际是会议纪要被错分 | 权威标签错配 + 同音字风险高 5 | 应跨源 check, 撞 conflict |
| collaboration_task 张真承诺 "**心灵**魔法学院" | 我方任务 | 权威 3 + 同音字风险低 2 | 印证 internal_doc |
| llm_extracted 录音转文字 "心灵" 多次 + "心理" 1 次 | 语音转文字 | 权威 3 + **同音字风险 5** | 必须跨源 check |
| internet_official 日慈官网 "心灵魔法学院" 项目页 | **没爬过, 0 条** | 权威 5 + 同音字风险 1 + 可验证 5 | **真基准缺失** |

→ 5 个来源里 4 个写"心灵", 1 个写"心理" — **任何 1.0 跨源规则都该撞 conflict, 但 V2.2 0 触发**.

→ 真致命: **internet_official 来源 0 条** — 缺最高权威基准, 4 个 "心灵" 写法之间互证也不够 (它们都是同源 docx 抽出, 不算独立验证).

---

## 3 · 4 处理通道设计

不是所有信息都写进 atomic_facts. 按特质决定处理通道:

### 通道 A · 高权威基准直入 (权威 ≥ 4 + 可验证 ≥ 4)

```
入: internet_official + client_official_doc (真章程/合同/官网, 不是误分类的)
出: atomic_facts (validity_status='current' + verification_status='user_confirmed'
   + confidence ≥ 0.95 + 长 lifecycle)

作用: 基准, 所有其它信息要跟它对账
```

### 通道 B · 中权威标待验证 (权威 = 3-4 + 可验证 ≥ 3)

```
入: client_internal_doc + collaboration_task + collaboration_review + internet_media
出: atomic_facts (verification_status='unverified' + confidence 0.7-0.9)
    + cross-check trigger 加入待澄清队列 (clarification_records)
```

### 通道 C · 低权威需跨源 cross-check (权威 ≤ 2 OR 同音字风险 ≥ 4)

```
入: client_verbal_meeting + user_verbal_fact + 任何"同音字风险 ≥ 4" 的
出: 第一步 → external_evidence_cards (现有空表, 23 字段就位)
    第二步 → 找通道 A/B 同 subject 的事实做 cross-check
    第三步:
      · 字面相同 → 升级写 atomic_facts (verification='user_confirmed')
      · 同音字嫌疑 → 写 clarification_records 等用户澄清
      · 完全 conflict → 用 update_relation='conflict' 写, 弹给用户
```

★ 这是"心灵 vs 心理"案例真正该走的通道. V2.2 缺失.

### 通道 D · UGC / AI 推断隔离 (权威 ≤ 2 + 立场 ≥ 4)

```
入: internet_ugc + internet_ai_inferred
出: external_evidence_cards (永不直进 atomic_facts)
作用: 仅作背景参考, 用户手动 promote 才入主层
```

### 通道矩阵 (按 source_type 分配)

| source_type | 通道 | 行为 |
|---|---|---|
| internet_official | A | 直入 atomic_facts |
| client_official_doc (真章程) | A | 直入 |
| client_internal_doc | B | atomic_facts + cross-check trigger |
| internet_media | B | atomic_facts + 标 source 立场 |
| client_verbal_meeting | C | 先入 evidence_cards + 找 A/B 对账 |
| user_verbal_fact | C | 先入 evidence_cards |
| collaboration_task | B | atomic_facts (我方视角标记) |
| collaboration_review | B | atomic_facts |
| user_observation | C | 先入 evidence_cards |
| internet_ugc | D | 仅 evidence_cards, 永不主层 |
| internet_ai_inferred | D | 仅 evidence_cards |
| llm_extracted | **继承上游通道** | 透传 source_type, 不应该独立成一类 |

---

## 4 · 2.0 同音字 + 同义近义检测层 (V2.2 致命缺失)

按 Karpathy §1 三层架构:

| 检测 | 应用层 | 实例 |
|---|---|---|
| 字符串相等 | 1.0 SQL `subject_text = X` | "心灵魔法学院" = "心灵魔法学院" |
| **同音字识别** | **2.0 训练好的中文音素相似模型** | "心灵" vs "心理" 同 pinyin xinli, 嫌疑度 0.95 |
| **同义近义** | **2.0 embedding 相似度** | "心灵" vs "灵魂" embed sim 0.7 |
| 语义全等 | 3.0 LLM 判断 | "本质是同一个项目吗?" |

V2.2 当前 detect_update_relation 是 **1.0 字符串相等**, 这就是"心灵/心理"对撞 0 触发的根因.

### 4.1 必加的 2.0 检测函数

```python
# backend/app/services/cross_source_check.py (新建)
def detect_same_object_candidates(subject_text: str, client_id: str) -> list[dict]:
    """跨 source_type 找候选同对象 fact, 给出嫌疑度.

    检测维度:
    1. 字符串相等 (1.0)
    2. pinyin 相等 (2.0 jieba.pinyin)
    3. embedding 相似度 ≥ 0.85 (2.0 embedding_provider)
    4. LLM 语义判断 (3.0, 仅在 2.0 嫌疑 ≥ 0.7 时调用)

    返回: [{candidate_id, match_type, score, suggested_action}]
    """
```

调用时机: 通道 C 写入 atomic_facts 前必跑 + 通道 B 写入时异步跑.

### 4.2 嫌疑度 → 行动

```
sim ≥ 0.95: 字符串相等 → 升级 supersedes
0.85 ≤ sim < 0.95: 同音字 + 同 attribute 嫌疑 → 写 clarification_records + 弹用户
0.5 ≤ sim < 0.85: 弱嫌疑 → 写 external_evidence_cards 关联
sim < 0.5: 不算同对象
```

---

## 5 · 利用现有 14 张空管道 (不新建)

| 现有空表 (字段数, 0 行) | 应该承担的角色 |
|---|---|
| **external_evidence_cards** (23) | 通道 C/D 的暂存层 — 待 cross-check 的低权威信息 |
| **clarification_records** (13) | 同音字嫌疑 / cross-source conflict 用户澄清队列 |
| **cooperation_relationships** (12) | 跨客户人物-机构合作关系图 (entity 表 4987 现成的关联) |
| **key_decisions** (21) | 通道 A 沉淀的关键决策 (跟 atomic_facts decision role 互补) |
| **org_events** (22) | 组织事件 (任命/重组/合并/解散) — 比 atomic_facts 散记更结构化 |
| **event_log** (12, 217 行 - 已开始) | 整条系统事件总线 |
| **prompt_log** (15) | LLM 调用日志 (含调用 cross_source_check 的) |
| **idempotency_keys** (12) | AI agent retry 防重 (V2.1 F2.8 N3 A6) |
| **ai_episode_log** (11, 147 行 - 已开始) | AI 推理 episode |

→ V2.2 14 张空表里 5 张正好是 4 来源架构需要的处理通道支撑. **不要新建表**.

---

## 6 · 9 板块如何用这套架构

| 板块 | 信息流 |
|---|---|
| 01 任务与日程 | 任务承诺 → 通道 B → atomic_facts + collaboration_task |
| 02 客户工作台 | 文件上传 → 自动分类: 合同→A / 项目方案→B / 录音→C |
| 03 战略陪伴 | 6 段叙事 + 待澄清队列 (clarification_records) — 用户看 conflict 自己改 |
| **04 资讯情报站** | 爬虫 → 自动分: 官网→A / 媒体→B / UGC→D ★ **当前 0 接入** |
| 05 成长中心 | 成长信号 (一般不进数据中心) |
| 06 智能文件导入 | 拖文件 + 口述背景 → 通道 B (文件) + 通道 C (口述) |
| 07 数据中心 | 全部承载 |
| 08a 计划工坊 | 决策 → 通道 B → key_decisions 表 |
| 08b 系统设置 | 来源管理 / 通道开关 / 阈值配置 |

---

## 7 · 落地路径 (V2.3 计划)

按可感知度 + 依赖关系排:

### 第 1 步 (1 天) · 同音字检测能跑出来

修 `ingest_pipeline.detect_update_relation` 加 2.0 同音字层. 不接通新路径, 先让"心灵/心理"撞出来.

验收: 跑一次现有 atomic_facts retro-scan, "心灵"/"心理"魔法学院进 clarification_records 表至少 1 条.

### 第 2 步 (2-3 天) · 路径 3 官网接入

按通道 A 接 internet_official.
- 抓 日慈基金会官网项目页 (已有 internet_crawler 1430 行)
- 走 IngestPipeline (绑 metadata_for_internet_crawler normalizer)
- 写入 atomic_facts + verification_status='user_confirmed' (官网真权威)

验收: 跑 baseline, 日慈"心灵魔法学院"在 internet_official 至少 1 条 + 撞 client_internal_doc 的 9 条 supersedes/none.

### 第 3 步 (3-5 天) · 通道 C 接通 external_evidence_cards

verbal_meeting + user_verbal_fact 不直进 atomic_facts, 先入 evidence_cards. clarification_records 接前端 (战略陪伴"待澄清"区).

验收: 5/19 录音 docx 重抽时, 走通道 C, "心理"作为低权威 evidence_card 暂存, 经 cross-check 后弹给用户澄清.

### 第 4 步 (跟 §3.2 同) · cross_source_check service

新建 `backend/app/services/cross_source_check.py` — 4 层检测.
跟现有 entities 表 (4987) + embedding_provider 整合.

验收: 跑 retro-scan, 给出全 prod db 同音字 / 同义近义嫌疑清单.

### 第 5 步 (优化) · 4 来源每来源专属 normalizer

`metadata_for_internet_official` (高权威, confidence 默认 0.95)
`metadata_for_client_verbal_meeting` (同音字风险, confidence 默认 0.6 + lifecycle 短)
等

---

## 8 · 给 A 接力的 contract

A 如要接 V2.3 路径 3 + 同音字检测, B 提供:

```python
# 1. cross_source_check.py 接口契约
def detect_same_object_candidates(
    db, client_id: str, new_subject: str, new_attribute: str
) -> list[Candidate]:
    """返回同对象嫌疑候选 + 嫌疑度 + 建议 action"""

class Candidate:
    existing_fact_id: str
    match_type: Literal["string_eq", "pinyin", "embedding", "llm"]
    score: float  # 0-1
    suggested_action: Literal["supersedes", "clarify", "evidence_card", "ignore"]

# 2. ingest_pipeline.ingest() 加 cross_source_check hook
# 在 detect_update_relation 之后调用
# 嫌疑度 ≥ 0.85 → 自动写 clarification_records + verification_status='disputed'

# 3. clarification_records 字段映射 (现有 13 字段)
{
    "client_id", "subject_text_a", "subject_text_b",
    "match_type", "score", "evidence_fact_ids_json",
    "status",  # pending / resolved / dismissed
    "user_resolution_subject",  # 用户选了哪个
    "resolved_by_user_id", "resolved_at", ...
}
```

---

## 9 · 真验收门 (跟 V2.2 大成 7/7 比)

V2.2 大成 7/7 测的是: **关键词字符串匹配**.

V2.3 真验收门:

| # | 测试 | 数据来源 |
|---|---|---|
| 1 | "心灵"vs"心理"同音字案在 V2.3 后撞 clarification_records | 通道 C + cross_source_check |
| 2 | 日慈官网"心灵魔法学院"进 atomic_facts (internet_official 来源) | 通道 A + 路径 3 |
| 3 | atomic_facts update_relation 实际分布: 5%+ 是 conflict/supersedes (而非 0.1%) | 真跨源印证 |
| 4 | clarification_records ≥ 10 条 (真用户澄清记录) | 通道 C + 前端"待澄清"区 |
| 5 | 用户问 AI "心灵还是心理?" 答 "心灵 (按官网+9 条内部 doc, 但 5/19 录音有 1 处误)" | 4 来源真整合证据 |

---

## 10 · 总评

V2.2 7/7 是"字符串测试", 不是"信息架构测试". V2.3 真测试 = "AI 能不能自己发现并解决同音字问题".

按本设计 V2.3 落地后:
- 4 来源真按特质分通道
- 信息商 1.0 → 2.0 升级
- 14 张空管道 5 张真用上
- 用户感受到 "AI 在帮我澄清错处" 的真实体验
- Karpathy §1 三层架构 + §3 eval 对象升级到用户感知层

---

**Author**: B AI · 2026-05-22 · 触发 "心灵/心理魔法学院" 案
**附**: V2.2 大成 7/7 测对了机器层, 漏了语义层. V2.3 第 1 件事 = 同音字撞出来. 等顾源源 + A review.
