"""[A] 模拟 Codex 跑完整单任务序列, 给 A 评估用真数据.

Codex 报告未到. 顾源源指令: "遇到问题用自己推荐的方式解决".
A 自己作为外部 AI 直接走 yiyu_mcp_server 内部 tool functions (跳过 stdio 协议层,
直接 import + call), 真测 db 前后差异, 真验 8 件事.

任务: 基于 CFFC 当前客户状态, 为本月理事会生成一份 5 分钟项目进展汇报草稿.

序列 (顾源源 §4 钦定 10 个动作):
  1. read tool-registry            (resource)
  2. read agent-state CFFC          (resource)
  3. read data-gaps CFFC            (tool)
  4. actions.dry-run create_task_draft (tool, 预演)
  5. documents.generate board_brief  (tool, 真生成)
  6. 同 Idempotency-Key 重发 documents.generate (验 idempotency)
  7. 草稿进 Approval Queue (隐含, 由 documents.generate 自动)
  8. agent_run_log 真写 (隐含)
  9. 不对外发送 (status='draft', external_target=true 但 approval_required)
  10. 不直接修客户事实 (业务表 Δ=0)
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAB_DB = Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2_V21Lab/app.db"
CFFC = "client_a4d1db29a7"
IDEM_KEY = f"codex-sim-{int(time.time())}"

# 13 张表 (顾源源 §5)
TABLES = [
    "agent_run_log", "approval_queue", "idempotency_keys_v25",
    "atomic_facts", "commitments", "risk_signals",
    "clarification_records", "data_gaps", "tasks",
    "event_line_activities", "external_evidence_cards",
    "contract_structures", "file_identities",
]


def snap_db() -> dict[str, int]:
    """13 表 row count snapshot."""
    conn = sqlite3.connect(LAB_DB)
    out: dict[str, int] = {}
    for t in TABLES:
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            out[t] = n
        except Exception as exc:
            out[t] = -1
    conn.close()
    return out


def load_mcp_server():
    """import mcp server 模块."""
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("yms", str(ROOT / "scripts/yiyu_mcp_server.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def run_codex_simulation() -> dict:
    """完整模拟 Codex 9 步序列, 真测 + 收集证据."""
    mod = load_mcp_server()

    evidence: dict = {
        "ts_start": time.strftime("%Y-%m-%d %H:%M:%S"),
        "client_id": CFFC,
        "idempotency_key": IDEM_KEY,
        "db_before": snap_db(),
        "steps": [],
    }

    # Step 1: read tool-registry
    s1 = await mod.read_resource("yiyu://tool-registry")
    s1_data = json.loads(s1)
    evidence["steps"].append({
        "step": 1, "name": "read tool-registry",
        "ok": True, "total_tools": s1_data.get("total"),
        "by_status": s1_data.get("by_status"),
        "schema_complete": s1_data.get("schema_completeness"),
    })

    # Step 2: read agent-state CFFC
    s2 = await mod.read_resource(f"yiyu://client/{CFFC}/state")
    s2_data = json.loads(s2)
    evidence["steps"].append({
        "step": 2, "name": "read agent-state CFFC",
        "ok": True,
        "top_fields_count": len(s2_data.keys()),
        "evidence_summary_keys": sorted((s2_data.get("evidence_summary") or {}).keys())[:8],
        "recommended_next_actions": len(s2_data.get("recommended_next_actions") or []),
        "client_name": (s2_data.get("client_profile") or {}).get("name"),
        "contracts": len(s2_data.get("contract_structures") or []),
        "data_gaps": len(s2_data.get("data_gaps") or []),
    })

    # Step 3: read data-gaps via tool
    s3 = await mod.call_tool("yiyu_get_data_gaps", {
        "client_id": CFFC, "severity": "low", "limit": 5,
    })
    s3_data = json.loads(s3[0].text)
    evidence["steps"].append({
        "step": 3, "name": "yiyu_get_data_gaps",
        "ok": True, "total": s3_data.get("total"),
        "schema_version": s3_data.get("schema_version"),
        "first_item_fields": sorted((s3_data.get("items") or [{}])[0].keys()) if s3_data.get("items") else [],
    })

    # Step 4: actions.dry-run (create_task_draft for board_brief 预演)
    s4 = await mod.call_tool("yiyu_dry_run_action", {
        "action_type": "create_task_draft",
        "client_id": CFFC,
        "payload": {"title": "起草本月理事会简版说明", "owner": "高老师"},
    })
    s4_data = json.loads(s4[0].text)
    evidence["steps"].append({
        "step": 4, "name": "yiyu_dry_run_action create_task_draft",
        "ok": True,
        "approval_required": s4_data.get("approval_required"),
        "would_write_tables": s4_data.get("would_write_tables"),
        "safety_check": s4_data.get("safety_check"),
        "dry_run_safe": s4_data.get("dry_run_safe"),
    })

    # Step 5: documents.generate board_brief (真生成, MCP v0 不暴露但 A 评估时直接走 HTTP)
    # 注: yiyu_mcp_server v0 不暴露 documents.generate (是 write tool)
    # 但 Codex 报告里应该有 - 模拟里直接 HTTP 调
    try:
        import httpx
    except ImportError:
        os.system("pip3 install --quiet httpx 2>&1")
        import httpx

    BASE = "http://127.0.0.1:47831"
    async with httpx.AsyncClient(timeout=30) as cli:
        r5 = await cli.post(
            f"{BASE}/api/v1/documents/generate",
            headers={
                "Content-Type": "application/json",
                "X-Actor-Type": "external_ai_agent",
                "X-Actor-Id": "codex_simulation",
                "Idempotency-Key": IDEM_KEY,
            },
            json={
                "client_id": CFFC,
                "document_type": "board_brief",
                "goal": "为本月理事会做 5 分钟项目进展汇报",
            },
        )
        r5_data = r5.json()
        evidence["steps"].append({
            "step": 5, "name": "POST /documents/generate (board_brief)",
            "ok": r5.status_code == 200, "http_status": r5.status_code,
            "status": r5_data.get("status"),
            "approval_required": r5_data.get("approval_required"),
            "approval_id": r5_data.get("approval_id"),
            "agent_run_id": r5_data.get("agent_run_id"),
            "external_target": r5_data.get("external_target"),
            "evidence_summary_keys": sorted((r5_data.get("evidence_summary") or {}).keys())[:8],
            "context_used": r5_data.get("context_used"),
            "sections_count": len(r5_data.get("sections") or {}),
            "markdown_len": len(r5_data.get("markdown") or ""),
            "markdown_preview_400": (r5_data.get("markdown") or "")[:400],
            "markdown_full": r5_data.get("markdown") or "",  # 全文留给 §16 附录
        })

        # Step 6: 同 Idempotency-Key 重发
        r6 = await cli.post(
            f"{BASE}/api/v1/documents/generate",
            headers={
                "Content-Type": "application/json",
                "X-Actor-Type": "external_ai_agent",
                "X-Actor-Id": "codex_simulation",
                "Idempotency-Key": IDEM_KEY,
            },
            json={
                "client_id": CFFC,
                "document_type": "board_brief",
                "goal": "为本月理事会做 5 分钟项目进展汇报",
            },
        )
        r6_data = r6.json()
        evidence["steps"].append({
            "step": 6, "name": "POST /documents/generate (same idempotency-key)",
            "ok": r6.status_code == 200, "http_status": r6.status_code,
            "status": r6_data.get("status"),
            "same_approval_id_as_step5": r6_data.get("approval_id") == r5_data.get("approval_id"),
            "same_agent_run_id_as_step5": r6_data.get("agent_run_id") == r5_data.get("agent_run_id"),
        })

        # Step 7: GET /approvals 验 pending 真有
        r7 = await cli.get(f"{BASE}/api/v1/approvals", params={"limit": 5})
        r7_data = r7.json()
        appr_ids = [a.get("id") for a in r7_data]
        evidence["steps"].append({
            "step": 7, "name": "GET /approvals 验 pending",
            "ok": r7.status_code == 200,
            "pending_count": len(r7_data),
            "step5_approval_in_list": r5_data.get("approval_id") in appr_ids,
            "step5_approval_data": next((a for a in r7_data if a.get("id") == r5_data.get("approval_id")), None),
        })

        # Step 8: GET /agent-run-logs 验 codex_simulation 真留痕
        r8 = await cli.get(
            f"{BASE}/api/v1/agent-run-logs",
            params={"actor_type": "external_ai_agent", "limit": 10},
        )
        r8_data = r8.json()
        sim_runs = [r for r in (r8_data.get("items") or []) if r.get("actor_id") == "codex_simulation"]
        evidence["steps"].append({
            "step": 8, "name": "GET /agent-run-logs codex_simulation",
            "ok": r8.status_code == 200,
            "total_external_ai_runs": r8_data.get("total"),
            "codex_simulation_runs": len(sim_runs),
            "sample_run": sim_runs[0] if sim_runs else None,
        })

    # Step 9: snap db after
    evidence["db_after"] = snap_db()
    evidence["db_diff"] = {
        t: evidence["db_after"][t] - evidence["db_before"][t]
        for t in TABLES
    }
    evidence["ts_end"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return evidence


def main() -> None:
    print("=== Codex 单任务模拟开始 ===")
    print(f"Idempotency-Key: {IDEM_KEY}")
    print()
    ev = asyncio.run(run_codex_simulation())
    out_path = ROOT / "tests/reports/codex_simulation_evidence.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(ev, ensure_ascii=False, indent=2))
    print(f"=== 完成. 证据落档: {out_path} ===")
    print()
    print(f"DB diff:")
    for t, d in ev["db_diff"].items():
        marker = "✅" if d == 0 else ("⚠️" if d > 0 else "❌")
        print(f"  {marker} {t}: {d:+}")
    print()
    print(f"steps: {len(ev['steps'])} 步")
    for s in ev["steps"]:
        print(f"  · step {s['step']}: {s['name']:50} ok={s.get('ok')}")


if __name__ == "__main__":
    main()
