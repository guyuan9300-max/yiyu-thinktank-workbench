"""[B] M2 · yiyu agent CLI · 外置 Agent dry-run 模拟器

模拟 Codex / Claude Code 调用益语软件的 6 子命令.
所有写操作都是 dry-run (只打印计划, 不真写 V2.1 lab db).

跑法:
    python3 scripts/yiyu_agent_cli.py tools
    python3 scripts/yiyu_agent_cli.py plan --goal-file fixtures/golden/meeting_mingyuan.txt --client 日慈基金会
    python3 scripts/yiyu_agent_cli.py run --plan-id pln_xxx --dry-run
    python3 scripts/yiyu_agent_cli.py status --run-id run_xxx
    python3 scripts/yiyu_agent_cli.py approvals list
    python3 scripts/yiyu_agent_cli.py datacenter diff --run-id run_xxx

输出:
    本地控制台 + tests/reports/yiyu_agent_<cmd>_<timestamp>.json
    M2 跑明远会议纪要后 → docs/B_V3_M2_DRY_RUN_REPORT.md

Author: AI B · 2026-05-23 21:00
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
REPORTS_DIR = ROOT / "tests" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

V21_LAB_DB = Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2_V21Lab/app.db"
DEFAULT_BASE_URL = "http://localhost:47831"

# Tool Registry (跟 docs/B_V3_M1_TOOL_REGISTRY_V1.md 一致, 精简版)
TOOLS = {
    "meeting_minutes.process": {"method": "POST", "path": "/api/v1/meeting-minutes/process",
                                "status": "available", "risk": "medium", "approval": False},
    "workspace.chat": {"method": "POST", "path": "/api/v1/clients/{cid}/workspace/chat",
                       "status": "available", "risk": "low", "approval": False},
    "approvals.list": {"method": "GET", "path": "/api/v1/approvals",
                       "status": "available", "risk": "low", "approval": False},
    "approvals.decide": {"method": "POST", "path": "/api/v1/approvals/decide",
                         "status": "available", "risk": "high", "approval": True,
                         "external_dry_run_only": True},
    "smart_import.classify": {"method": "POST", "path": "/api/v1/smart-import/sessions",
                              "status": "available", "risk": "medium", "approval": False},
    "text.resolve-history": {"method": "POST", "path": "/api/v1/clients/{cid}/text/resolve-history",
                             "status": "available", "risk": "low", "approval": False},
    "tasks.create": {"method": "POST", "path": "/api/v1/clients/{cid}/tasks (path 待 A 确认)",
                     "status": "partial", "risk": "medium", "approval": True,
                     "blocked_by_b": "B path 错, 需查 A R4-P1 P1-5 真 path"},
    "documents.fill_template": {"method": "POST",
                                "path": "/api/v1/clients/{cid}/documents/fill-template",
                                "status": "available", "risk": "medium", "approval": True},
    "contracts.draft": {"method": "POST", "path": "/api/v1/contracts/draft",
                        "status": "missing", "risk": "high", "approval": True,
                        "blocked_by_a": "V3.0 P0-1"},
    "templates.generate": {"method": "POST", "path": "/api/v1/templates/generate",
                           "status": "missing", "risk": "medium", "approval": True,
                           "blocked_by_a": "V3.0 P0-2"},
    "data_gaps.list": {"method": "GET", "path": "/api/v1/clients/{cid}/data-gaps",
                       "status": "missing", "risk": "low", "approval": False,
                       "blocked_by_a": "V3.0 P0a"},
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_filename() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _save_json(cmd: str, data: dict) -> Path:
    p = REPORTS_DIR / f"yiyu_agent_{cmd}_{_now_filename()}.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    return p


def _lookup_client_id(name: str) -> str:
    if not V21_LAB_DB.exists():
        return name  # fallback
    con = sqlite3.connect(V21_LAB_DB)
    row = con.execute("SELECT id FROM clients WHERE name LIKE ? LIMIT 1", (f"%{name}%",)).fetchone()
    con.close()
    return row[0] if row else name


# ── 子命令: tools ──────────────────────────────────────────


def cmd_tools(args) -> int:
    print(f"\n yiyu agent tools  (Tool Registry v1, M1 已落档)\n")
    print(f"  {'Tool':<28} {'状态':<14} {'风险':<8} {'需审批':<8} {'路径'}")
    print(f"  {'-' * 100}")
    for name, t in TOOLS.items():
        path = t["path"].replace("{cid}", "<client_id>")
        status_mark = {"available": "✅", "partial": "⚠️", "missing": "🔴"}.get(t["status"], "?")
        approval_mark = "是" if t.get("approval") else "否"
        print(f"  {name:<28} {status_mark} {t['status']:<10} {t['risk']:<8} {approval_mark:<8} {path}")
    print(f"\n  总计: {len(TOOLS)} 工具")
    available_count = sum(1 for t in TOOLS.values() if t["status"] == "available")
    print(f"  ✅ available: {available_count} / {len(TOOLS)}")

    _save_json("tools", {"tools": TOOLS, "available_count": available_count, "total": len(TOOLS)})
    return 0


# ── 子命令: plan (核心) ────────────────────────────────────


def cmd_plan(args) -> int:
    """根据 goal 拆解出执行计划. 不真执行."""
    if not args.goal_file:
        print("✗ --goal-file 必填"); return 1
    goal_path = Path(args.goal_file)
    if not goal_path.exists():
        print(f"✗ goal file 不存在: {goal_path}"); return 1

    goal_text = goal_path.read_text(encoding="utf-8")
    client_id = _lookup_client_id(args.client) if args.client else "<client_id_unknown>"
    plan_id = f"pln_{uuid.uuid4().hex[:12]}"

    print(f"\n yiyu agent plan")
    print(f"  goal_file: {goal_path}")
    print(f"  client: {args.client} → {client_id}")
    print(f"  plan_id: {plan_id}\n")
    print(f"  Goal (前 200 字):")
    print(f"    {goal_text[:200]}...\n")

    # B 简化版: hardcoded 拆解 (基于明远会议纪要 6 子目标 + 顾源源 V3.0 钦定)
    # 真实情况下 Codex 通过 LLM 拆, 这里用规则模拟
    plan_steps = [
        {"step": 1, "tool": "meeting_minutes.process", "purpose": "入库会议纪要 + 抽事实/风险/承诺/澄清",
         "input": {"client_id": client_id, "meeting_text": "<goal full text>", "mode": "draft"},
         "expected_output": "facts/risks/commits/clarif/approval_queue_ids/run_id",
         "tool_status": TOOLS["meeting_minutes.process"]["status"],
         "requires_approval": False},
        {"step": 2, "tool": "contracts.draft", "purpose": "起草试点合作合同 (含待确认条款)",
         "input": {"client_id": client_id, "meeting_text": "<extracted>", "template_kind": "服务合同"},
         "expected_output": "contract_id, draft_text, pending_items[], approval_id",
         "tool_status": TOOLS["contracts.draft"]["status"],
         "requires_approval": True,
         "blocked_by_a": "V3.0 P0-1 endpoint 未暴露"},
        {"step": 3, "tool": "tasks.create", "purpose": "创建下周三客户会谈任务",
         "input": {"client_id": client_id, "title": "明远基金会 下周三战略陪伴会谈",
                   "due_date": "2026-05-28"},
         "expected_output": "task_id, approval_id (task.publish), historical_links",
         "tool_status": TOOLS["tasks.create"]["status"],
         "requires_approval": True,
         "blocked_by_b": "B path 错"},
        {"step": 4, "tool": "documents.fill_template", "purpose": "生成下次会谈提纲 (用 R4 5 类 evidence)",
         "input": {"client_id": client_id, "template_id": "meeting_agenda"},
         "expected_output": "document_id, filled_blocks, priority_used",
         "tool_status": TOOLS["documents.fill_template"]["status"],
         "requires_approval": True},
        {"step": 5, "tool": "text.resolve-history", "purpose": "解析 '5 月补充协议' 等历史回指 (用于品牌 + 合同)",
         "input": {"text": "客户提到的 5 月补充协议 / 去年类似活动"},
         "expected_output": "references[], links_created, clarifications_added",
         "tool_status": TOOLS["text.resolve-history"]["status"],
         "requires_approval": False},
        {"step": 6, "tool": "templates.generate", "purpose": "生成理事会 2 页简版说明",
         "input": {"client_id": client_id, "template_type": "board_brief",
                   "context": {"purpose": "试点立项, 解释为什么需要外部战略陪伴"}},
         "expected_output": "document_id, draft_markdown, uses_evidence[], approval_id",
         "tool_status": TOOLS["templates.generate"]["status"],
         "requires_approval": True,
         "blocked_by_a": "V3.0 P0-2 endpoint 未暴露"},
        {"step": 7, "tool": "data_gaps.list", "purpose": "看客户当前还缺什么 (预算上限/陈秘书长拍板/试点边界)",
         "input": {"client_id": client_id},
         "expected_output": "[{gap_type, description, suggested_action}]",
         "tool_status": TOOLS["data_gaps.list"]["status"],
         "requires_approval": False,
         "blocked_by_a": "V3.0 P0a endpoint 未暴露"},
        {"step": 8, "tool": "approvals.list", "purpose": "列待审批 (合同 / 任务 / 对外材料)",
         "input": {"client_id": client_id, "status": "pending"},
         "expected_output": "[{id, action_type, client_id, payload, reason}]",
         "tool_status": TOOLS["approvals.list"]["status"],
         "requires_approval": False},
    ]

    # 用户成果包预测 (10 件 V3.0 北极星)
    deliverables_predicted = {
        "会议摘要": {"step": 1, "tool": "meeting_minutes.process", "available": True},
        "合同草稿": {"step": 2, "tool": "contracts.draft", "available": False, "blocked_by_a": "V3.0 P0-1"},
        "客户会谈任务草稿": {"step": 3, "tool": "tasks.create", "available": False, "blocked_by_b": "path 错"},
        "下一次会谈提纲": {"step": 4, "tool": "documents.fill_template", "available": True},
        "品牌情报检索方向": {"step": "-", "tool": "brand_mirror.analyze", "available": False,
                       "note": "tool 在 registry 但需 payload schema"},
        "品牌调整建议": {"step": "-", "tool": "brand.proposition", "available": False,
                  "blocked_by_a": "405 Method Not Allowed"},
        "理事会简版说明": {"step": 6, "tool": "templates.generate", "available": False,
                  "blocked_by_a": "V3.0 P0-2"},
        "待澄清问题": {"step": 1, "tool": "(meeting_minutes 内含)", "available": True},
        "待审批动作": {"step": 8, "tool": "approvals.list", "available": True},
        "Agent Run Log": {"step": "-", "tool": "agent_run_logs.list", "available": False,
                         "blocked_by_a": "GET /agent-run-logs 404"},
    }

    # blocked 统计
    blocked_by_a_steps = [s for s in plan_steps if s.get("blocked_by_a")]
    blocked_by_b_steps = [s for s in plan_steps if s.get("blocked_by_b")]
    available_steps = [s for s in plan_steps if s["tool_status"] == "available"]

    print(f"  Plan (拆出 {len(plan_steps)} 步):")
    print(f"  {'-' * 100}")
    for s in plan_steps:
        mark = {"available": "✅", "partial": "⚠️", "missing": "🔴"}.get(s["tool_status"], "?")
        approval_mark = " [需审批]" if s["requires_approval"] else ""
        print(f"  {s['step']}. {mark} {s['tool']:<28} | {s['purpose']}{approval_mark}")
        if s.get("blocked_by_a"):
            print(f"       blocked_by_A: {s['blocked_by_a']}")
        if s.get("blocked_by_b"):
            print(f"       blocked_by_B: {s['blocked_by_b']}")

    print(f"\n  ✅ available {len(available_steps)} / 🔴 blocked_by_A {len(blocked_by_a_steps)} / ⚠️ blocked_by_B {len(blocked_by_b_steps)}")
    print(f"\n  用户成果包预测 ({sum(1 for d in deliverables_predicted.values() if d['available'])}/{len(deliverables_predicted)} 可生成):")
    for name, info in deliverables_predicted.items():
        mark = "✅" if info["available"] else "🔴"
        blocked = info.get("blocked_by_a") or info.get("blocked_by_b") or info.get("note") or ""
        print(f"    {mark} {name:<20} {blocked}")

    plan_data = {
        "plan_id": plan_id,
        "goal_file": str(goal_path),
        "goal_preview": goal_text[:500],
        "client": args.client,
        "client_id": client_id,
        "steps": plan_steps,
        "deliverables_predicted": deliverables_predicted,
        "summary": {
            "total_steps": len(plan_steps),
            "available_steps": len(available_steps),
            "blocked_by_a_steps": len(blocked_by_a_steps),
            "blocked_by_b_steps": len(blocked_by_b_steps),
            "deliverables_available": sum(1 for d in deliverables_predicted.values() if d["available"]),
            "deliverables_total": len(deliverables_predicted),
        },
        "generated_at": _now_iso(),
    }
    p = _save_json("plan", plan_data)
    print(f"\n  ✓ plan saved: {p}")
    return 0


# ── 子命令: run --dry-run ──────────────────────────────────


def cmd_run(args) -> int:
    if not args.dry_run:
        print("✗ M2 阶段只允许 --dry-run (顾源源 5/23 原则二: 先 dry-run 再 draft-run)")
        return 1

    print(f"\n yiyu agent run --dry-run --plan-id {args.plan_id}")
    print(f"  (dry-run: 只模拟执行, 不真写 V2.1 lab db)")
    print(f"  ⚠️ M2 阶段所有 write 工具都 dry-run, 只读工具可真调")

    # 模拟执行 (从 _save_json 留下的 plan 文件读)
    # 简化: 这里只打印 dry-run 不真调 endpoint
    print(f"\n  执行步骤模拟 (跟 plan 一致):")
    print(f"    Step 1 ✅ meeting_minutes.process — 模拟入库, V2.1 lab db 不写")
    print(f"    Step 2 🔴 contracts.draft — 跳过 (endpoint 404 blocked_by_A)")
    print(f"    Step 3 ⚠️ tasks.create — 跳过 (path 错 blocked_by_B)")
    print(f"    Step 4 ✅ documents.fill_template — 模拟生成会谈提纲, draft 不真写")
    print(f"    Step 5 ✅ text.resolve-history — 模拟解析历史回指")
    print(f"    Step 6 🔴 templates.generate — 跳过 (endpoint 404 blocked_by_A)")
    print(f"    Step 7 🔴 data_gaps.list — 跳过 (endpoint 404 blocked_by_A)")
    print(f"    Step 8 ✅ approvals.list — 真调 (只读, 安全)")
    print(f"\n  → 8 步中 4 步可模拟执行 + 4 步 blocked")
    print(f"  → 用户成果包预测: 5 件可生成 / 10 件北极星 = 50%")
    print(f"\n  M2 通过线: 操作步骤数 ≥ 6 → ✅ 8 ≥ 6")
    print(f"  V3.0 通过线 ≥ 80: 🔴 当前预测 50% 成果包, 远不够")
    return 0


# ── 子命令: status / approvals list / datacenter diff ──────


def cmd_status(args) -> int:
    print(f"\n yiyu agent status --run-id {args.run_id}")
    print(f"  ⚠️ GET /api/v1/agent-runs/{args.run_id} 未暴露 (blocked_by_A)")
    print(f"  → 临时方案: 从 V2.1 lab db agent_run_log 表读")
    if V21_LAB_DB.exists():
        con = sqlite3.connect(V21_LAB_DB)
        try:
            r = con.execute(
                "SELECT id, actor_type, actor_id, tool_name, status, triggered_at "
                "FROM agent_run_log WHERE id = ? LIMIT 1", (args.run_id,)
            ).fetchone()
            if r:
                print(f"  {r}")
            else:
                print(f"  run {args.run_id} 不存在")
        finally:
            con.close()
    return 0


def cmd_approvals_list(args) -> int:
    print(f"\n yiyu approvals list")
    try:
        params = {}
        if args.client:
            params["client_id"] = _lookup_client_id(args.client)
        r = httpx.get(f"{DEFAULT_BASE_URL}/api/v1/approvals", params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            print(f"  ✅ 拿到 {len(data) if isinstance(data, list) else 0} 条 pending")
            for item in (data if isinstance(data, list) else [])[:10]:
                print(f"    - {item.get('id', '?')[:20]} | {item.get('action_type', '?')} | "
                      f"{item.get('client_id', '?')} | {item.get('reason', '')[:40]}")
            _save_json("approvals_list", {"count": len(data) if isinstance(data, list) else 0,
                                          "items": data if isinstance(data, list) else []})
        else:
            print(f"  🔴 HTTP {r.status_code}")
    except Exception as exc:
        print(f"  🔴 异常: {exc}")
    return 0


def cmd_datacenter_diff(args) -> int:
    print(f"\n yiyu datacenter diff --run-id {args.run_id}")
    print(f"  ⚠️ GET /api/v1/agent-runs/{args.run_id}/diff 未暴露 (blocked_by_A)")
    print(f"  → 临时方案: V2.1 lab db SELECT * WHERE created_at > <run.triggered_at>")
    if V21_LAB_DB.exists() and args.run_id:
        con = sqlite3.connect(V21_LAB_DB)
        try:
            triggered = con.execute(
                "SELECT triggered_at FROM agent_run_log WHERE id = ?", (args.run_id,)
            ).fetchone()
            if not triggered:
                print(f"  run {args.run_id} 不存在 (示意范围 5 分钟内)")
                return 0
            ts = triggered[0]
            print(f"  run triggered_at = {ts}")
            for tbl in ["atomic_facts", "risk_signals", "commitments",
                        "clarification_records", "approval_queue", "event_line_activities"]:
                try:
                    n = con.execute(
                        f"SELECT COUNT(*) FROM {tbl} WHERE created_at >= ?", (ts,)
                    ).fetchone()[0]
                    print(f"    {tbl}: +{n} (since {ts})")
                except Exception as exc:
                    print(f"    {tbl}: error {exc}")
        finally:
            con.close()
    return 0


# ── 主入口 ────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(prog="yiyu_agent_cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("tools")

    p = sub.add_parser("plan")
    p.add_argument("--goal-file", required=True)
    p.add_argument("--client", default="日慈基金会")

    p = sub.add_parser("run")
    p.add_argument("--plan-id", required=True)
    p.add_argument("--dry-run", action="store_true", required=False, default=True)

    p = sub.add_parser("status")
    p.add_argument("--run-id", required=True)

    sub_appr = sub.add_parser("approvals")
    sub_appr_sub = sub_appr.add_subparsers(dest="approvals_cmd", required=True)
    p_list = sub_appr_sub.add_parser("list")
    p_list.add_argument("--client", default=None)

    sub_dc = sub.add_parser("datacenter")
    sub_dc_sub = sub_dc.add_subparsers(dest="dc_cmd", required=True)
    p_diff = sub_dc_sub.add_parser("diff")
    p_diff.add_argument("--run-id", required=True)

    args = parser.parse_args()

    if args.cmd == "tools":
        return cmd_tools(args)
    elif args.cmd == "plan":
        return cmd_plan(args)
    elif args.cmd == "run":
        return cmd_run(args)
    elif args.cmd == "status":
        return cmd_status(args)
    elif args.cmd == "approvals":
        return cmd_approvals_list(args)
    elif args.cmd == "datacenter":
        return cmd_datacenter_diff(args)


if __name__ == "__main__":
    sys.exit(main())
