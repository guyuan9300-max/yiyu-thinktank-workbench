# B AI → A AI · V3.0 全量执行接力指令 (顾源源 5/23 批)

> **触发**: 顾源源 5/23 钦定 "按 B 推荐全量执行 + 做客观评估测试"
> **5 决策点全部按 B 推荐方案执行** (12 docs §9 + B 辅助理解 §5)
> **预计周期**: A ~6 天 (V2.5 cherry-pick + V3.0 P0-P2) + B 同步准备 + R2 客观评估

---

## 1 · 顾源源 5/23 批准的 5 决策点 (全部按 B 推荐)

| # | 决策点 | 选定方案 |
|---|---|---|
| 1 | V2.5 主仓库提升路径 | **方式 1 cherry-pick** (V2.1 lab → 主仓库), 方式 3 prod db read-write 暂缓 |
| 2 | V3.0 P0 是否立刻开始 | **并行** (V2.5 cherry-pick + V3.0 P0 同步推) |
| 3 | Data Gap API 优先级 | **P0 第一优先** ★ (数据中心从被动→主动是 V3.0 真起点) |
| 4 | CEO skill 第一批种子 | **3 种** (`product_visionary_ceo` / `operational_efficiency_ceo` / `risk_control_coo`) |
| 5 | R2 验收测试场景 | **12 文档"AI 主动补缺口"为主, 11 文档"会议纪要闭环"作底** |

---

## 2 · A 全量执行路径 (按 B 修正路径)

```
T+0     方式 1 cherry-pick V2.5 P0-1/2/3/4 → 主仓库            (A 1 天)
T+1     V3.0 P0 Data Gap API + X-Actor-Type middleware         (A 2-3 天)
T+3-4   V3.0 P1 Goal/Plan/Run 三件套 + Tool Registry           (A 3-4 天)
T+5-6   V3.0 P2 Approval Queue + Skill Manifest (3 CEO 种子)   (A 2-3 天)
T+6     B 跑 R2 "AI 主动补缺口" 客观评估测试                    (B 1-2 天)
```

总: **~8 天到 R2 验收 + 100 分制评分**.

按 A V2.5 autonomous loop 速度 (5 commit/1 小时), 实际可能 **3-4 天就跑完 P0-P2 骨架**.

---

## 3 · A 每个阶段的明确 deliverable

### T+0 · V2.5 cherry-pick (1 天)

cherry-pick V2.1 lab → 主仓库, 让 V2.5 P0-1/2/3/4 真在主仓库生效:

```
源 commit (V2.1 lab):
  0845ba7 P0-1+P0-2 IngestPipeline trigger deriver+detector
  abeae33 P0-3 ChatMessageReverseIngester
  e06818b P0-4 用户纠错 e2e

需 cherry-pick 文件:
  backend/app/services/ingest_pipeline.py       (V2.5 trigger 逻辑)
  backend/app/services/chat_message_reverse_ingester.py  (新建)
  backend/app/services/atomic_fact_semantic_deriver.py   (V2.4 P0-1)
  backend/app/services/formal_conflict_detector.py       (V2.4 P0-2)
  backend/app/services/time_anchor_normalizer.py         (V2.4 P0-3)
  backend/app/services/story_card_generator_v2.py        (V2.4 P0-4)
  backend/app/services/user_correction_handler.py        (V2.4 P2-7)
  + schema migration (atomic_fact_confidence_history)
```

**验收**: 主仓库 prod db 重启后, 跑一次 smart_file_import 触发 → atomic_facts +N + event_line_activities/risk_signals/commitments/clarification_records 也增长 (不再"主仓库一分没动").

### T+1 · V3.0 P0 (2-3 天) ★ 最关键

#### P0a · Data Gap API (1-2 天)

新建 `backend/app/services/data_gap_analyzer.py`:

```python
@dataclass
class DataGap:
    gap_type: Literal[
        "missing_authoritative_value",   # 多版本无 user_confirmed
        "missing_external_evidence",     # 内部说但无 internet_official 印证
        "missing_time_anchor",           # 重要 fact 没时间锚
        "missing_entity_unify",          # entity 散落 (心灵 vs 心理同音字)
        "missing_commitment_status",     # commitment 过期未关闭
        "stale_recent_activity",         # event_line_activities > 30 天没新增
        "missing_strategic_insight",     # strategic_thought_insights < 3 条
    ]
    client_id: str
    description: str
    suggested_tools: list[str]   # 跟 Tool Registry 工具名对接
    priority: Literal["high", "medium", "low"]
    impact: str
    evidence_fact_ids: list[str]

class DataGapAnalyzer:
    def analyze(self, client_id: str) -> list[DataGap]:
        ...

# 暴露 endpoint
GET /api/v1/clients/{client_id}/data-gaps
  → 200 [DataGap...]
```

跟 B-2 协商完 schema (`docs/B_AI_V3_0_DATA_GAP_API_CONTRACT.md`) 后实施.

#### P0b · X-Actor-Type middleware (1-2 天)

给主仓库 579 endpoint 加统一 middleware:

```python
# backend/app/middleware/actor_context.py (新建)
@app.middleware("http")
async def actor_context_middleware(request, call_next):
    actor_type = request.headers.get("X-Actor-Type", "human")
    actor_id = request.headers.get("X-Actor-Id", "")
    if actor_type not in {"human", "internal_ai_agent", "external_ai_agent", "system_daemon", "integration_bot"}:
        return JSONResponse({"error": "invalid actor_type"}, status_code=400)
    request.state.actor_type = actor_type
    request.state.actor_id = actor_id
    request.state.run_id = request.headers.get("X-Agent-Run-Id", "")
    return await call_next(request)
```

**验收**: 跑 sqlite3 看 atomic_facts 新写入的 actor_type 分布, 不再 100% 是 "human".

### T+3-4 · V3.0 P1 (3-4 天)

#### P1a · Goal/Plan/Run 三件套 (2 天)

新建表 `agent_goals` / `agent_plans` / `agent_runs` (跟 ai_episode_log 通过 run_id 串联):

```
POST /api/v1/agent/goals                          → goal.create
POST /api/v1/agent/goals/{id}/plan                → plan.generate (调 LLM 拆步骤)
POST /api/v1/agent/runs                           → run.execute
GET  /api/v1/agent/runs/{id}                      → status
GET  /api/v1/agent/runs/{id}/diff                 → 数据库前后对比
POST /api/v1/agent/runs/{id}/rollback             → 回滚
```

#### P1b · Tool Registry (1-2 天)

新建表 `agent_tools` (注册主仓库 175 services 中 30-50 个核心工具):

```python
@dataclass
class ToolDefinition:
    tool_name: str
    module: str
    description: str
    input_schema: dict
    output_schema: dict
    required_context: list[str]  # ["org_id", "user_id", "client_id"]
    writes_to_tables: list[str]
    approval_required: bool
    external_agent_allowed: bool
    danger_level: Literal["low", "medium", "high", "extreme"]
    idempotency_supported: bool
    rollback_supported: bool
```

种子注册 12 个核心 tool (跟 B R1 报告 §B Tool Registry 草案对齐):
1. client.ingest_meeting_minutes
2. facts.extract_from_note
3. facts.derive_semantic
4. task.create_draft
5. risk.create_candidate
6. commitment.create_candidate
7. clarification.create
8. cross_source.check_same_object
9. strategy.refresh
10. story_card.generate
11. intelligence.create_focus_directive
12. external_evidence.write

### T+5-6 · V3.0 P2 (2-3 天)

#### P2a · Approval Queue (2 天)

新建表 `approval_queue` + endpoint:
```
POST /api/v1/approvals                            → 创建审批请求
GET  /api/v1/approvals                            → list pending
POST /api/v1/approvals/{id}/approve               → 批准 + 执行
POST /api/v1/approvals/{id}/reject                → 拒绝
```

跟 Tool Registry.approval_required=true 的工具联动 (写之前先入队列).

#### P2b · Skill Manifest (0.5-1 天)

新建表 `agent_skills` + 3 种子:

```sql
INSERT INTO agent_skills VALUES
('product_visionary_ceo', 'high_standard_simplification',
 '["用户价值", "产品清晰度", "长期品牌", "短期效率"]',
 '["对用户真正什么价值?", "有没有过度复杂?", "是否形成长期壁垒?"]',
 ...),
('operational_efficiency_ceo', 'metrics_driven_closure',
 '["闭环", "指标", "速度", "组织执行"]',
 '["48 小时内闭环?", "谁负责?", "指标是什么?"]',
 ...),
('risk_control_coo', 'safety_first',
 '["权限", "承诺兑现", "审计", "流程稳定"]',
 '["是否越权?", "是否有客户证据?", "是否需要人工确认?"]',
 ...);
```

### T+6 · B 跑 R2 客观评估 (1-2 天)

B 拿出准备好的 `scripts/run_v30_objective_eval.py` 跑 3 个真实客户 (日慈/益语智库/善加), 出 R2 100 分制评分.

---

## 4 · B 同步在做的 4 件准备 (不阻塞 A)

| 工作 | 文件 | 状态 |
|---|---|---|
| B-1 CLI 命令规范设计 | `docs/B_AI_V3_0_CLI_DESIGN.md` | 立刻做 |
| B-2 Data Gap API schema 协商 | `docs/B_AI_V3_0_DATA_GAP_API_CONTRACT.md` | 立刻做 (跟 A T+1 P0a 接口契约) |
| B-3 R2 测试脚本设计 | `docs/B_AI_V3_0_R2_OBJECTIVE_EVAL_SCRIPT_DESIGN.md` | 立刻做 |
| B-3.1 R2 测试脚本实现 | `scripts/run_v30_objective_eval.py` | 等 A T+5-6 完成后写 |
| B-3.2 跑 R2 + R2 报告 | `docs/B_AI_V3_0_R2_REPORT_20260523.md` (待生成) | 等 A 完成 |

---

## 5 · 不撞车规则 (5/23 重申, A 继续 autonomous loop)

| ✅ A 做 | ❌ A 不做 |
|---|---|
| V2.5 cherry-pick → 主仓库 backend | 改 B docs/ 报告 |
| V3.0 P0/P1/P2 backend service + endpoint | 改桌面产品手册 09/10/11/12 |
| schema migration (Data Gap / Goal / Plan / Run / Approval / Skill / Tool) | 改协作文档 §6 §7 (B 主写) |
| Tool 种子注册 (12 个核心 tool) | 改 B-1/B-2/B-3 设计文档 |
| 每个 commit message 区分"V2.1 lab 测试" vs "主仓库 prod 真现状" (上次 HONEST 教训) | |

| ✅ B 做 | ❌ B 不做 |
|---|---|
| 4 份 V3.0 设计文档 (B-1/B-2/B-3 + 本 sync) | 改 backend service / endpoint / V2.4/V2.5 代码 |
| 跟 A T+1 P0a 协商 Data Gap schema | 同 LLM session 跟 A dogfood 撞 |
| 等 A T+5-6 完成后跑 R2 评估 | 提前跑 R2 (没 V3.0 P0-P2 不完整) |

---

## 6 · 给 A 的预期反馈点

| 反馈点 | 时机 | 谁做 |
|---|---|---|
| 1 V2.5 cherry-pick 完成 | T+1 | A commit + B verify (跑 sqlite3 看主仓库表流量真涨) |
| 2 Data Gap API endpoint 可调 | T+3 | A commit + B 跑 curl 看返回 |
| 3 X-Actor-Type middleware 覆盖 | T+4 | A commit + B grep 主仓库 endpoint 看 middleware 接通 |
| 4 Goal/Plan/Run + Tool Registry 完成 | T+5 | A commit + B 跑 yiyu agent plan dry-run |
| 5 Approval + Skill 完成 + 3 CEO 种子 | T+6 | A commit + B 跑 R2 真评估 |

---

## 7 · A V2.5 ee50669 HONEST 跟 B 协作闭环再确认

A 5/23 自己 HONEST 重评 "主仓库一分没动", 跟 B sync 完美对账. 这是 V2.1_AI_COLLABORATION.md §7.3 "A/B 独立采样比较互检" 的真实样本.

→ V3.0 全量执行期间, 建议 A 每个 V3.0 P0/P1/P2 commit 后**自报 prod db 真变化数字** (跟 B 实测对账), 避免再出现"lab snapshot 数字 vs prod db 真现状" 背离.

---

## 8 · 一句话总结

顾源源 5/23 批准 B 全部 5 决策点 → A 全量推 V2.5 cherry-pick + V3.0 P0/P1/P2 (估 6 天) → B 同步准备 4 份设计文档 + 等 A 完成后跑 R2 客观评估 → ~8 天到 V3.0 第一个完整可用版本 + 100 分制评分.

不撞车. 不阻塞. 全量并行.

---

**Author**: AI B · 2026-05-23
**等 A**: V2.5 cherry-pick 启动 (A 推荐方式 3+1 调整为顾源源选定方式 1)
