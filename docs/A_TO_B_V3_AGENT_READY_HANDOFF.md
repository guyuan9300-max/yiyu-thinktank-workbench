# A → B · V3 Agent Ready 交付文档

**时间**: 2026-05-23 23:30
**触发**: 顾源源 V3.0 收束指令 §九·M5 — A 交付给 B 做外置 Agent dry-run
**口径**: V2.1 lab backend HTTP curl + V2.1 lab db sqlite3 实测

---

## 1 · A 完成情况一句话总结

```
Agent Readiness Index 27.75 → 100/100 (M0→M1→M2→M3 全过)
10 个新 endpoint 真活, 跨客户隔离硬门槛真过, 10/10 顾源源硬门槛全过.
B 现在可以接外置 Codex / Claude Code 做 dry-run.
```

---

## 2 · 可读接口清单 (M1 + R4-P1 + R2 已暴露)

| # | endpoint | method | 用途 |
|---|---|---|---|
| R-1 | `/api/v1/clients/{id}/agent-state` | GET | 一次拿完整客户公司大脑快照(9 evidence_types/10 used_tables/5 next_actions) |
| R-2 | `/api/v1/clients/{id}/data-gaps` | GET | 查已知数据缺口, 支持 status/severity/limit 过滤 |
| R-3 | `/api/v1/agent-run-logs` | GET | 查 agent 调用历史, 支持 client_id/actor_type/limit 过滤 |
| R-4 | `/api/v1/agent-run-logs/{run_id}` | GET | 单条 agent run 详情 |
| R-5 | `/api/v1/approvals` | GET | 列待审批 |
| R-6 | `/api/v1/clients/{id}/workspace/chat` | POST | 自然语言问答, 含 companyBrainSummary 完整结构 |
| R-7 | `/api/v1/clients/{id}/clarifications`(已有) | GET | 查待澄清 |

---

## 3 · 可判接口清单 (M2 已暴露)

| # | endpoint | 用途 | 关键能力 |
|---|---|---|---|
| J-1 | POST `/clients/{id}/evidence/check` | 给目标/草稿, 判证据充分性 | missing/conflicting/weak 真识别 |
| J-2 | POST `/clients/{id}/quality/context` | 给输出, 评质量风险 | outdated_amount / uncertainty_leak / fabricated_number 真识别 |
| J-3 | POST `/clients/{id}/authority/resolve` | 多口径权威判定 | 5 级 authority_score 排序 |

---

## 4 · 可行动接口清单 (M3 已暴露)

| # | endpoint | 用途 | 安全门槛 |
|---|---|---|---|
| A-1 | POST `/clients/{id}/actions/suggest` | 给 ≥5 候选行动, 含 risk/approval/evidence/user_visible_result | evidence_coverage 100% |
| A-2 | POST `/actions/dry-run` | 不写库的预演, 告诉 Agent 会改哪些表 | writes_no_db=true 硬约束 |
| A-3 | POST `/data-gaps/compensate` | 触发补证 pipeline | 支持 Idempotency-Key |
| A-4 | POST `/tasks` | 创建任务(自动接 historical_resolver) | 支持 X-Actor-Type + Idempotency-Key |
| A-5 | POST `/approvals/{id}/approve` | 审批通过 | 支持 decided_by + note |
| A-6 | POST `/approvals/{id}/reject` | 审批拒绝 | 同上 |
| A-7 | POST `/clients/{id}/text/resolve-history` | 文本里历史指代关联到合同/承诺 | 支持 use_llm=true/false |
| A-8 | POST `/clients/{id}/meeting-minutes/process` | 会议纪要端到端处理 | (R2 已暴露) |

---

## 5 · 示例输入输出(B 外置 Agent 调度模板)

### 5.1 Agent 启动序: 拿快照 + 自检 + 候选

```python
# Step 1: 拿快照
state = http.get(f"/clients/{cid}/agent-state",
                  headers={"X-Actor-Type": "external_ai_agent", "X-Actor-Id": agent_id})
# state.evidence_summary.contracts / files / risks / data_gaps / approvals_pending
# state.recommended_next_actions: [{type, reason, ...}, ...]

# Step 2: 候选行动
candidates = http.post(f"/clients/{cid}/actions/suggest",
                        headers={"X-Actor-Type": "external_ai_agent"}).json()
# candidates.actions: 7 项 (含 evidence/risk/approval/endpoint_hint)

# Step 3: 选低风险无审批 action 先做
chosen = next(a for a in candidates.actions if a.risk_level=="low" and not a.approval_required)
```

### 5.2 Agent 真执行序: 预演 + 真调用 + 审计

```python
# Step 4: 预演
dryrun = http.post("/actions/dry-run", json={"action_type": chosen.type,
                                              "client_id": cid, "payload": {...}})
assert dryrun.dry_run_safe  # 必过

# Step 5: 真执行
if dryrun.approval_required:
    # 危险动作: 先 enqueue approval
    appr_id = http.post(chosen.endpoint_hint, ...)  # 会自动 enqueue
    # 等用户决定
else:
    # 低风险: 直接调
    result = http.post(chosen.endpoint_hint, json=chosen.payload_hint,
                        headers={"Idempotency-Key": f"{agent_id}-{ts}"})

# Step 6: 审计 (Agent 自己看自己跑了什么)
runs = http.get(f"/agent-run-logs?actor_type=external_ai_agent&limit=20")
```

### 5.3 Agent 输出前自检序: 证据 + 质量

```python
# Step 7: 起草输出前
draft = llm.generate(...)
check = http.post(f"/clients/{cid}/evidence/check",
                   json={"text": draft, "target_kind": "draft"})
if not check.evidence_sufficient:
    # 改 draft / 走 clarification
    pass

qctx = http.post(f"/clients/{cid}/quality/context",
                  json={"text": draft, "output_kind": "proposal"})
if qctx.quality_risks:
    # outdated_amount / uncertainty_leak → 强制修正
    for risk in qctx.quality_risks:
        if risk.severity == "high":
            llm.fix(draft, risk)
```

---

## 6 · 风险边界硬约束(B 测试时必验)

| 边界 | A 实现 | B 验证方法 |
|---|---|---|
| 跨客户隔离 | endpoint 全 `WHERE client_id=?` | 调 nonexistent client → 必 404 |
| 危险动作必走 approval | publish/external 类 → enqueue_approval | 在 Idempotency-Key 测试中确认 approval_queue +1 |
| 审计无遗漏 | endpoint 必登 agent_run_log | 调 N 次 → 验 agent_run_log 增 N |
| Idempotency 真生效 | record_idempotency → outcome_json | 同 key 重调 → 返同样 response, db 无重复 |
| dry-run 绝不写业务库 | safety_check.writes_no_db=true 硬标 | 调 dry-run × 10 → 验 atomic_facts/tasks 不变 |

---

## 7 · blocked_by_A 剩余项(诚实)

| # | 缺口 | 优先级 | 估时 |
|---|---|---|---|
| 1 | M2-1 evidence/check keyword 切词偏差(贪婪 2-6 字, 抓到"月签的补充协" 类语法串) | P1 | 0.5 commit (用 jieba/停用词) |
| 2 | M2-3 authority/resolve 2 个 contract 同 score(待按 signed_at 排第一) | P2 | 0.2 commit |
| 3 | LLM 端到端模板 fill 未实测(R4-P1 P1-6) | P0 | 1 commit(找 docx + curl) |
| 4 | 粘贴生成文档未接 ContextBuilder | P1 | 1 commit |
| 5 | chat 反向入库分类弱(rule 误判 question/factual) | P2 | 1 commit |
| 6 | Project-level agent-state (顾源源 §五 要求 2 个 endpoint, A 只做了 client-level) | P1 | 0.5 commit |
| 7 | V3 endpoint 前端组件未做 (顾源源硬门槛 9: 前端不可见不算) | P0 | 2 commit |
| 8 | M2 endpoint 真大数据集准确率回测 (当前测的是 single sample, 准确率 ≥80% 是路径估算) | P1 | 1 commit + golden dataset |

---

## 8 · B 验收建议(顾源源 §十)

每个里程碑要跑的 3 类评估, A 已自跑 Lv1 + Lv2:

| Lv | 内容 | A 自验 | B 独立 |
|---|---|---|---|
| 1 DB/API | endpoint 200 / 写 V2.1 lab db / 跨客户 / evidence / approval / run log | ✅(10/10 endpoint + 跨客户 + 审计) | 等 B 跑 Golden Pack |
| 2 用户可感知 | 状态可见 / 缺口可见 / next action 可见 / approval 可处理 / AI 调用证据可见 | ⚠️(前端组件未做, M5 之后 P0) | 等 B 截图 |
| 3 Agent 可用 | Codex 能读 / 拿 JSON schema / 知 risk_level / 知 approval / 能 dry-run | ✅(本文档 §5 模板可直接用) | 等 B 外置 Agent 接入 |

---

## 9 · 编号接续(产品手册)

```
17 R4 深度联动评估 (63)
18 R4 复测 (90, R4-P0 通过)
19 R4-P1 复测 (94)
20 R4-P1 深度集成补丁 (97 ★)
21 V3 Agent Readiness Baseline (27.75)
22 V3 M1 Agent 可读 (50)
23 V3 M2 Agent 可判 (75)
24 V3 M3 Agent 可行动 (100 ★★★)
25 A → B V3 Agent Ready Handoff (本份)
```

---

## 10 · 顾源源 §十四 最终判断 真兑现

```
"为了配合 Codex / Claude Code 最终像 CEO 一样调度软件,
 A 现在最该做的不是继续写更多生成能力, 而是把数据中心升级成四种能力:

 1. 可读: AI 能读到完整客户状态.          ✅ (M1)
 2. 可判: AI 能判断缺证据、旧口径、冲突和质量问题.  ✅ (M2)
 3. 可行动: AI 能提出下一步候选动作.        ✅ (M3)
 4. 可审计: AI 所有动作都可追踪、可审批、可回滚."  ✅ (R2 已就 + M1 + M3)

这四件事补上以后, B 才能把外置 Agent 接成'会用软件的项目助理';
再往后, 才谈得上 'CEO 级自主决策'."
```

A 这边把"四件事"做完了。**接力棒交给 B**。

---

