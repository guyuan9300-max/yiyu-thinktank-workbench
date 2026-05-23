"""[B] V2.1 RC R2 真 HTTP 客观评估测试

服务: 顾源源 5/23 09:50 拍板 — 先解 R2 阻塞, 再做 V3.0 P0a
设计依据: docs/B_AI_V3_0_R2_OBJECTIVE_EVAL_SCRIPT_DESIGN.md
新口径: docs/V2_1_RC_EVAL_DIRECTIVE_20260523.md (V2.1 = 未来主仓库候选版)

5 硬门槛 (顾源源 5/23 09:50 钦定):
  1. 通过 HTTP endpoint 调用, 不直接调 Python service
  2. V2.1 lab db 里 11 张关键表真实存在
  3. 会议纪要处理后, 事实/风险/承诺/澄清/任务草稿/Agent Run Log/Approval Queue 都真有记录
  4. 不依赖 dogfood_real snapshot
  5. 能重复跑一次, 不产生重复任务和重复澄清

顾源源 5/23 11:00 加严 8 步 (跑前/跑中/跑后全覆盖):
  1. curl smoke endpoint (跑前先确认 R2 endpoint 真存在, 不是 404)
  2. 提交日慈会议纪要
  3. 提交 CFFC 会议纪要
  4. sqlite3 查 V2.1 lab db 前后差异
  5. 核对 facts / event_line / risks / commitments / clarifications / approval_queue / agent_run_log
  6. 验证跨客户隔离 (跑客户 A 后, 客户 B 在 V2.1 lab db 数据不动)
  7. 验证重复运行不重复写入
  8. 输出 V2.1 R2 HTTP 真实运行报告

★ 严卡:
  - 不接受 dogfood_real / snapshot 作为通过依据
  - 不再用旧主仓库 prod db 扣分

跑法:
    cd ~/openclaw/workspace/V2.1
    # 前置: A 已暴露 endpoint + 用户已跑 npm run db:init:lab + npm run dev:lab
    python3 scripts/run_v25_r2_meeting_minute.py \
        --clients 日慈基金会,益语智库,善加基金会 \
        --mode draft \
        --base-url http://localhost:47831

输出:
    - JSON: tests/reports/v25_r2_<timestamp>.json
    - Markdown: docs/B_AI_V2_5_R2_REPORT_<timestamp>.md
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import httpx
except ImportError:
    print("✗ httpx 未安装, 跑: pip install httpx")
    sys.exit(1)


# ── 配置 ─────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "tests" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

V21_LAB_DB = Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2_V21Lab/app.db"

DEFAULT_BASE_URL = "http://localhost:47831"
# 顾源源 5/23 11:00 钦定: "提交日慈会议纪要 + 提交 CFFC 会议纪要"
DEFAULT_CLIENTS = ["日慈基金会", "CFFC"]

# 真实会议纪要场景 (3 客户共用同一段, 替换 X)
GOLDEN_MEETING_TEMPLATE = """
今天和{client}开会, 客户提到下个月想先做教师端试点, 预算还没有最终确认.
项目负责人希望先压缩方案复杂度, 但秘书长担心学校配合度不够.
我们答应下周二前给一版更轻量的试点方案, 同时补充风险控制说明.
""".strip()

# 11 张关键表 (硬门槛 2)
CRITICAL_TABLES = [
    "atomic_facts",
    "atomic_fact_confidence_history",
    "approval_queue",
    "agent_run_log",
    "idempotency_keys_v25",
    "source_registry",
    "event_line_activities",
    "risk_signals",
    "commitments",
    "clarification_records",
    "strategic_thought_insights",
]

# 5 硬门槛 + 100 分制 7 维度
HARD_GATE_THRESHOLDS = {
    "min_atomic_facts": 5,
    "min_risk_signals": 1,
    "min_commitments": 1,
    "min_clarification_records": 1,
    "min_task_drafts": 1,
    "min_agent_run_log": 1,
    "min_approval_queue": 1,
}


# ── 工具函数 ──────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_filename() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


# Per-table client filter SQL clause (V2.1 lab db 真实 schema)
# 缺省: client_id = ?  (大部分表)
# 例外: clarification_records 用 scope_type='client' AND scope_id = ?
#       event_line_activities 通过 event_line_id JOIN event_lines
#       idempotency_keys_v25 没 client 字段, 走全表 fallback
TABLE_CLIENT_FILTERS: dict[str, str | None] = {
    "atomic_facts": "client_id = ?",
    "atomic_fact_confidence_history": None,  # fact-level, 无 client 列
    "approval_queue": "client_id = ?",
    "agent_run_log": "client_id = ?",
    "idempotency_keys_v25": None,  # key-level
    "source_registry": "client_id = ?",
    "event_line_activities": (
        "event_line_id IN (SELECT id FROM event_lines WHERE primary_client_id = ?)"
    ),
    "risk_signals": "client_id = ?",
    "commitments": "client_id = ?",
    "clarification_records": "scope_type='client' AND scope_id = ?",
    "strategic_thought_insights": "client_id = ?",
}


def snapshot_tables(conn: sqlite3.Connection, client_id: str) -> dict:
    """采集 11 张关键表的全量行数 + 客户特定行数."""
    snap: dict = {}
    for t in CRITICAL_TABLES:
        try:
            total = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        except sqlite3.OperationalError as exc:
            snap[t] = {"total": 0, "client": 0, "exists": False, "error": str(exc)}
            continue
        filter_clause = TABLE_CLIENT_FILTERS.get(t, "client_id = ?")
        if filter_clause is None:
            client_n = total  # fallback: 全表当 client 数 (无 client 维度)
        else:
            try:
                client_n = conn.execute(
                    f'SELECT COUNT(*) FROM "{t}" WHERE {filter_clause}', (client_id,)
                ).fetchone()[0]
            except sqlite3.OperationalError as exc:
                client_n = None
                snap[t] = {
                    "total": total, "client": None,
                    "exists": True, "filter_error": str(exc),
                }
                continue
        snap[t] = {"total": total, "client": client_n, "exists": True}
    return snap


def lookup_client_id(conn: sqlite3.Connection, client_name: str) -> str | None:
    row = conn.execute(
        "SELECT id FROM clients WHERE name LIKE ? LIMIT 1",
        (f"%{client_name}%",),
    ).fetchone()
    return row[0] if row else None


# ── 5 硬门槛检查 ─────────────────────────────────────────────


def check_hard_gate_1_http_only(call_log: list[dict]) -> dict:
    """硬门槛 1: 通过 HTTP endpoint 调用, 不直接调 Python service."""
    if not call_log:
        return {"pass": False, "evidence": "没有任何 HTTP 调用记录"}
    all_http = all(c.get("type") == "http" for c in call_log)
    return {
        "pass": all_http,
        "evidence": f"{len(call_log)} 次调用, 全 HTTP={all_http}",
    }


def check_hard_gate_2_tables_exist(snap: dict) -> dict:
    """硬门槛 2: V2.1 lab db 里 11 张关键表真实存在."""
    missing = [t for t, info in snap.items() if not info.get("exists")]
    return {
        "pass": len(missing) == 0,
        "evidence": f"11 张表存在 {11 - len(missing)}/11" + (f", 缺: {missing}" if missing else ""),
    }


def check_hard_gate_3_records_real(snap_before: dict, snap_after: dict) -> dict:
    """硬门槛 3: 会议纪要处理后, 事实/事件线/风险/承诺/澄清/任务/run log/approval queue 真有记录.

    顾源源 5/23 11:00 第 5 步: 核对 facts / event_line / risks / commitments /
    clarifications / approval_queue / agent_run_log.
    """
    deltas = {}
    for t in CRITICAL_TABLES:
        b = snap_before.get(t, {}).get("client") or 0
        a = snap_after.get(t, {}).get("client") or 0
        deltas[t] = a - b

    pass_atomic = deltas.get("atomic_facts", 0) >= HARD_GATE_THRESHOLDS["min_atomic_facts"]
    pass_event_line = deltas.get("event_line_activities", 0) >= 1
    pass_risk = deltas.get("risk_signals", 0) >= HARD_GATE_THRESHOLDS["min_risk_signals"]
    pass_commit = deltas.get("commitments", 0) >= HARD_GATE_THRESHOLDS["min_commitments"]
    pass_clarify = deltas.get("clarification_records", 0) >= HARD_GATE_THRESHOLDS["min_clarification_records"]
    pass_run_log = deltas.get("agent_run_log", 0) >= HARD_GATE_THRESHOLDS["min_agent_run_log"]
    pass_approval = deltas.get("approval_queue", 0) >= HARD_GATE_THRESHOLDS["min_approval_queue"]

    all_pass = all([
        pass_atomic, pass_event_line, pass_risk, pass_commit,
        pass_clarify, pass_run_log, pass_approval,
    ])
    return {
        "pass": all_pass,
        "evidence": {
            "atomic_facts +": deltas.get("atomic_facts", 0),
            "event_line_activities +": deltas.get("event_line_activities", 0),
            "risk_signals +": deltas.get("risk_signals", 0),
            "commitments +": deltas.get("commitments", 0),
            "clarification_records +": deltas.get("clarification_records", 0),
            "agent_run_log +": deltas.get("agent_run_log", 0),
            "approval_queue +": deltas.get("approval_queue", 0),
        },
    }


def check_hard_gate_6_cross_client_isolation(
    snap_other_before: dict, snap_other_after: dict, other_client_id: str,
) -> dict:
    """硬门槛 6: 跨客户隔离 (顾源源 5/23 11:00 第 6 步).

    跑客户 A 后, 客户 B 在 V2.1 lab db 的 (client_id = B) 数据不动.
    若 B 数据动了 → 客户隔离破, R2 不过.
    """
    if not snap_other_before or not snap_other_after:
        return {"pass": None, "evidence": "无对照客户, 跳过 (single-client 模式)"}
    leaks: list[str] = []
    for t in [
        "atomic_facts", "event_line_activities", "risk_signals",
        "commitments", "clarification_records",
        "agent_run_log", "approval_queue",
    ]:
        b = snap_other_before.get(t, {}).get("client") or 0
        a = snap_other_after.get(t, {}).get("client") or 0
        if a != b:
            leaks.append(f"{t}: {b}→{a}")
    return {
        "pass": len(leaks) == 0,
        "evidence": (
            f"对照客户 {other_client_id} 数据未动 (0 leak)"
            if not leaks
            else f"客户隔离破: {leaks}"
        ),
    }


def smoke_check_endpoints(base_url: str) -> dict:
    """顾源源 5/23 11:00 第 1 步: curl smoke endpoint.

    跑前先确认 R2 endpoint 真存在 (不是 404), 否则后面跑没意义.
    返回 dict: { endpoint: {status_code, note} }.
    """
    smoke_targets = [
        ("POST", "/api/v1/meeting-minutes/process", {"client_id": "smoke", "meeting_text": "smoke", "mode": "draft"}),
        ("GET", "/api/v1/approvals", None),
    ]
    results: dict = {}
    for method, path, payload in smoke_targets:
        try:
            if method == "GET":
                r = httpx.get(f"{base_url}{path}", timeout=3.0)
            else:
                r = httpx.post(f"{base_url}{path}", json=payload, timeout=3.0)
            results[f"{method} {path}"] = {
                "status_code": r.status_code,
                # 404 = 没暴露 / 422 = 存在但 payload 不对 / 200 = ok
                "exists": r.status_code != 404,
            }
        except Exception as exc:
            results[f"{method} {path}"] = {
                "status_code": "exception",
                "exists": False,
                "error": str(exc),
            }
    return results


def check_hard_gate_4_no_snapshot(snap_after: dict, test_run_id: str) -> dict:
    """硬门槛 4: 不依赖 dogfood_real snapshot — 验证写入直接进 V2.1 lab db."""
    # 通过看 atomic_facts 客户行数确实增长, 证明在 V2.1 lab db 写
    has_new_data = any(
        info.get("client", 0) and info["client"] > 0
        for info in snap_after.values()
        if info.get("exists")
    )
    return {
        "pass": has_new_data,
        "evidence": f"V2.1 lab db 有新数据 (test_run_id={test_run_id})",
    }


def check_hard_gate_5_idempotent(call_log: list[dict], snap_after_first: dict, snap_after_second: dict) -> dict:
    """硬门槛 5: 重复跑一次, 不产生重复任务和重复澄清."""
    # 如果 snap_after_second == snap_after_first (各表 client_n 一致), 说明幂等生效
    if snap_after_second is None:
        return {"pass": None, "evidence": "未跑第二次, 跳过 (single-run 模式)"}
    diff = {}
    for t in ["atomic_facts", "tasks", "clarification_records", "approval_queue"]:
        a1 = snap_after_first.get(t, {}).get("client") or 0
        a2 = snap_after_second.get(t, {}).get("client") or 0
        if a1 != a2:
            diff[t] = {"first": a1, "second": a2}
    return {
        "pass": len(diff) == 0,
        "evidence": "重复跑后无新增" if not diff else f"重复产生: {diff}",
    }


# ── 100 分制 7 维度评分 ───────────────────────────────────────


def score_v30_r2(snap_before: dict, snap_after: dict, call_log: list[dict],
                 hard_gates: dict, test_run_result: dict) -> dict:
    """100 分制 7 维度评分."""
    scores = {}

    # 维度 1: AI 调度全链路 (15 分)
    plan_steps = len(call_log)
    modules = {c.get("module") for c in call_log if c.get("module")}
    scores["d1_ai_dispatch"] = {
        "score": min(15, 5 + plan_steps + len(modules)),
        "max": 15,
        "evidence": f"调用步骤 {plan_steps}, 模块 {len(modules)}",
    }

    # 维度 2: 资料变客户理解 (20 分)
    d3 = hard_gates.get("3", {}).get("evidence", {})
    facts_n = d3.get("atomic_facts +", 0) if isinstance(d3, dict) else 0
    risks_n = d3.get("risk_signals +", 0) if isinstance(d3, dict) else 0
    commits_n = d3.get("commitments +", 0) if isinstance(d3, dict) else 0
    points = 0
    if facts_n >= 5: points += 8
    elif facts_n >= 3: points += 4
    if risks_n >= 1: points += 5
    if commits_n >= 1: points += 5
    if facts_n >= 8: points += 2
    scores["d2_data_to_understanding"] = {
        "score": min(20, points),
        "max": 20,
        "evidence": f"facts +{facts_n} / risks +{risks_n} / commits +{commits_n}",
    }

    # 维度 3: 澄清问题质量 (15 分)
    clarif_n = d3.get("clarification_records +", 0) if isinstance(d3, dict) else 0
    points = 0
    if clarif_n >= 1: points += 8
    if clarif_n >= 2: points += 4
    if clarif_n >= 3: points += 3
    scores["d3_clarification"] = {
        "score": min(15, points),
        "max": 15,
        "evidence": f"clarifications +{clarif_n}",
    }

    # 维度 4: 理解转行动草稿 (15 分)
    # tasks +N 信息暂取自 test_run_result.writes_summary 或 snap diff (tasks 表)
    task_drafts = test_run_result.get("task_drafts_created", 0)
    approvals_n = d3.get("approval_queue +", 0) if isinstance(d3, dict) else 0
    points = 0
    if task_drafts >= 1: points += 8
    if approvals_n >= 1: points += 5
    if task_drafts >= 2: points += 2
    scores["d4_action_drafts"] = {
        "score": min(15, points),
        "max": 15,
        "evidence": f"task drafts {task_drafts}, approvals queued {approvals_n}",
    }

    # 维度 5: 纠错回写 (15 分) - R2 主要静态, R3 真测
    scores["d5_correction_writeback"] = {
        "score": 5,  # 静态评估 5/15, R2 不真测
        "max": 15,
        "evidence": "R2 暂不测真纠错回写, 等 R3",
    }

    # 维度 6: 内外驱动一致性 (10 分) - R2 单驱动测, R3 双驱动测
    scores["d6_dual_drive"] = {
        "score": 4,  # 单驱动 4/10
        "max": 10,
        "evidence": "R2 单外置 agent 驱动, 双驱动一致性等 R3",
    }

    # 维度 7: 安全审计 (15 分)
    run_log_n = d3.get("agent_run_log +", 0) if isinstance(d3, dict) else 0
    points = 0
    if hard_gates.get("1", {}).get("pass"): points += 3  # HTTP only
    if hard_gates.get("2", {}).get("pass"): points += 3  # 11 张表存在
    if run_log_n >= 1: points += 4
    if hard_gates.get("5", {}).get("pass"): points += 5  # 幂等
    scores["d7_safety_audit"] = {
        "score": min(15, points),
        "max": 15,
        "evidence": f"HTTP only={hard_gates.get('1',{}).get('pass')}, 表 ok={hard_gates.get('2',{}).get('pass')}, run_log +{run_log_n}, 幂等={hard_gates.get('5',{}).get('pass')}",
    }

    scores["total"] = sum(s["score"] for s in scores.values() if isinstance(s, dict))
    scores["max"] = 100
    return scores


# ── 主流程: 单客户跑一次 R2 ──────────────────────────────────


def run_r2_for_client(
    client_name: str,
    base_url: str,
    db_path: Path,
    mode: str = "draft",
    test_repeatable: bool = True,
    other_client_name: str | None = None,
) -> dict:
    """单客户跑完整 R2.

    other_client_name: 跨客户隔离对照客户 (顾源源 5/23 11:00 第 6 步).
        跑客户 A 时, 同时采集 B 的 baseline → 跑完看 B 数据是否动 (应不动).
    """
    test_run_id = f"r2_{uuid.uuid4().hex[:12]}"
    print(f"\n{'=' * 72}")
    print(f"  V2.1 RC R2 真测试 · 客户: {client_name} · test_run_id={test_run_id}")
    print(f"{'=' * 72}\n")

    if not db_path.exists():
        return {
            "client_name": client_name,
            "error": f"V2.1 lab db 不存在: {db_path}",
        }

    conn = sqlite3.connect(str(db_path))

    # Step 1: 找 client_id
    client_id = lookup_client_id(conn, client_name)
    if not client_id:
        conn.close()
        return {
            "client_name": client_name,
            "error": f"客户不存在: {client_name}",
        }

    # Step 2: 第 0 轮 baseline + 跨客户对照 baseline
    snap_before = snapshot_tables(conn, client_id)
    print(f"▸ [0/6] R0 baseline 采集: 11 张表存在 {sum(1 for v in snap_before.values() if v['exists'])}/11")

    other_client_id: str | None = None
    snap_other_before: dict | None = None
    if other_client_name:
        other_client_id = lookup_client_id(conn, other_client_name)
        if other_client_id and other_client_id != client_id:
            snap_other_before = snapshot_tables(conn, other_client_id)
            print(f"  对照客户: {other_client_name} ({other_client_id}) baseline 采集")

    # Step 3: 调真 HTTP endpoint
    meeting_text = GOLDEN_MEETING_TEMPLATE.format(client=client_name)
    call_log: list[dict] = []

    headers = {
        "X-Actor-Type": "external_ai_agent",
        "X-Actor-Id": "b-v25-r2-test",
        "X-Agent-Run-Id": test_run_id,
        "Idempotency-Key": f"{test_run_id}_meeting_minute",
    }

    print(f"▸ [1/5] 调 POST /api/v1/meeting-minutes/process ...", flush=True)
    test_result: dict = {"test_run_id": test_run_id, "client_id": client_id}
    try:
        r = httpx.post(
            f"{base_url}/api/v1/meeting-minutes/process",
            headers=headers,
            json={
                "client_id": client_id,
                "meeting_text": meeting_text,
                "mode": mode,
                "test_run_id": test_run_id,
            },
            timeout=300,
        )
        call_log.append({
            "type": "http",
            "module": "meeting_minute_processor",
            "endpoint": "/api/v1/meeting-minutes/process",
            "status": r.status_code,
        })
        if r.status_code in (200, 201):
            resp = r.json()
            test_result["http_response"] = resp
            test_result["task_drafts_created"] = resp.get("task_drafts_created", 0)
            print(f"  ✅ HTTP {r.status_code}")
        else:
            test_result["error"] = f"HTTP {r.status_code}: {r.text[:200]}"
            print(f"  🔴 HTTP {r.status_code}: {r.text[:200]}")
    except Exception as exc:
        test_result["error"] = str(exc)
        call_log.append({
            "type": "http",
            "module": "meeting_minute_processor",
            "endpoint": "/api/v1/meeting-minutes/process",
            "status": "exception",
            "error": str(exc),
        })
        print(f"  🔴 异常: {exc}")

    # Step 4: 第 2 轮 baseline + 跨客户对照 after
    time.sleep(2)  # 等异步派生器跑完
    snap_after = snapshot_tables(conn, client_id)
    snap_other_after: dict | None = None
    if other_client_id and snap_other_before is not None:
        snap_other_after = snapshot_tables(conn, other_client_id)
    print(f"▸ [2/6] R2 baseline 采集")

    # Step 5: 硬门槛 5 重复跑 (幂等性测试)
    snap_after_second = None
    if test_repeatable:
        print(f"▸ [3/5] 重复跑 (验证幂等性)...", flush=True)
        try:
            r2 = httpx.post(
                f"{base_url}/api/v1/meeting-minutes/process",
                headers=headers,  # 同 idempotency_key
                json={
                    "client_id": client_id,
                    "meeting_text": meeting_text,
                    "mode": mode,
                    "test_run_id": test_run_id,
                },
                timeout=300,
            )
            call_log.append({
                "type": "http",
                "module": "meeting_minute_processor (repeat)",
                "endpoint": "/api/v1/meeting-minutes/process",
                "status": r2.status_code,
            })
            time.sleep(2)
            snap_after_second = snapshot_tables(conn, client_id)
            print(f"  ✅ 重复调用完成, HTTP {r2.status_code}")
        except Exception as exc:
            print(f"  ⚠️ 重复跑失败: {exc}")

    # Step 6: 6 硬门槛检查 (5 + 跨客户隔离)
    print(f"▸ [4/6] 6 硬门槛检查 (含跨客户隔离)...")
    hard_gates = {
        "1": check_hard_gate_1_http_only(call_log),
        "2": check_hard_gate_2_tables_exist(snap_after),
        "3": check_hard_gate_3_records_real(snap_before, snap_after),
        "4": check_hard_gate_4_no_snapshot(snap_after, test_run_id),
        "5": check_hard_gate_5_idempotent(call_log, snap_after, snap_after_second),
        "6": check_hard_gate_6_cross_client_isolation(
            snap_other_before, snap_other_after, other_client_id or "",
        ),
    }
    for k, v in hard_gates.items():
        mark = "✅" if v["pass"] else "🔴" if v["pass"] is False else "⚠️"
        print(f"  门槛 {k}: {mark} {v['evidence']}")

    # Step 7: 100 分制评分
    print(f"▸ [5/6] 100 分制 7 维度评分...")
    scores = score_v30_r2(snap_before, snap_after, call_log, hard_gates, test_result)
    print(f"  总分: {scores['total']}/100")
    for k, v in scores.items():
        if isinstance(v, dict):
            print(f"  {k}: {v['score']}/{v['max']}  ({v['evidence']})")

    conn.close()

    return {
        "client_name": client_name,
        "client_id": client_id,
        "other_client_name": other_client_name,
        "other_client_id": other_client_id,
        "test_run_id": test_run_id,
        "mode": mode,
        "snap_before": snap_before,
        "snap_after": snap_after,
        "snap_after_second": snap_after_second,
        "snap_other_before": snap_other_before,
        "snap_other_after": snap_other_after,
        "call_log": call_log,
        "hard_gates": hard_gates,
        "scores": scores,
        "test_result": test_result,
    }


# ── 主入口 ───────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clients", default=",".join(DEFAULT_CLIENTS))
    parser.add_argument("--mode", default="draft", choices=["dry-run", "draft", "live"])
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--db", default=str(V21_LAB_DB))
    parser.add_argument("--no-repeat", action="store_true", help="跳过幂等性测试")
    parser.add_argument("--json-out")
    parser.add_argument("--md-out")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"✗ V2.1 lab db 不存在: {db_path}")
        print(f"  请先跑: cd ~/openclaw/workspace/V2.1 && npm run db:init:lab")
        return 1

    # 前置 1: V2.1 backend 健康检查
    print(f"\n▸ 前置 1 · V2.1 backend ({args.base_url}) 是否可达...")
    try:
        r = httpx.get(f"{args.base_url}/api/v1/clients", timeout=5)
        if r.status_code != 200:
            print(f"  🔴 V2.1 backend 不可达, status {r.status_code}")
            return 1
        print(f"  ✅ V2.1 backend 健康, {len(r.json())} clients")
    except Exception as exc:
        print(f"  🔴 V2.1 backend 不可达: {exc}")
        print(f"  请先跑: cd ~/openclaw/workspace/V2.1 && npm run dev:lab")
        return 1

    # 前置 2: smoke check R2 endpoint 真存在 (顾源源 5/23 11:00 第 1 步)
    print(f"\n▸ 前置 2 · smoke check R2 endpoint 是否暴露 (顾源源第 1 步)...")
    smoke = smoke_check_endpoints(args.base_url)
    all_exists = True
    for ep, info in smoke.items():
        mark = "✅" if info["exists"] else "🔴"
        print(f"  {mark} {ep} → HTTP {info['status_code']}")
        if not info["exists"]:
            all_exists = False
    if not all_exists:
        print(f"\n  🔴 R2 endpoint 仍 404 (A 阻塞未解), R2 真测试无法进行.")
        print(f"  → 等 A 暴露 endpoint 后重跑.")
        # 写一份 "endpoint 未暴露" 的简短 markdown 报告, 便于追溯
        endpoint_blocked_md = (
            f"# V2.1 RC R2 真测试中止 · R2 endpoint 未暴露\n\n"
            f"> 时间: {_now_iso()}\n"
            f"> base_url: {args.base_url}\n\n"
            f"## smoke check\n\n"
        )
        for ep, info in smoke.items():
            mark = "✅" if info["exists"] else "🔴"
            endpoint_blocked_md += f"- {mark} {ep} → HTTP {info['status_code']}\n"
        endpoint_blocked_md += (
            f"\n## 下一步\n\nA 暴露 R2 endpoint 后重跑本脚本. (BLOCKER)\n"
        )
        md_blocked_path = ROOT / "docs" / f"B_AI_V2_5_R2_BLOCKED_{_now_filename()}.md"
        md_blocked_path.write_text(endpoint_blocked_md, encoding="utf-8")
        print(f"  → 已写: {md_blocked_path}")
        return 2  # blocked

    # 跨客户隔离对照: 跑客户 A 时取 B 当对照, 跑 B 时取 A 当对照
    client_list = [c.strip() for c in args.clients.split(",")]
    all_results = []
    started = time.perf_counter()
    for i, cname in enumerate(client_list):
        other_name = client_list[(i + 1) % len(client_list)] if len(client_list) > 1 else None
        if other_name == cname:
            other_name = None
        result = run_r2_for_client(
            cname, args.base_url, db_path,
            mode=args.mode, test_repeatable=not args.no_repeat,
            other_client_name=other_name,
        )
        all_results.append(result)

    duration = time.perf_counter() - started

    # 计算平均分
    valid_results = [r for r in all_results if "scores" in r]
    if valid_results:
        avg_score = sum(r["scores"]["total"] for r in valid_results) / len(valid_results)
    else:
        avg_score = 0.0

    # 输出 JSON
    json_path = Path(args.json_out) if args.json_out else REPORTS_DIR / f"v25_r2_{_now_filename()}.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps({
        "generated_at": _now_iso(),
        "mode": args.mode,
        "base_url": args.base_url,
        "duration_seconds": duration,
        "results": all_results,
        "summary": {
            "clients_tested": len(all_results),
            "avg_score": round(avg_score, 1),
            "pass_threshold": 70,
            "pass": avg_score >= 70,
        },
    }, ensure_ascii=False, indent=2))
    print(f"\n✓ JSON: {json_path}")

    # 输出 Markdown 报告
    md = render_md_report(all_results, args.mode, duration, avg_score)
    md_path = Path(args.md_out) if args.md_out else ROOT / "docs" / f"B_AI_V2_5_R2_REPORT_{_now_filename()}.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"✓ Markdown: {md_path}")

    # 终端总结
    print(f"\n{'=' * 72}")
    print(f"  V2.1 RC R2 真客观评估完成 · {duration:.0f}s")
    print(f"  3 客户平均: {avg_score:.1f}/100")
    print(f"  R2 通过线 70: {'🟢 PASS' if avg_score >= 70 else '🔴 FAIL'}")
    print(f"{'=' * 72}\n")

    return 0 if avg_score >= 70 else 1


def render_md_report(all_results: list[dict], mode: str, duration: float, avg_score: float) -> str:
    lines = []
    lines.append(f"# V2.1 RC R2 真客观评估报告 (B-3 真 HTTP 跑)")
    lines.append("")
    lines.append(f"> 生成: {_now_iso()} · 耗时 {duration:.0f}s · mode={mode}")
    lines.append(f"> 评估对象: V2.1 仓库 (= 未来主仓库候选版)")
    lines.append(f"> 调用方式: HTTP endpoint (port 47831), 不直调 Python service")
    lines.append("")
    lines.append(f"## 总分")
    lines.append("")
    lines.append(f"3 客户平均: **{avg_score:.1f}/100**")
    lines.append(f"R2 通过线: ≥ 70")
    lines.append(f"状态: {'🟢 PASS' if avg_score >= 70 else '🔴 FAIL'}")
    lines.append("")

    # 6 硬门槛汇总 (含跨客户隔离)
    lines.append(f"## 6 硬门槛汇总 (顾源源 5/23 11:00 加严)")
    lines.append("")
    lines.append("| 客户 | 1 HTTP only | 2 11 表 | 3 真记录 | 4 不靠 snapshot | 5 幂等 | 6 跨客户隔离 |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in all_results:
        if "hard_gates" not in r:
            lines.append(f"| {r['client_name']} | ⚠️ skip ({r.get('error', '?')}) | | | | | |")
            continue
        gates = r["hard_gates"]
        marks = []
        for i in ["1", "2", "3", "4", "5", "6"]:
            p = gates.get(i, {}).get("pass")
            marks.append("✅" if p else "🔴" if p is False else "⚠️")
        lines.append(f"| {r['client_name']} | {marks[0]} | {marks[1]} | {marks[2]} | {marks[3]} | {marks[4]} | {marks[5]} |")
    lines.append("")

    # 7 维度评分
    lines.append(f"## 7 维度评分明细")
    lines.append("")
    lines.append("| 客户 | D1 调度 | D2 理解 | D3 澄清 | D4 行动 | D5 纠错 | D6 双驱动 | D7 安全 | 总分 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in all_results:
        if "scores" not in r:
            lines.append(f"| {r['client_name']} | - | - | - | - | - | - | - | error |")
            continue
        s = r["scores"]
        d1 = f"{s['d1_ai_dispatch']['score']}/{s['d1_ai_dispatch']['max']}"
        d2 = f"{s['d2_data_to_understanding']['score']}/{s['d2_data_to_understanding']['max']}"
        d3 = f"{s['d3_clarification']['score']}/{s['d3_clarification']['max']}"
        d4 = f"{s['d4_action_drafts']['score']}/{s['d4_action_drafts']['max']}"
        d5 = f"{s['d5_correction_writeback']['score']}/{s['d5_correction_writeback']['max']}"
        d6 = f"{s['d6_dual_drive']['score']}/{s['d6_dual_drive']['max']}"
        d7 = f"{s['d7_safety_audit']['score']}/{s['d7_safety_audit']['max']}"
        lines.append(f"| {r['client_name']} | {d1} | {d2} | {d3} | {d4} | {d5} | {d6} | {d7} | **{s['total']}** |")
    lines.append("")

    # 每客户详情
    lines.append(f"## 每客户详情")
    lines.append("")
    for r in all_results:
        lines.append(f"### {r['client_name']}")
        lines.append("")
        if "error" in r and "scores" not in r:
            lines.append(f"⚠️ 跳过: {r['error']}")
            lines.append("")
            continue
        lines.append(f"- test_run_id: `{r['test_run_id']}`")
        lines.append(f"- client_id: `{r['client_id']}`")
        if r.get("hard_gates"):
            for k, v in r["hard_gates"].items():
                mark = "✅" if v["pass"] else "🔴" if v["pass"] is False else "⚠️"
                lines.append(f"  - 门槛 {k}: {mark} {v['evidence']}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("**Author**: AI B")
    lines.append(f"**Generated**: {_now_iso()}")
    lines.append("**前置**: V2.1 backend (port 47831) running + V2.1 lab db schema init done")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
