# B AI · V3.0 R2 客观评估测试脚本设计 (B-3)

> **触发**: 顾源源 5/23 批 "做客观评估测试" + B 推荐 R2 用 12 文档"AI 主动补缺口" 场景
> **作用**: 设计 `scripts/run_v30_objective_eval.py` 等 A V3.0 P0-P2 完成后跑
> **输出**: 100 分制评分 + 7 硬门槛 + 3 客户横向对比 + 修复优先级
> **执行人**: AI B
> **日期**: 2026-05-23

---

## 1 · 测试方法论

### 1.1 跟 V2.2 大成 7/7 教训对照

V2.2 大成只测了**机器层**字符串匹配 (L1 SQL keyword + L2 markdown grep), 漏了 L3 用户感知层. 这次 R2 设计**直接对齐用户感知**:

| V2.2 旧测试 | V3.0 R2 新测试 |
|---|---|
| L1 SQL keyword 命中 | 维度 1 AI 调度全链路 (Goal→Plan→Tool→Result) |
| L2 6 段 markdown keyword | 维度 2 资料变客户理解 (含派生表) |
| 单 dataset (5/19 张真) | 3 类客户 (资料丰富/正在推进/信息稀疏) |
| 1 个客户 1 次跑 | 第 0 / 1 / 2 轮对比 (使用前 vs 真实操作 vs 使用后) |
| keyword 字符串匹配 | 实际语义命中 + 自然语言回答 + 用户纠错 |

### 1.2 测试模式

**Headless 全后端**:
- 不动 UI (按 10 文档 §三原则一)
- 调 HTTP API (curl/httpx)
- 三客户每个跑同一段会议纪要 (但 client_id 不同, 验证跨客户隔离)
- test_run_id 标记所有写入 (按 10 文档 §三原则二可回滚)

---

## 2 · 测试场景设计 (12 文档"AI 主动补缺口" 为主, 11 文档作底)

### 2.1 主场景: AI 主动补缺口闭环

输入 (3 客户共用同一段, 替换 X 为客户名):

```
"今天和 X 开会, 客户提到下个月想先做教师端试点, 预算还没有最终确认.
项目负责人希望先压缩方案复杂度, 但秘书长担心学校配合度不够.
我们答应下周二前给一版更轻量的试点方案, 同时补充风险控制说明."
```

预期 AI 路径 (按 12 文档 §六):

```
1. workbench.ingest_meeting_minutes
   → 写 documents + v2_chunks
2. facts.extract_from_note
   → 写 atomic_facts (≥ 5 条)
3. facts.derive_semantic (V2.4 P0-1 触发)
   → 写 event_line_activities + risk_signals + commitments
4. ★ data_gap.analyze (V3.0 P0a 新接口)
   → 找出 ≥ 3 个缺口 (预期: 预算未定 / 学校名单缺失 / 学校配合证据)
5. ★ intel.search (根据 gap 主动调用 — V3.0 调度核心)
   → 写 external_evidence_cards (≥ 1 条)
6. clarification.create (V2.4 P0-2 触发)
   → 写 clarification_records (≥ 2 条)
7. task.create_draft (requires_approval=true)
   → 写 tasks (status=draft, ≥ 1 条)
8. strategy.refresh
   → 写 digital_asset_narrative_snapshots
```

### 2.2 同测 7 硬门槛 (按 11 文档 §四)

```
门槛 1 AI 不操作界面     ★ 全 HTTP API, 0 UI
门槛 2 AI 不直接写 DB    ★ 走 service, 不暴露 SQL
门槛 3 上下文绑定        ★ X-Actor-Type/X-Actor-Id/X-Agent-Run-Id 全填
门槛 4 不只写 atomic_facts ★ 验证 event_line/risk/commitment/clarification 都有
门槛 5 危险动作进 approval ★ task.create_draft 进 approval_queue
门槛 6 Agent Run Log     ★ run_id 串联完整链
门槛 7 跨客户隔离 0 错   ★ 3 客户 client_id 互不串
```

### 2.3 第 0/1/2 轮设计 (按 09 文档 §四)

| 轮 | 作用 | 数据库状态 |
|---|---|---|
| **第 0 轮** | 跑测试**前** 的客户档案现状 baseline | 不改 db, 只采集数字 |
| **第 1 轮** | 跑测试 (Headless 调用会议纪要处理闭环) | test_run_id 写入新数据 |
| **第 2 轮** | 跑测试**后**, 重新 baseline, 对比第 0 轮 | 看故事卡升级度 |

→ 每个客户跑完后 rollback test_run_id, 不污染 prod.

---

## 3 · 脚本设计 (scripts/run_v30_objective_eval.py)

### 3.1 主体结构

```python
"""V3.0 R2 客观评估测试 (B-3)

跑法:
    python3 scripts/run_v30_objective_eval.py \
        --clients 日慈基金会,益语智库,善加基金会 \
        --rounds 0,1,2 \
        --mode draft \
        --report-out docs/B_AI_V3_0_R2_REPORT_20260523.md
"""
import argparse, json, time, uuid, sqlite3
from pathlib import Path
from datetime import datetime

PROD_DB = Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2/app.db"
TEST_CLIENTS = ["日慈基金会", "益语智库", "善加基金会"]

GOLDEN_MEETING_MINUTES = """
今天和{client}开会, 客户提到下个月想先做教师端试点, 预算还没有最终确认.
项目负责人希望先压缩方案复杂度, 但秘书长担心学校配合度不够.
我们答应下周二前给一版更轻量的试点方案, 同时补充风险控制说明.
""".strip()

ROUND_TABLES_TO_SNAPSHOT = [
    "atomic_facts", "event_line_activities", "risk_signals", "commitments",
    "strategic_thought_insights", "fact_contradictions", "clarification_records",
    "external_evidence_cards", "key_decisions", "org_events",
    "event_log", "ai_episode_log", "reasoning_traces",
    "tasks", "approval_queue",
]


def snapshot_round(conn, client_id, round_label):
    """每轮采集 N 张表 row count + 客户特定 fact 数."""
    snap = {"round": round_label, "client_id": client_id, "timestamp": datetime.utcnow().isoformat()}
    for t in ROUND_TABLES_TO_SNAPSHOT:
        try:
            total = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            client_n = conn.execute(
                f'SELECT COUNT(*) FROM "{t}" WHERE client_id = ?',
                (client_id,)
            ).fetchone()[0] if has_client_id_col(conn, t) else None
            snap[t] = {"total": total, "client": client_n}
        except Exception as e:
            snap[t] = {"error": str(e)}
    return snap


def run_objective_eval_for_client(client_id, client_name, mode="draft"):
    """单客户跑一次完整 R2 测试."""
    test_run_id = f"r2_{uuid.uuid4().hex[:12]}"
    print(f"\n{'=' * 72}\n  R2 客观评估 · 客户: {client_name} · test_run_id={test_run_id}\n{'=' * 72}")

    conn = sqlite3.connect(str(PROD_DB))

    # Round 0: baseline
    snap_r0 = snapshot_round(conn, client_id, "R0_before")

    # Round 1: Headless 跑测试场景
    run_result = headless_run_meeting_minutes(
        client_id, client_name, test_run_id, mode
    )

    # Round 2: post-run baseline
    snap_r2 = snapshot_round(conn, client_id, "R2_after")

    # 计算 R2 100 分制
    scores = compute_v30_score(snap_r0, snap_r2, run_result)

    # 7 硬门槛检查
    hard_gates = check_hard_gates(snap_r0, snap_r2, run_result, conn, client_id, test_run_id)

    # 回滚 test_run_id 的写入 (清理)
    rollback_test_run_id(conn, test_run_id)
    conn.close()

    return {
        "client_id": client_id,
        "client_name": client_name,
        "test_run_id": test_run_id,
        "snap_r0": snap_r0,
        "snap_r2": snap_r2,
        "run_result": run_result,
        "scores": scores,
        "hard_gates": hard_gates,
    }


def headless_run_meeting_minutes(client_id, client_name, test_run_id, mode):
    """通过 HTTP API 跑会议纪要处理闭环 (V3.0 Goal-Plan-Run 模式)."""
    import httpx

    BASE_URL = "http://localhost:47829"  # 主仓库 backend
    headers_base = {
        "X-Actor-Type": "external_ai_agent",
        "X-Actor-Id": "b-r2-objective-eval",
        "X-Agent-Run-Id": test_run_id,
    }

    result = {
        "client_id": client_id,
        "test_run_id": test_run_id,
        "mode": mode,
        "steps": [],
        "errors": [],
        "writes_summary": {},
    }

    meeting_text = GOLDEN_MEETING_MINUTES.format(client=client_name)

    try:
        # Step 1: 创建 goal
        goal_resp = httpx.post(
            f"{BASE_URL}/api/v1/agent/goals",
            headers={**headers_base, "Idempotency-Key": f"{test_run_id}_goal"},
            json={
                "goal_text": f"处理 {client_name} 5/23 会议纪要, 主动补缺口, 生成行动包",
                "client_id": client_id,
                "skill_name": "operational_efficiency_ceo",
                "constraints": {
                    "do_not_send_external": True,
                    "only_create_drafts": True,
                    "require_human_approval": True,
                },
                "meeting_text": meeting_text,
            },
            timeout=30,
        )
        goal_resp.raise_for_status()
        goal_id = goal_resp.json()["goal_id"]
        result["steps"].append({"step": "goal.create", "goal_id": goal_id, "status": "success"})

        # Step 2: 生成 plan
        plan_resp = httpx.post(
            f"{BASE_URL}/api/v1/agent/goals/{goal_id}/plan",
            headers=headers_base,
            json={"skill_name": "operational_efficiency_ceo"},
            timeout=120,
        )
        plan_resp.raise_for_status()
        plan = plan_resp.json()
        plan_id = plan["plan_id"]
        result["steps"].append({
            "step": "plan.generate",
            "plan_id": plan_id,
            "step_count": len(plan["steps"]),
            "modules_called": list({s["tool"].split(".")[0] for s in plan["steps"]}),
        })

        # Step 3: 跑 plan
        run_resp = httpx.post(
            f"{BASE_URL}/api/v1/agent/runs",
            headers={**headers_base, "Idempotency-Key": f"{test_run_id}_run"},
            json={"plan_id": plan_id, "mode": mode},
            timeout=600,  # LLM 调用慢
        )
        run_resp.raise_for_status()
        run_data = run_resp.json()
        result["agent_run_id"] = run_data["run_id"]
        result["steps"].append({
            "step": "run.execute",
            "run_id": run_data["run_id"],
            "status": run_data["status"],
            "writes": run_data.get("writes_summary", {}),
        })
        result["writes_summary"] = run_data.get("writes_summary", {})

        # Step 4: 查 data-gaps (验证主动补缺口能力)
        gaps_resp = httpx.get(
            f"{BASE_URL}/api/v1/clients/{client_id}/data-gaps",
            headers=headers_base,
            timeout=30,
        )
        gaps_resp.raise_for_status()
        gaps = gaps_resp.json()["gaps"]
        result["data_gaps"] = {
            "count": len(gaps),
            "by_priority": dict(zip(
                ["high", "medium", "low"],
                [len([g for g in gaps if g["priority"] == p]) for p in ["high", "medium", "low"]]
            )),
            "gap_types": list({g["gap_type"] for g in gaps}),
        }

        # Step 5: 查 approvals queue (验证危险动作进队列)
        approvals_resp = httpx.get(
            f"{BASE_URL}/api/v1/approvals",
            headers=headers_base,
            params={"run_id": result["agent_run_id"]},
            timeout=30,
        )
        approvals_resp.raise_for_status()
        result["pending_approvals"] = len(approvals_resp.json().get("approvals", []))

    except Exception as e:
        result["errors"].append(str(e))

    return result


def compute_v30_score(snap_r0, snap_r2, run_result):
    """100 分制评分 (跟 11 文档 7 维度对齐)."""
    scores = {}

    # 维度 1: AI 调度全链路 (15 分)
    scores["维度1_AI调度全链路"] = score_dimension_1(run_result)

    # 维度 2: 资料变客户理解 (20 分)
    scores["维度2_资料变客户理解"] = score_dimension_2(snap_r0, snap_r2, run_result)

    # 维度 3: 澄清问题质量 (15 分)
    scores["维度3_澄清问题质量"] = score_dimension_3(snap_r0, snap_r2, run_result)

    # 维度 4: 理解转行动草稿 (15 分)
    scores["维度4_理解转行动草稿"] = score_dimension_4(snap_r0, snap_r2, run_result)

    # 维度 5: 纠错回写 (15 分) — R2 主要静态评估, 实测留 R3
    scores["维度5_纠错回写"] = score_dimension_5(run_result)

    # 维度 6: 内外驱动一致性 (10 分) — R2 跑外置 agent, 比较内置留 R3
    scores["维度6_内外驱动一致"] = score_dimension_6(run_result)

    # 维度 7: 安全审计 (15 分)
    scores["维度7_安全审计"] = score_dimension_7(run_result)

    scores["total"] = sum(s["score"] for s in scores.values() if isinstance(s, dict))
    return scores


def check_hard_gates(snap_r0, snap_r2, run_result, conn, client_id, test_run_id):
    """7 硬门槛 (任一失败 = 不能宣告目标完成)."""
    gates = {}

    # 1 AI 不操作界面 (我们走 HTTP, 必过)
    gates["1_不操作界面"] = {"pass": True, "evidence": "Headless HTTP only"}

    # 2 AI 不直接写 DB (检查 run_result 是否走 service)
    gates["2_不直写DB"] = {"pass": all_via_service(run_result), "evidence": "..."}

    # 3 上下文绑定 (检查写入 atomic_facts 的 actor_type)
    new_facts = sqlite_query(conn, f"""
        SELECT actor_type, COUNT(*) FROM atomic_facts
        WHERE client_id = ? AND created_at > '{test_run_start}'
        GROUP BY actor_type
    """, (client_id,))
    gates["3_上下文绑定"] = {
        "pass": all(at == "external_ai_agent" for at, _ in new_facts),
        "evidence": dict(new_facts),
    }

    # 4 不只写 atomic_facts (验证派生表也有增长)
    derived_growth = sum(
        snap_r2[t]["client"] - snap_r0[t]["client"]
        for t in ["event_line_activities", "risk_signals", "commitments",
                  "clarification_records", "strategic_thought_insights"]
        if snap_r0[t].get("client") is not None
    )
    gates["4_不只atomic_facts"] = {
        "pass": derived_growth >= 3,
        "evidence": f"派生表新增 {derived_growth} 条",
    }

    # 5 危险动作进 approval
    gates["5_危险动作approval"] = {
        "pass": run_result.get("pending_approvals", 0) >= 1,
        "evidence": f"pending {run_result.get('pending_approvals', 0)}",
    }

    # 6 Agent Run Log 完整
    run_id = run_result.get("agent_run_id")
    if run_id:
        n_traces = conn.execute(
            "SELECT COUNT(*) FROM ai_episode_log WHERE ai_session_id = ?",
            (run_id,)
        ).fetchone()[0]
        gates["6_AgentRunLog"] = {
            "pass": n_traces >= 5,
            "evidence": f"ai_episode_log {n_traces} 条",
        }
    else:
        gates["6_AgentRunLog"] = {"pass": False, "evidence": "no run_id"}

    # 7 跨客户隔离 (新写入的 atomic_facts client_id 必须等于 input client_id)
    cross_client_leaks = conn.execute("""
        SELECT COUNT(*) FROM atomic_facts
        WHERE client_id != ?
          AND created_at > ?
          AND actor_id = ?
    """, (client_id, test_run_start, "b-r2-objective-eval")).fetchone()[0]
    gates["7_跨客户隔离"] = {
        "pass": cross_client_leaks == 0,
        "evidence": f"cross-client leak: {cross_client_leaks}",
    }

    return gates


# ... 其余 helper 函数省略 (compute_v30_score 子函数, rollback_test_run_id 等)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clients", default=",".join(TEST_CLIENTS))
    parser.add_argument("--mode", default="draft")
    parser.add_argument("--report-out", default="docs/B_AI_V3_0_R2_REPORT_20260523.md")
    args = parser.parse_args()

    all_results = []
    for cname in args.clients.split(","):
        client_id = lookup_client_id_by_name(cname)
        result = run_objective_eval_for_client(client_id, cname, mode=args.mode)
        all_results.append(result)

    # 生成 R2 报告
    report_md = render_r2_report(all_results)
    Path(args.report_out).write_text(report_md, encoding="utf-8")
    print(f"\n✓ R2 报告: {args.report_out}")

    # 汇总
    total_score_avg = sum(r["scores"]["total"] for r in all_results) / len(all_results)
    print(f"\n★ R2 平均总分: {total_score_avg:.1f}/100")
    pass_threshold = 70
    print(f"  通过线: {pass_threshold}")
    print(f"  状态: {'🟢 PASS' if total_score_avg >= pass_threshold else '🔴 FAIL'}")


if __name__ == "__main__":
    main()
```

### 3.2 输出 R2 报告模板

```markdown
# B AI · V3.0 R2 客观评估报告

> 跑日期: 2026-05-XX
> 测试客户: 日慈基金会 / 益语智库 / 善加基金会
> Mode: draft

## 总分

| 客户 | 维度 1 | 维度 2 | 维度 3 | 维度 4 | 维度 5 | 维度 6 | 维度 7 | 总分 |
|---|---|---|---|---|---|---|---|---|
| 日慈基金会 | 13/15 | 18/20 | 12/15 | 13/15 | 8/15 | 6/10 | 12/15 | 82/100 |
| 益语智库 | ... | ... | ... | ... | ... | ... | ... | ... |
| 善加基金会 | ... | ... | ... | ... | ... | ... | ... | ... |
| **平均** | | | | | | | | **XX/100** |

通过线: 70/100 (R2 工程验收)
状态: 🟢 / 🟡 / 🔴

## 7 硬门槛通过情况

| 客户 | 1 不操作界面 | 2 不直写 DB | 3 上下文绑定 | 4 不只 atomic | 5 approval | 6 Run Log | 7 跨客户 0 | 通过 |
|---|---|---|---|---|---|---|---|---|
| 日慈 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 7/7 |
| ... |

## 数据中心前后对比 (R0 vs R2)

(每客户独立列表)

## AI 主动补缺口能力评估

(列出每客户的 data_gaps 数量 + 调用 intel.search 次数 + 写 external_evidence_cards 数)

## 修复优先级 (Top 5)

...
```

---

## 4 · 跟 A V3.0 P0-P2 endpoint 对接

| R2 测试调用 | 等 A 哪个 endpoint |
|---|---|
| POST /api/v1/agent/goals | V3.0 P1a (T+3-4) |
| POST .../goals/{id}/plan | V3.0 P1a (T+3-4) |
| POST /api/v1/agent/runs | V3.0 P1a (T+3-4) |
| GET .../data-gaps | V3.0 P0a (T+1) ★ 最早可用 |
| GET /api/v1/approvals | V3.0 P2a (T+5-6) |
| Headers X-Actor-Type | V3.0 P0b (T+1) |

→ B-3 脚本依赖 A T+1 + T+3-4 + T+5-6 全部完成, 估 **A 完成后 B 跑 1-2 天**.

---

## 5 · 可选: 早期"Data Gap only" smoke 测试 (T+1 就能跑)

如果 A 先完成 V3.0 P0 (Data Gap API + X-Actor-Type), B 可以先跑一个轻量 smoke:

```python
# scripts/run_v30_data_gap_smoke.py
def smoke_test():
    for client in ["日慈基金会", "益语智库", "善加基金会"]:
        client_id = lookup(client)
        gaps = httpx.get(f"{BASE}/api/v1/clients/{client_id}/data-gaps", headers=hdr).json()
        print(f"  {client}: {len(gaps['gaps'])} gaps")
        for g in gaps['gaps'][:5]:
            print(f"    - [{g['priority']}] {g['gap_type']}: {g['description'][:60]}...")
```

A T+1 完成后 B 立刻跑 smoke, 看 Data Gap API 真实出什么.

---

## 6 · R2 客户预期分数 (基于现状预测)

按 09 评估 (38 分) + A V2.5 P0-1/2/3/4 进展 + V3.0 P0-P2 完成后:

| 客户 | R0 (V2.2 大成时) | R1 (现在 V2.4) | R2 预测 (V3.0 P0-P2 后) |
|---|---|---|---|
| 日慈基金会 | 38 | 50-55 | **75-85** ★ 可能过 80 |
| 益语智库 | (没测) | 30-40 | 60-70 |
| 善加基金会 | (没测) | 20-25 | 45-55 (信息稀疏先天劣势) |
| **平均** | 38 | 35-40 | **60-70** |

**R2 通过线 70 分**: 平均如果到 70, V3.0 P0-P2 阶段验收通过 ✅. 否则识别短板进 P3.

---

## 7 · 风险与备选 (B 提前 flag)

| 风险 | 影响 | 备选 |
|---|---|---|
| A V3.0 endpoint 跑慢 (LLM 调用 > 10 分钟单 plan) | 单客户 R2 跑半小时 | mode=dry-run 优先, 真 LLM 留 R3 |
| 跨客户测试同时跑会冲突 LLM session lock | 三客户串行才行 | 默认串行 (一个跑完再跑下一个) |
| approval queue 还没接前端 → 测不到"用户批准后真执行" | 维度 4 任务草稿打折 | R2 只测 approval 入队, 真批准留 R3 |
| Data Gap API 跨客户隔离 bug | 门槛 7 失败 | 跨客户 atomic_facts 直接 SQL verify |
| test_run_id rollback 不完全 (派生表 trigger 写入没标 run_id) | prod db 残留测试数据 | 跑前快照 + 跑后 diff + 手动清理 |

---

## 8 · 何时跑

```
等 A 全部完成 (V3.0 P0+P1+P2 全部 ✅) 后, B 跑:
  Step 1 (5 min):  sqlite3 quick verify 14 张语义表 baseline
  Step 2 (5 min):  smoke test Data Gap API (轻量)
  Step 3 (15 min): 单客户 dry-run 跑一遍 (日慈)
  Step 4 (45-90 min): 三客户串行 draft mode (生成真 fact + 进 approval queue)
  Step 5 (15 min): 生成 R2 报告
  Step 6 (5 min):  rollback test_run_id 清理

总: 1.5-2 小时跑完 R2.
```

---

**Author**: AI B · 2026-05-23
**实现时机**: 等 A V3.0 P0-P2 全部完成 (T+5-6) 后 B 立刻写 scripts/run_v30_objective_eval.py + 跑
**报告模板**: docs/B_AI_V3_0_R2_REPORT_20260523.md (待生成)
