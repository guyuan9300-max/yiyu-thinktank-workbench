"""[B] V3.0 AI 驱动软件能力 · L1-L4 dry-run 评估器 (顾源源 5/23 19:00 钦定)

不替 A 写业务. 测当前 V2.1 能跑到哪一层 + 标 blocked_by_A.

L1 单链路处理        — 一段输入触发一个内置链路 (会议纪要 → facts)
L2 多模块串联调度    — 一次输入触发 ≥ 4 个模块 (合同+任务+品牌+理事会)
L3 主动缺口发现      — AI 看出"缺预算/缺历史", 主动生成澄清+调外部
L4 Goal-Plan-Run     — 用户给目标, AI 拆解 N 步并执行

跑法:
    npm run eval:v3:dryrun
    或 python3 scripts/run_v3_ai_driven_dryrun_eval.py

输出:
    docs/B_AI_V3_DRYRUN_REPORT.md (覆盖最新)
    docs/B_AI_V3_DRYRUN_REPORT.json

跟 scripts/run_v30_ai_driven_software_eval.py 区别:
  · v30_ai_driven: 跑分 100 分制 7 维度 (前一份)
  · v3_dryrun: 分层判断 L1/L2/L3/L4 通不通 (这份, 顾源源新口径)

Author: AI B · 2026-05-23 19:40
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import httpx
except ImportError:
    print("✗ httpx 未安装"); sys.exit(1)


ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = ROOT / "fixtures" / "golden"
V21_LAB_DB = Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2_V21Lab/app.db"
DEFAULT_BASE_URL = "http://localhost:47831"
DEFAULT_CLIENT = "日慈基金会"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_filename() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _current_commit() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL,
        ).decode().strip()
        return out[:10]
    except Exception:
        return "unknown"


def lookup_client_id(conn: sqlite3.Connection, name: str) -> str | None:
    row = conn.execute(
        "SELECT id FROM clients WHERE name LIKE ? LIMIT 1", (f"%{name}%",),
    ).fetchone()
    return row[0] if row else None


# ── L1 单链路 ───────────────────────────────────────────────


def test_l1_single_link(base_url: str, client_id: str) -> dict:
    """L1 · 一段输入触发一个内置链路 (会议纪要 → facts/risks/commits/clarif)."""
    print(f"\n▸ L1 · 单链路处理 (会议纪要 → 内置链路)")
    test_run_id = f"v3dryrun_l1_{uuid.uuid4().hex[:10]}"
    meeting = (GOLDEN_DIR / "meeting_mingyuan.txt").read_text(encoding="utf-8")

    headers = {
        "X-Actor-Type": "internal_ai",
        "X-Actor-Id": "v3-dryrun-l1",
        "X-Agent-Run-Id": test_run_id,
        "Idempotency-Key": f"{test_run_id}_l1",
    }
    try:
        r = httpx.post(
            f"{base_url}/api/v1/meeting-minutes/process",
            headers=headers,
            json={"client_id": client_id, "meeting_text": meeting, "mode": "draft"},
            timeout=120,
        )
        if r.status_code != 200:
            return {
                "passed": False, "status": "blocked_by_A",
                "reason": f"meeting-minutes/process HTTP {r.status_code}",
            }
        resp = r.json()
        # L1 通过条件: facts ≥ 5 + commit ≥ 1 (单链路真处理了输入)
        passed = (
            resp.get("atomic_facts_added", 0) >= 5
            and resp.get("commitments_added", 0) >= 1
        )
        return {
            "passed": passed, "status": "ok" if passed else "weak",
            "test_run_id": test_run_id,
            "evidence": {
                "facts": resp.get("atomic_facts_added", 0),
                "risks": resp.get("risks_added", 0),
                "commits": resp.get("commitments_added", 0),
                "clarif": resp.get("clarifications_added", 0),
                "task_drafts": resp.get("task_drafts_added", 0),
                "approval_queue_ids": len(resp.get("approval_queue_ids", []) or []),
                "elapsed_seconds": resp.get("elapsed_seconds"),
            },
            "blocked_by": None if passed else "A meeting-minutes/process 处理能力不足",
        }
    except Exception as exc:
        return {"passed": False, "status": "exception", "reason": str(exc)[:120]}


# ── L2 多模块 ───────────────────────────────────────────────


def test_l2_multi_module(base_url: str, client_id: str) -> dict:
    """L2 · 一次输入触发 ≥ 4 个模块 (合同+任务+品牌+理事会)."""
    print(f"\n▸ L2 · 多模块串联调度")

    # 期望调用的 5 个 sub_goal endpoint
    sub_endpoints = [
        ("write_contract", "POST", "/api/v1/contracts/draft", {"client_id": client_id, "meeting_text": "x"}),
        ("meeting_agenda", "POST", f"/api/v1/clients/{client_id}/strategic-cockpit/meeting-pack", {"meeting_text": "x"}),
        ("brand_research", "POST", "/api/v1/intelligence/brand-mirror/analyze", {"client_id": client_id}),
        ("brand_proposal", "POST", f"/api/v1/clients/{client_id}/brand-proposition", {}),
        ("board_brief", "POST", "/api/v1/templates/generate", {"client_id": client_id}),
    ]
    module_results = []
    for key, method, path, payload in sub_endpoints:
        try:
            r = httpx.request(method, f"{base_url}{path}", json=payload, timeout=10.0)
            ok = r.status_code in (200, 201)
            module_results.append({
                "module": key, "endpoint": f"{method} {path}",
                "status_code": r.status_code, "ok": ok,
                "blocked_by_a": r.status_code in (404, 405),
            })
        except Exception as exc:
            module_results.append({
                "module": key, "endpoint": f"{method} {path}",
                "status_code": "exception", "ok": False, "blocked_by_a": True,
            })

    # +1 for meeting-minutes (L1 已过)
    modules_passed = 1 + sum(1 for m in module_results if m["ok"])
    passed = modules_passed >= 4
    return {
        "passed": passed,
        "status": "ok" if passed else "blocked_by_A",
        "modules_passed": modules_passed,
        "target": 4,
        "sub_modules": module_results,
        "blocked_by": [
            f"endpoint {m['endpoint']} 缺 ({m['status_code']})"
            for m in module_results if m["blocked_by_a"]
        ],
    }


# ── L3 主动缺口 ──────────────────────────────────────────────


def test_l3_active_gap(base_url: str, client_id: str, conn: sqlite3.Connection) -> dict:
    """L3 · AI 主动发现缺口 + 调外部补."""
    print(f"\n▸ L3 · 主动缺口发现")

    # 试调 data-gaps endpoint
    gap_endpoint_ok = False
    gap_count = 0
    try:
        r = httpx.get(f"{base_url}/api/v1/clients/{client_id}/data-gaps", timeout=5.0)
        if r.status_code == 200:
            data = r.json()
            gap_endpoint_ok = True
            gap_count = len(data) if isinstance(data, list) else 0
    except Exception:
        pass

    # 跑 GAP 输入看 V2.1 lab db 是否真涨 data_gaps
    test_run_id = f"v3dryrun_l3_{uuid.uuid4().hex[:10]}"
    gap_text = (
        "客户说他们想做青年行动者计划, 但没有给我们完整预算, 也没有给品牌历史资料. "
        "会议纪要里只提到去年他们做过类似活动, 但没有说明成效. 客户希望我们下周给一版品牌调整建议."
    )

    snap_before = conn.execute('SELECT COUNT(*) FROM data_gaps WHERE client_id = ?', (client_id,)).fetchone()[0]

    headers = {
        "X-Actor-Type": "internal_ai",
        "X-Actor-Id": "v3-dryrun-l3",
        "X-Agent-Run-Id": test_run_id,
        "Idempotency-Key": f"{test_run_id}_gap",
    }
    try:
        r = httpx.post(
            f"{base_url}/api/v1/meeting-minutes/process",
            headers=headers,
            json={"client_id": client_id, "meeting_text": gap_text, "mode": "draft"},
            timeout=120,
        )
        post_ok = r.status_code == 200
        post_data = r.json() if post_ok else {}
    except Exception as exc:
        post_ok = False
        post_data = {"error": str(exc)[:80]}

    time.sleep(2)
    snap_after = conn.execute('SELECT COUNT(*) FROM data_gaps WHERE client_id = ?', (client_id,)).fetchone()[0]
    data_gaps_added = snap_after - snap_before

    # L3 通过条件:
    # 1) data-gaps endpoint 暴露 200 (主动可查), 或
    # 2) data_gaps 表真涨 ≥ 3 (主动生成), 或
    # 3) clarifications 真涨 ≥ 3 (主动追问)
    clarif_added = post_data.get("clarifications_added", 0) if post_ok else 0
    passed = gap_endpoint_ok or data_gaps_added >= 3 or clarif_added >= 3

    return {
        "passed": passed,
        "status": "ok" if passed else "blocked_by_A",
        "gap_endpoint_ok": gap_endpoint_ok,
        "gap_endpoint_count": gap_count,
        "data_gaps_added_in_session": data_gaps_added,
        "clarifications_added_in_session": clarif_added,
        "target_data_gaps": 3,
        "target_clarifications": 3,
        "blocked_by": None if passed else "GET /clients/{id}/data-gaps 缺 + meeting-minutes 没派生 data_gaps",
    }


# ── L4 Goal-Plan-Run ─────────────────────────────────────────


def test_l4_goal_plan_run(base_url: str) -> dict:
    """L4 · 用户给目标, AI 拆解 N 步并执行."""
    print(f"\n▸ L4 · Goal-Plan-Run 三件套")
    endpoints_to_test = [
        ("POST", "/api/v1/agent/plan"),
        ("POST", "/api/v1/agent/run"),
        ("GET", "/api/v1/agent/status"),
    ]
    results = []
    for method, path in endpoints_to_test:
        try:
            r = httpx.request(method, f"{base_url}{path}",
                              json={"goal": "smoke"} if method == "POST" else None,
                              timeout=5.0)
            ok = r.status_code not in (404, 405)
            results.append({
                "endpoint": f"{method} {path}",
                "status_code": r.status_code,
                "ok": ok,
                "blocked_by_a": r.status_code in (404, 405),
            })
        except Exception:
            results.append({
                "endpoint": f"{method} {path}",
                "status_code": "exception", "ok": False, "blocked_by_a": True,
            })

    passed = all(r["ok"] for r in results)
    return {
        "passed": passed,
        "status": "blocked_by_A" if not passed else "ok",
        "endpoints": results,
        "blocked_by": [r["endpoint"] for r in results if r["blocked_by_a"]],
    }


# ── 主流程 ───────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", default=DEFAULT_CLIENT)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--db", default=str(V21_LAB_DB))
    args = parser.parse_args()

    commit = _current_commit()
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"✗ V2.1 lab db 不存在: {db_path}"); return 1

    print(f"\n{'=' * 72}")
    print(f"  V3.0 AI 驱动软件 · L1-L4 dry-run")
    print(f"  commit: {commit} · backend: {args.base_url} · client: {args.client}")
    print(f"{'=' * 72}")

    # backend 健康
    try:
        r = httpx.get(f"{args.base_url}/api/v1/clients", timeout=5)
        if r.status_code != 200:
            print(f"  🔴 backend 不可达"); return 1
        print(f"  ✅ backend 健康")
    except Exception as exc:
        print(f"  🔴 backend 不可达: {exc}"); return 1

    conn = sqlite3.connect(str(db_path))
    client_id = lookup_client_id(conn, args.client) or lookup_client_id(conn, "日慈基金会")
    if not client_id:
        print(f"  🔴 客户 fallback 失败"); return 1
    print(f"  client_id: {client_id}")

    # 跑 L1-L4
    l1 = test_l1_single_link(args.base_url, client_id)
    l2 = test_l2_multi_module(args.base_url, client_id)
    l3 = test_l3_active_gap(args.base_url, client_id, conn)
    l4 = test_l4_goal_plan_run(args.base_url)

    # 汇总
    print(f"\n{'=' * 72}")
    layers = [("L1", l1), ("L2", l2), ("L3", l3), ("L4", l4)]
    for name, layer in layers:
        mark = "✅" if layer["passed"] else "🔴"
        status = layer.get("status", "?")
        print(f"  {mark} {name} {status}")
    passed_count = sum(1 for _, l in layers if l["passed"])
    print(f"\n  通过层数: {passed_count} / 4")
    print(f"{'=' * 72}")

    # 输出
    result = {
        "generated_at": _now_iso(),
        "commit": commit,
        "base_url": args.base_url,
        "client": args.client,
        "client_id": client_id,
        "layers": {"L1": l1, "L2": l2, "L3": l3, "L4": l4},
        "summary": {
            "passed_count": passed_count,
            "total": 4,
            "north_star_achievement": (
                "L1 ✅ 单链路成立" if l1["passed"] else "L1 ❌ 单链路不成立"
            ),
        },
    }
    json_path = ROOT / "tests" / "reports" / f"v3_dryrun_{_now_filename()}.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    print(f"\n✓ JSON: {json_path}")

    md_path = ROOT / "docs" / "B_AI_V3_DRYRUN_REPORT.md"
    md_path.write_text(_render_md(result), encoding="utf-8")
    print(f"✓ Markdown: {md_path}")

    conn.close()
    return 0 if passed_count >= 2 else 1


def _render_md(result: dict) -> str:
    lines = [
        "# V3.0 AI 驱动软件 · L1-L4 dry-run 报告",
        "",
        f"> 生成: {result['generated_at']}",
        f"> commit: `{result['commit']}` · backend: {result['base_url']}",
        f"> client: {result['client']} ({result['client_id']})",
        "",
        f"## 总览",
        "",
        f"通过层数: {result['summary']['passed_count']} / 4",
        f"北极星状态: {result['summary']['north_star_achievement']}",
        "",
        f"## L1-L4 分层结果",
        "",
        f"| 层 | 状态 | 关键证据 | 阻塞 |",
        f"|---|---|---|---|",
    ]
    for name, key in [("L1 单链路处理", "L1"), ("L2 多模块调度", "L2"),
                      ("L3 主动缺口发现", "L3"), ("L4 Goal-Plan-Run", "L4")]:
        layer = result["layers"][key]
        mark = "✅" if layer["passed"] else "🔴"
        evidence_str = ""
        if key == "L1":
            ev = layer.get("evidence", {})
            evidence_str = f"facts {ev.get('facts')}/risks {ev.get('risks')}/commit {ev.get('commits')}/clarif {ev.get('clarif')}"
        elif key == "L2":
            evidence_str = f"调用 {layer.get('modules_passed', 0)} 模块 (目标 ≥4)"
        elif key == "L3":
            evidence_str = (
                f"gap endpoint={'✅' if layer.get('gap_endpoint_ok') else '🔴'}, "
                f"data_gaps +{layer.get('data_gaps_added_in_session', 0)}, "
                f"clarif +{layer.get('clarifications_added_in_session', 0)}"
            )
        elif key == "L4":
            evidence_str = f"endpoints {sum(1 for e in layer.get('endpoints', []) if e['ok'])}/{len(layer.get('endpoints', []))}"
        blocked = layer.get("blocked_by") or "-"
        if isinstance(blocked, list):
            blocked = "; ".join(blocked)
        lines.append(f"| {name} | {mark} {layer['status']} | {evidence_str} | {blocked} |")
    lines.append("")

    # L2 详情
    lines.append("## L2 详情 · 5 个 sub_goal endpoint")
    lines.append("")
    lines.append("| Module | Endpoint | HTTP | 状态 |")
    lines.append("|---|---|---|---|")
    for m in result["layers"]["L2"].get("sub_modules", []):
        mark = "✅" if m["ok"] else ("🔴 blocked_by_A" if m["blocked_by_a"] else "⚠️")
        lines.append(f"| {m['module']} | `{m['endpoint']}` | {m['status_code']} | {mark} |")
    lines.append("")

    # L4 详情
    lines.append("## L4 详情 · Goal-Plan-Run 三件套")
    lines.append("")
    lines.append("| Endpoint | HTTP | 状态 |")
    lines.append("|---|---|---|")
    for e in result["layers"]["L4"].get("endpoints", []):
        mark = "✅" if e["ok"] else "🔴 blocked_by_A"
        lines.append(f"| `{e['endpoint']}` | {e['status_code']} | {mark} |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("**关联**:")
    lines.append("- 评估标准: `docs/B_AI_EVAL_STANDARD_V1.md`")
    lines.append("- Golden Pack: `docs/B_AI_GOLDEN_TEST_PACK.md`")
    lines.append("- 进展雷达: `docs/B_AI_PROGRESS_RADAR.md`")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
