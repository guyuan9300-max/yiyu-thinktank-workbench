# Milestone Audit · Phase 2 高把握度批量推进

> 时间: 2026-05-22 (晚)
> 范围: F2.2 + F2.4 + F2.6 + F2.7 + F2.8 + 5 件事自主执行 + Phase 2 起步
> 跑法: 对照 V2.2_NORTH_STAR.md 三北极星 + 整体规划位置, 不只看代码

---

## 1 · 本轮里程碑做了什么 (5 个 commit)

| commit | 内容 | 行数 | 测试 |
|---|---|---|---|
| `e225e9b` | Phase 2 起步 5 件事 (IngestPipeline + 信息商 + 渠道驱动 + ai_episode_log 封装 + ai_improvement_suggestions) | +1225 | 30 |
| `c87c62d` | F2.2 + F2.6: key_decisions + org_events + event_line_state_changes 复合事件容器 | +652 | 16 |
| `0da61ee` | F2.8 + N3 A6: IdempotencyStore 防 AI retry 重复创建 | +617 | 17 |
| `4d1ccda` | F2.7 + N3 A3: ReasoningTraceStore AI 推理链路全记录 | +642 | 14 |
| **合计** | | **+3136 行 代码** | **77 新测试** |

加上前一段本 session (F1.7/F1.8/F1.9/F2.0/ClientFactBadge) 累计 13 个 commit。

---

## 2 · 三北极星对照

### N1 · 功能顺畅

| 维度 | 现状 | 本轮进展 |
|---|---|---|
| 跨 view 数据一致性 | ClientFactProvider 已就位 | 没新接入 view (推 v2.3) |
| v1.0 客户 bug #1 (frozen) | F1.7 已修 | 持平 |
| 9 大模块功能完整 | 全在 | 未破坏 (123 测试全过, 0 新增 pre-existing failure) |

**N1 推进度**: 持平 (本轮主要打地基, 不直接破/修功能)

### N2 · 4 主路径接通 + 数据中心理解信息源

| 维度 | 现状 | 本轮进展 |
|---|---|---|
| 4 路径统一通道 | F2.4 IngestPipeline 工具就位 (含 4 路径 normalizer) | ★ 接入散落入库待 F2.4 下一步 |
| 5 维元数据 schema | F1.8/F1.9 + F2.2/F2.6 + F2.7 全字段就位 | ★★★ schema 层基本完整: atomic_facts 17 维 / key_decisions / org_events / event_line_state_changes / reasoning_traces |
| 信息商 (conflict vs 更新 vs 互补) | F2.4 detect_update_relation 函数 + atomic_facts.update_relation 字段 | ★★ 顾源源原案例 "300 万改 800 万重签" 端到端测试通过 |
| 渠道驱动 content_role | F2.4 default_role_for_source 14 类映射表 | ★ 已落地 (合同→fact, 纪要→decision, 复盘→lesson) |
| 机器人答题能力 | ClientFactBadge 雏形, 实际答题没新 view 接入 | ⚠️ B 门进展有限 |

**N2 推进度**: 大幅进步 (schema 层基本完成 N2 表达能力), 但**实际数据流通入库还没接 main.py**, 用户端感知 0。这是下个 critical step。

### N3 · 3.0 接入预留

| 维度 | 现状 | 本轮进展 |
|---|---|---|
| A1 actor_type/actor_id | atomic_facts + event_log + key_decisions + org_events + event_line_state_changes + reasoning_traces + idempotency_keys + ai_episode_log + ai_improvement_suggestions 全部带 | ★★★ 7+ 张表都贯彻 (3.0 AI 写任何东西都能区分 human/ai_agent) |
| A2 event_log 总线 | F1.9 已建 + IngestPipeline 自动写 | ★ |
| A3 reasoning_trace | F2.7 reasoning_traces 表完整 + Store 工具 | ★★★ 新增, 3.0 fact graph 因果链就绪 |
| A4 verification_status | F1.8 已加 | 持平 |
| A5 AI Memory 5 表 | F2.0 占位 + ai_improvement_suggestions 第 6 张表 (双层澄清) | ★ |
| A6 idempotency | F2.8 idempotency_keys + Store 工具 | ★★★ 新增, 防 AI retry 重复创建 |
| 命名锁定 | source_type 14 类枚举 / content_role 10 类 / actor_type 3 类 | ★★ 大部分锁定 |

**N3 推进度**: **接近完成 (90%)**. 剩 idempotency middleware 全局接入 + reasoning_traces 实际填入 (依赖 F2.1 LLM extractor).

---

## 3 · 把握度判断 — 为什么本轮停在这里

按 NORTH_STAR §2 自主边界规则:

| 任务 | 把握 | 决策 |
|---|---|---|
| F2.4 IngestPipeline 接入 main.py 散落入库 | 65% | **停** — 需要顾源源决定哪些 endpoint 优先接, 改 main.py 风险中 |
| F2.1 LLM ExtractionRunner | 60% | **停** — 顾源源 5/22 明确说 prompt 工程是他的活 |
| F2.5 朋友式 clarification | 60% | **停** — 需要顾源源给"朋友式 vs 问卷式"3-5 个对比样本 |
| F2.3 v2_documents trigger | 依赖 F2.1 | **停** |

剩下都 < 70% 把握 且 不澄清完不成北极星, 按规则停下来等顾源源决策。

---

## 4 · 自主决策记录 (本轮)

| 决策 | 把握 | 理由 |
|---|---|---|
| F2.8 降级为 schema + Store 工具 (不做全局 middleware) | 80% | streaming response 跟 idempotency 缓存冲突, 风险中, 渐进改造更稳 |
| reasoning_traces.prompt_summary 限 500 字 (不存全 prompt) | 90% | 通过 prompt_log_id 关联 llm_context.prompt_log, 避免重复存储 |
| AI Memory 实际写入只 ai_episode_log 一张 (其他 5 张占位) | 90% | 顾源源 5/22 决策 — 字段已稳定 ≠ 写入逻辑成本 |
| reasoning_traces 用 list[str] reasoning_steps (不是结构化 chain) | 85% | LLM 自描述比结构化模板更自然, 3.0 学起来更准 |

---

## 5 · 等顾源源拍板的事

按 V2.2_PHASE2_KICKOFF.md §5 + 5/22 后续对话, **4 个关键决策点都已有答案**, 但还有 3 个新决策点需要拍板才能继续:

| 新决策点 | 上下文 |
|---|---|
| **D1: F2.4 接入哪些 endpoint?** | main.py 现有散落入库代码: smart_file_import / knowledge_v2 / internet_crawler / wechat_sogou — 优先接哪 1 个验证? 顾源源建议 Path B 客户价值驱动, 那可能是 smart_file_import 因为 5/19 docx 用这个入 |
| **D2: F2.1 prompt 样本** | 顾源源 5/22 说"prompt 工程是他的活", 需要给 5/19 张真会议 docx 的 4-6 个抽取案例 (跟 V2.2_INFORMATION_SOURCE_METADATA.md §1 同模板) |
| **D3: F2.5 朋友式问法样本** | 顾源源 5/22 说豆包不算最好样本, 需要 3-5 个"AI 已看资料 → 反问用户" 的正面样本 |

---

## 6 · 校验门状态 (本轮)

### 门 A (N1 功能不掉链)
- ✅ TS 编译 0 错误 (上次 8ac7531 已验)
- ✅ v22 系列 123 测试全过
- ✅ pre-existing 26 失败稳定 (没新增)

### 门 B (N2 4 主路径 + 机器人能力)
- ✅ 4 路径 normalizer + 信息商 + 渠道驱动 全 schema/工具就位
- ⚠️ 实际数据流通入库 main.py 还没接, 用户端机器人答题能力**没真实进步**
- 🟡 B 门连续 2 个 milestone "schema 就位但没接入" — 触发 NORTH_STAR §8 预警, **必须下一里程碑直接推进**

### 门 C (N3 3.0 接入预留)
- ✅ A1 actor_type 7+ 表贯彻
- ✅ A2 event_log 总线 + IngestPipeline 自动写
- ✅ A3 reasoning_traces 表 + Store 工具 (新增)
- ✅ A4 verification_status atomic_facts 字段
- ✅ A5 AI Memory 6 表 (5 占位 + ai_improvement_suggestions)
- ✅ A6 idempotency_keys + Store 工具 (新增)
- 🟡 命名锁定: source_type/content_role/actor_type 全枚举, 但 content/body 还没统一

**N3 推进度: ~90% 完成**. 这是本轮最大的进步.

---

## 7 · 客户价值评估 (顾源源 5/22 原则: 关注用户感知)

诚实评估本轮新增的客户感知:

| 变化 | 客户能感知? |
|---|---|
| IngestPipeline schema + 工具 | ❌ 还没接入实际入库 |
| 复合事件容器 (key_decisions/org_events) | ❌ 等 F2.1 LLM 抽出来才有数据 |
| reasoning_traces | ❌ 等 F2.1 LLM 写入才有 |
| idempotency 防 AI retry | ❌ 3.0 才用到 |
| 信息商 (重签语义识别) | ❌ 等接入实际入库才能跑 |
| AI Memory 6 表 | ❌ 3.0 才读 |

**客户价值评估**: 本轮 0 新增客户可感知变化。**全部是基础设施**。

这意味着下个里程碑必须直接推进 "用户能感知到变化" 的工作 (B 门要求), 否则 NORTH_STAR §8 触发 "重新评估方向" 警报.

---

## 8 · 下一个里程碑必须做什么 (强制建议)

不能再做基础设施了, **下一里程碑必须有 1 个用户可感知的进步**。候选:

### 方案 A: F2.4 接入 smart_file_import (用户可感知 ★★★)

把 SmartFileImport 现有的 INSERT INTO atomic_facts 切到 IngestPipeline.ingest()。
完成后用户上传一份 docx, 立即在 atomic_facts 表里能看到带完整 5 维元数据 + reasoning_trace + idempotency-safe 的事实记录。

把握度: 70% (需要小心 main.py 改造不引入 regression)
工作量: 2-3 天

### 方案 B: F2.1 LLM ExtractionRunner 跑通 1 个真实样本

跟顾源源对 prompt 设计 1-2 小时, 然后用 5/19 张真会议 docx 跑一次抽取, 把抽出来的事实写进 atomic_facts。
完成后机器人就能答 "5/19 那场会有什么决定" → 直接推进 B 门到 M2 level。

把握度: 60% (需顾源源参与, 但价值最高)
工作量: 1 天 (顾源源 1 小时 + 我 5-6 小时)

**推荐方案 B**, 因为对 N2 (机器人能力 + 软件灵魂) 推进最直接。但需要顾源源给 1-2 小时对 prompt。

---

## 9 · 本 session 整体收尾

本 session (2026-05-22) 累计:
- **13 个 clean commit** (本轮 4 个 + 前段 9 个)
- **123 个新测试全过**
- **3500+ 行新增代码**
- **3 个北极星全部推进**, 其中 N3 接近完成 (90%)
- **Phase 2 schema 层基本就位** (8 张新表 / 5 个 Store 工具函数 / 5 维元数据完整)

**v2.2 整体进度估算**: 工程层 ~45-50% / 客户感知层 ~10%

下个 session 必须有用户可感知进步, 否则 §8 触发。
