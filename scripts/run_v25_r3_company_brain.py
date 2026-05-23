"""[B] V2.1 RC R3 真 HTTP 客观评估测试 · 公司大脑理解指数 (骨架)

服务: 顾源源 5/23 拍板 — R2 通过后用同款 HTTP 严卡标尺重测 R3
设计依据:
  - A R3 FINAL 88.8 评分公式 (docs/V2.6_R3_COMPANY_BRAIN_SCORE.json)
  - B R3 验证 (docs/B_AI_R3_88_STATS_VERIFY_20260523.md)
  - 顾源源 5/23 11:00 8 步严卡 (跟 R2 同款标尺)

R3 北极星 (A docs/V2.6_R3_FINAL_ASSESSMENT.md):
  数据中心从"会处理材料" → "懂公司正在发生什么"

8 维度 100 分 (A 钦定):
  D1 信息身份识别  15  (文件类型 90% + 角色 80%)
  D2 关系归属判断  15  (historical_links 关联 + cross-table)
  D3 历史记忆调取  15  (M2 复盘 + M3 QA 引用率)
  D4 合同与承诺理解 15 (contract_structures 全抽)
  D5 缺口与矛盾澄清 15 (contradictions / clarifications / data_gaps)
  D6 跨板块反向入库 10 (chat/会议/文件/合同/外部/任务/资讯/方法卡/计划)
  D7 行动转化能力  10  (agent_run_log + approval_queue)
  D8 安全与隔离    5   (跨客户 0 leak)

R3 通过线: ≥ 80 (A 钦定)
R3 8 硬门槛 (A 钦定, 顾源源接受): 见 docs/V2.6_R3_FINAL_ASSESSMENT.md

R3 必需 endpoint (A 待暴露):
  POST /api/v1/clients/{id}/files/identify       FileIdentityClassifier
  POST /api/v1/contracts/parse                   ContractStructureParser
  POST /api/v1/clients/{id}/historical-resolve   HistoricalMaterialResolver
  POST /api/v1/clients/{id}/company-brain/qa     CompanyBrainQA
  POST /api/v1/clients/{id}/data-gaps/compensate DataGapCompensator
  GET  /api/v1/clients/{id}/data-gaps            list

4 场景 (跟 A R3 一致, 但全 HTTP 严卡):
  Scenario 1: 20 文件场景 — file_identities 90% + 合同 6 份结构解析
  Scenario 2: 复盘历史关联 — '5 月签的补充协议' → 5/18 心盛 v2
  Scenario 3: CompanyBrainQA — 21 问 95% 引用 / 0 幻觉
  Scenario 4: DataGapCompensator — data_gaps 0→N / external_evidence_cards 真破零

跑法 (R2 通过 + A 暴露 R3 endpoint 后):
    cd ~/openclaw/workspace/V2.1
    python3 scripts/run_v25_r3_company_brain.py \
        --clients 日慈基金会,CFFC \
        --base-url http://localhost:47831

输出:
    - JSON: tests/reports/v26_r3_<timestamp>.json
    - Markdown: docs/B_AI_V2_6_R3_REPORT_<timestamp>.md

★ 严卡 (顾源源 5/23 钦定, 沿用 R2):
  - 通过 HTTP endpoint, 不直接调 Python service
  - 数据源强制 V2.1 lab db (不接受 dogfood_real snapshot)
  - test_run_id 标记 + 可回滚
  - 不再用旧主仓库扣分
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
DEFAULT_CLIENTS = ["日慈基金会", "CFFC"]

# R3 涉及表 (A R3 stats + V2.5 R2 治理表)
R3_CRITICAL_TABLES = [
    # V2.3 phase 0/1
    "atomic_facts",
    "event_line_activities",
    "risk_signals",
    "commitments",
    "clarification_records",
    "strategic_thought_insights",
    "fact_contradictions",
    # V2.4 派生器表
    "atomic_fact_confidence_history",
    # V2.5 R2-A 治理表
    "agent_run_log",
    "approval_queue",
    "idempotency_keys_v25",
    # V2.5 R2-B Pipeline
    "source_registry",
    # V2.6 R3 表 (A 待建)
    "file_identities",
    "contract_structures",
    "historical_reference_links",
    "data_gaps",
    "external_evidence_cards",
]

# R3 8 硬门槛 (A 钦定 + B 严卡)
R3_HARD_GATES = {
    "1_source_registered": "任何板块进入的信息必须登记来源 (source_registry)",
    "2_contract_structured": "合同类必须识别合同结构 (contract_structures ≥ 1)",
    "3_historical_linked": "复盘/任务提旧材料必须尝试关联 (historical_reference_links ≥ 1)",
    "4_uncertain_clarified": "不确定关联必须进澄清 (clarification_records 多候选场景 ≥ 1)",
    "5_external_isolated": "外部情报不得覆盖内部权威 (external_evidence_cards needs_confirm only)",
    "6_method_isolated": "方法卡不得污染客户事实 (system_derived 隔离)",
    "7_user_correction_propagates": "用户纠错必须改变后续回答 (V2.4 P2-7)",
    "8_cross_client_zero_leak": "跨客户隔离必须 0 错误 (V2.5 R2-D)",
    # 顾源源 R2 沿用 5 严卡
    "9_http_only": "全程 HTTP endpoint 调用",
    "10_v21_lab_db": "数据在 V2.1 lab db 真写 (非 dogfood_real)",
    "11_idempotent": "重复跑不重复写入",
}


# ── 工具 ──────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_filename() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def snapshot_r3_tables(conn: sqlite3.Connection, client_id: str) -> dict:
    """R3 17 张表的客户特定行数."""
    snap: dict = {}
    for t in R3_CRITICAL_TABLES:
        try:
            total = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            try:
                client_n = conn.execute(
                    f'SELECT COUNT(*) FROM "{t}" WHERE client_id = ?', (client_id,)
                ).fetchone()[0]
            except sqlite3.OperationalError:
                client_n = None
            snap[t] = {"total": total, "client": client_n, "exists": True}
        except sqlite3.OperationalError as exc:
            snap[t] = {"total": 0, "client": 0, "exists": False, "error": str(exc)}
    return snap


def lookup_client_id(conn: sqlite3.Connection, client_name: str) -> str | None:
    row = conn.execute(
        "SELECT id FROM clients WHERE name LIKE ? LIMIT 1",
        (f"%{client_name}%",),
    ).fetchone()
    return row[0] if row else None


# ── 4 场景 (TODO: 等 A 暴露 R3 endpoint 后填) ────────────────


def scenario_1_file_identification(
    client_id: str, base_url: str, headers: dict, conn: sqlite3.Connection,
) -> dict:
    """场景 1: 20 文件场景 → file_identities 90% + 合同 6 份结构解析.

    TODO: 等 A 暴露:
      POST /api/v1/clients/{id}/files/identify
      POST /api/v1/contracts/parse
    """
    return {
        "scenario": "1_file_identification",
        "status": "blocked_endpoint_not_exposed",
        "todo": [
            "POST /api/v1/clients/{id}/files/identify",
            "POST /api/v1/contracts/parse",
        ],
        "expected_file_identities_delta": ">=20 with type/role accuracy >= 80%",
        "expected_contract_structures_delta": ">=1",
    }


def scenario_2_historical_resolve(
    client_id: str, base_url: str, headers: dict, conn: sqlite3.Connection,
) -> dict:
    """场景 2: 复盘历史关联.

    输入: "客户提到 5 月签的那份补充协议, 我们要找原件做参考"
    期望: HistoricalMaterialResolver 命中历史合同, historical_reference_links +1

    TODO: 等 A 暴露 POST /api/v1/clients/{id}/historical-resolve
    """
    return {
        "scenario": "2_historical_resolve",
        "status": "blocked_endpoint_not_exposed",
        "todo": ["POST /api/v1/clients/{id}/historical-resolve"],
        "expected_links_delta": ">=1",
        "test_prompt": "客户提到 5 月签的那份补充协议, 我们要找原件做参考",
    }


def scenario_3_company_brain_qa(
    client_id: str, base_url: str, headers: dict, conn: sqlite3.Connection,
) -> dict:
    """场景 3: CompanyBrainQA 21 问.

    评估: 引用率 ≥ 95% (有 [fact:xxx]/[contract:xxx] 等引用标签) + 0 幻觉

    TODO: 等 A 暴露 POST /api/v1/clients/{id}/company-brain/qa
          (现 workspace/chat 已接 build_company_brain_context, 可考虑沿用)

    21 问 (A R3-M3 标准): 客户基本面 / 合同 / 历史 / 风险 / 承诺 / 缺口 / 战略
    """
    return {
        "scenario": "3_company_brain_qa",
        "status": "blocked_endpoint_not_exposed_or_use_workspace_chat",
        "todo": ["POST /api/v1/clients/{id}/company-brain/qa or workspace/chat"],
        "expected_citation_rate": ">= 95%",
        "expected_hallucination_rate": "== 0%",
        "test_questions_count": 21,
    }


def scenario_4_data_gap_compensate(
    client_id: str, base_url: str, headers: dict, conn: sqlite3.Connection,
) -> dict:
    """场景 4: DataGapCompensator 真破零.

    输入: "客户预算还没定, 学校配合度也不确定, 但希望下周二看到一版轻量方案."
    期望: data_gaps +N (预算/学校名单/配合风险) +
          external_evidence_cards 真 ≥ 1 (在 V2.1 lab db, 不是 dogfood_real)

    TODO: 等 A 暴露:
      GET /api/v1/clients/{id}/data-gaps
      POST /api/v1/clients/{id}/data-gaps/compensate
    """
    return {
        "scenario": "4_data_gap_compensate",
        "status": "blocked_endpoint_not_exposed",
        "todo": [
            "POST /api/v1/clients/{id}/data-gaps/compensate",
            "GET /api/v1/clients/{id}/data-gaps",
        ],
        "expected_data_gaps_delta": ">= 3",
        "expected_external_evidence_cards_delta": ">= 1",
        "test_prompt": "客户预算还没定, 学校配合度也不确定, 但希望下周二看到一版轻量方案.",
    }


# ── 8 维度评分 (跟 A 一致, 但数据来自 V2.1 lab db 真测) ──────


def score_r3_8d(snap_before: dict, snap_after: dict, scenarios: dict) -> dict:
    """R3 8 维度评分.

    跟 A R3 FINAL 一致, 但所有 stats 来自 V2.1 lab db (snap_before/after diff),
    不是 dogfood_real snapshot.
    """
    def delta(t: str) -> int:
        b = snap_before.get(t, {}).get("client") or 0
        a = snap_after.get(t, {}).get("client") or 0
        return a - b

    file_id_n = delta("file_identities")
    contract_n = delta("contract_structures")
    hist_link_n = delta("historical_reference_links")
    contra_n = delta("fact_contradictions")
    clarif_n = delta("clarification_records")
    gap_n = delta("data_gaps")
    eec_n = delta("external_evidence_cards")
    run_log_n = delta("agent_run_log")
    appr_n = delta("approval_queue")
    facts_n = delta("atomic_facts")
    insights_n = delta("strategic_thought_insights")

    # D1 信息身份识别 (15)
    if file_id_n >= 20:
        d1_score = 12 + min(3, contract_n * 0.5)
    elif file_id_n >= 10:
        d1_score = 8
    elif file_id_n >= 1:
        d1_score = 4
    else:
        d1_score = 0
    d1_score = min(15, d1_score)

    # D2 关系归属判断 (15)
    d2_score = min(15, 4 + hist_link_n * 3 + (4 if hist_link_n >= 4 else 0))

    # D3 历史记忆调取 (15) - 来自 scenario 3 QA 引用率
    qa = scenarios.get("scenario_3", {}) or {}
    citation_rate = qa.get("actual_citation_rate", 0.0)
    if citation_rate >= 0.95:
        d3_score = 15
    elif citation_rate >= 0.80:
        d3_score = 12
    elif citation_rate >= 0.60:
        d3_score = 8
    elif hist_link_n >= 1:
        d3_score = 5
    else:
        d3_score = 0

    # D4 合同与承诺理解 (15)
    if contract_n >= 6:
        d4_score = 15
    else:
        d4_score = min(15, contract_n * 2.5)

    # D5 缺口与矛盾澄清 (15)
    d5_score = min(15, (1 if contra_n >= 1 else 0) * 5
                       + (1 if clarif_n >= 1 else 0) * 5
                       + (1 if gap_n >= 1 else 0) * 5)

    # D6 跨板块反向入库 (10)
    # 9 板块: chat/会议/文件/合同/外部 + 任务/资讯/方法卡/计划
    # 简化: 每入 1 板块 +1.1 分
    boards_touched = 0
    if facts_n >= 1: boards_touched += 1   # 会议/chat
    if file_id_n >= 1: boards_touched += 1  # 文件
    if contract_n >= 1: boards_touched += 1  # 合同
    if eec_n >= 1: boards_touched += 1     # 外部
    if appr_n >= 1: boards_touched += 1    # 任务草稿排队
    # 资讯/方法卡/计划 R3 不一定测
    d6_score = min(10, boards_touched * 1.1)

    # D7 行动转化能力 (10)
    d7_score = min(10, (4 if run_log_n >= 1 else 0)
                      + (4 if appr_n >= 1 else 0)
                      + (2 if appr_n >= 2 else 0))

    # D8 安全与隔离 (5) - 来自跨客户隔离 check
    cross_iso = scenarios.get("cross_isolation", {}) or {}
    d8_score = 5 if cross_iso.get("pass") else 0

    scores = {
        "d1_信息身份识别": {"score": round(d1_score, 1), "max": 15},
        "d2_关系归属判断": {"score": round(d2_score, 1), "max": 15},
        "d3_历史记忆调取": {"score": round(d3_score, 1), "max": 15},
        "d4_合同与承诺理解": {"score": round(d4_score, 1), "max": 15},
        "d5_缺口与矛盾澄清": {"score": round(d5_score, 1), "max": 15},
        "d6_跨板块反向入库": {"score": round(d6_score, 1), "max": 10},
        "d7_行动转化能力": {"score": round(d7_score, 1), "max": 10},
        "d8_安全与隔离": {"score": round(d8_score, 1), "max": 5},
    }
    scores["total"] = round(sum(s["score"] for s in scores.values()), 1)
    scores["max"] = 100
    scores["r3_pass_line"] = 80
    scores["r3_passed"] = scores["total"] >= 80
    return scores


# ── 主流程: 单客户跑 R3 ─────────────────────────────────────


def run_r3_for_client(
    client_name: str, base_url: str, db_path: Path,
    other_client_name: str | None = None,
) -> dict:
    test_run_id = f"r3_{uuid.uuid4().hex[:12]}"
    print(f"\n{'=' * 72}")
    print(f"  V2.1 RC R3 真测试 · 客户: {client_name} · test_run_id={test_run_id}")
    print(f"{'=' * 72}\n")

    if not db_path.exists():
        return {"client_name": client_name, "error": f"V2.1 lab db 不存在: {db_path}"}

    conn = sqlite3.connect(str(db_path))
    client_id = lookup_client_id(conn, client_name)
    if not client_id:
        conn.close()
        return {"client_name": client_name, "error": f"客户不存在: {client_name}"}

    snap_before = snapshot_r3_tables(conn, client_id)
    print(f"▸ [0/6] R0 baseline · {sum(1 for v in snap_before.values() if v['exists'])}/17 表存在")

    other_client_id = None
    snap_other_before = None
    if other_client_name:
        other_client_id = lookup_client_id(conn, other_client_name)
        if other_client_id and other_client_id != client_id:
            snap_other_before = snapshot_r3_tables(conn, other_client_id)
            print(f"  对照客户 {other_client_name} baseline 采集")

    headers = {
        "X-Actor-Type": "external_ai_agent",
        "X-Actor-Id": "b-v26-r3-test",
        "X-Agent-Run-Id": test_run_id,
        "Idempotency-Key": f"{test_run_id}_r3_session",
    }

    scenarios = {
        "scenario_1": scenario_1_file_identification(client_id, base_url, headers, conn),
        "scenario_2": scenario_2_historical_resolve(client_id, base_url, headers, conn),
        "scenario_3": scenario_3_company_brain_qa(client_id, base_url, headers, conn),
        "scenario_4": scenario_4_data_gap_compensate(client_id, base_url, headers, conn),
    }
    for k, v in scenarios.items():
        print(f"  {k}: {v.get('status', 'unknown')}")

    time.sleep(2)
    snap_after = snapshot_r3_tables(conn, client_id)
    snap_other_after = (
        snapshot_r3_tables(conn, other_client_id)
        if other_client_id and snap_other_before is not None
        else None
    )

    # 跨客户隔离
    leaks: list[str] = []
    if snap_other_before and snap_other_after:
        for t in R3_CRITICAL_TABLES:
            b = snap_other_before.get(t, {}).get("client") or 0
            a = snap_other_after.get(t, {}).get("client") or 0
            if a != b:
                leaks.append(f"{t}: {b}→{a}")
    scenarios["cross_isolation"] = {
        "pass": len(leaks) == 0,
        "evidence": "0 leak" if not leaks else str(leaks),
        "other_client_id": other_client_id,
    }
    print(f"  cross_isolation: {'✅ 0 leak' if not leaks else '🔴 ' + str(leaks)}")

    # 8 维度评分
    scores = score_r3_8d(snap_before, snap_after, scenarios)
    print(f"\n▸ R3 总分: {scores['total']}/100  (通过线 ≥ 80)")
    for k, v in scores.items():
        if isinstance(v, dict):
            print(f"  {k}: {v['score']}/{v['max']}")

    conn.close()

    return {
        "client_name": client_name,
        "client_id": client_id,
        "test_run_id": test_run_id,
        "snap_before": snap_before,
        "snap_after": snap_after,
        "snap_other_before": snap_other_before,
        "snap_other_after": snap_other_after,
        "scenarios": scenarios,
        "scores": scores,
    }


# ── 主入口 ───────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clients", default=",".join(DEFAULT_CLIENTS))
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--db", default=str(V21_LAB_DB))
    parser.add_argument("--json-out")
    parser.add_argument("--md-out")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"✗ V2.1 lab db 不存在: {db_path}")
        print(f"  请先跑: cd ~/openclaw/workspace/V2.1 && npm run db:init:lab")
        return 1

    # 前置检查
    print(f"\n▸ 前置 · V2.1 backend ({args.base_url}) 是否可达...")
    try:
        r = httpx.get(f"{args.base_url}/api/v1/clients", timeout=5)
        if r.status_code != 200:
            print(f"  🔴 V2.1 backend 不可达, status {r.status_code}")
            return 1
        print(f"  ✅ V2.1 backend 健康, {len(r.json())} clients")
    except Exception as exc:
        print(f"  🔴 V2.1 backend 不可达: {exc}")
        return 1

    print(f"\n  ⚠️ R3 5 个 endpoint 仍 TODO 等 A 暴露:")
    print(f"      POST /api/v1/clients/{{id}}/files/identify")
    print(f"      POST /api/v1/contracts/parse")
    print(f"      POST /api/v1/clients/{{id}}/historical-resolve")
    print(f"      POST /api/v1/clients/{{id}}/company-brain/qa  (或沿用 workspace/chat)")
    print(f"      POST /api/v1/clients/{{id}}/data-gaps/compensate")

    client_list = [c.strip() for c in args.clients.split(",")]
    all_results = []
    started = time.perf_counter()
    for i, cname in enumerate(client_list):
        other = client_list[(i + 1) % len(client_list)] if len(client_list) > 1 else None
        if other == cname:
            other = None
        result = run_r3_for_client(cname, args.base_url, db_path, other_client_name=other)
        all_results.append(result)

    duration = time.perf_counter() - started

    valid_results = [r for r in all_results if "scores" in r]
    avg_score = (
        sum(r["scores"]["total"] for r in valid_results) / len(valid_results)
        if valid_results else 0.0
    )

    json_path = Path(args.json_out) if args.json_out else REPORTS_DIR / f"v26_r3_{_now_filename()}.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps({
        "generated_at": _now_iso(),
        "base_url": args.base_url,
        "duration_seconds": duration,
        "results": all_results,
        "summary": {
            "clients_tested": len(all_results),
            "avg_score": round(avg_score, 1),
            "pass_threshold": 80,
            "pass": avg_score >= 80,
        },
    }, ensure_ascii=False, indent=2))
    print(f"\n✓ JSON: {json_path}")

    md_path = (
        Path(args.md_out) if args.md_out
        else ROOT / "docs" / f"B_AI_V2_6_R3_REPORT_{_now_filename()}.md"
    )
    md_path.write_text(_render_md(all_results, duration, avg_score), encoding="utf-8")
    print(f"✓ Markdown: {md_path}")

    print(f"\n{'=' * 72}")
    print(f"  V2.1 RC R3 真客观评估完成 · {duration:.0f}s")
    print(f"  {len(client_list)} 客户平均: {avg_score:.1f}/100")
    print(f"  R3 通过线 80: {'🟢 PASS' if avg_score >= 80 else '🔴 FAIL'}")
    print(f"{'=' * 72}\n")
    return 0 if avg_score >= 80 else 1


def _render_md(all_results: list[dict], duration: float, avg_score: float) -> str:
    lines = [
        f"# V2.1 RC R3 真客观评估报告 · 公司大脑理解指数",
        "",
        f"> 生成: {_now_iso()} · 耗时 {duration:.0f}s",
        f"> 评估对象: V2.1 仓库 (= 未来主仓库候选版)",
        f"> 调用方式: HTTP endpoint (port 47831), 不直调 Python service",
        f"> 数据源: V2.1 lab db (拒绝 dogfood_real / snapshot)",
        "",
        f"## 总分",
        "",
        f"{len(all_results)} 客户平均: **{avg_score:.1f}/100**",
        f"R3 通过线: ≥ 80",
        f"状态: {'🟢 PASS' if avg_score >= 80 else '🔴 FAIL'}",
        "",
        f"## 8 维度评分明细",
        "",
        "| 客户 | D1 身份 | D2 归属 | D3 历史 | D4 合同 | D5 澄清 | D6 反向 | D7 行动 | D8 安全 | 总分 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in all_results:
        if "scores" not in r:
            lines.append(f"| {r['client_name']} | - | - | - | - | - | - | - | - | error |")
            continue
        s = r["scores"]
        cells = [
            f"{s['d1_信息身份识别']['score']}/{s['d1_信息身份识别']['max']}",
            f"{s['d2_关系归属判断']['score']}/{s['d2_关系归属判断']['max']}",
            f"{s['d3_历史记忆调取']['score']}/{s['d3_历史记忆调取']['max']}",
            f"{s['d4_合同与承诺理解']['score']}/{s['d4_合同与承诺理解']['max']}",
            f"{s['d5_缺口与矛盾澄清']['score']}/{s['d5_缺口与矛盾澄清']['max']}",
            f"{s['d6_跨板块反向入库']['score']}/{s['d6_跨板块反向入库']['max']}",
            f"{s['d7_行动转化能力']['score']}/{s['d7_行动转化能力']['max']}",
            f"{s['d8_安全与隔离']['score']}/{s['d8_安全与隔离']['max']}",
            f"**{s['total']}**",
        ]
        lines.append(f"| {r['client_name']} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append(f"## 4 场景结果")
    lines.append("")
    for r in all_results:
        if "scenarios" not in r:
            continue
        lines.append(f"### {r['client_name']}")
        for k, v in r["scenarios"].items():
            mark = "✅" if v.get("pass") or v.get("status", "").startswith("ok") else "⚠️" if "blocked" in v.get("status", "") else "🔴"
            ev = v.get("evidence") or v.get("status", "")
            lines.append(f"- {mark} **{k}**: {ev}")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("**Author**: AI B")
    lines.append(f"**Generated**: {_now_iso()}")
    lines.append("**前置**: V2.1 backend (port 47831) + V2.1 lab db schema init + A 暴露 R3 endpoint")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
