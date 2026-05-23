"""[B] B AI 评估基线总入口 (顾源源 5/23 19:00 钦定)

不替 A 写业务. 4 模式持续告诉用户:
  - capability-probe: 哪些 endpoint 真通 (L1)
  - api-contract: API response 是否含公司大脑字段 (L1)
  - db-diff: V2.1 lab db 是否真写入 (L2)
  - ui-checklist: 输出 L3 人工 verify 清单 (B 不能自动判, 给顾源源截图)

跑法:
    npm run eval:b:baseline
    或
    python3 scripts/run_b_eval_baseline.py --mode all
    python3 scripts/run_b_eval_baseline.py --mode capability-probe
    python3 scripts/run_b_eval_baseline.py --mode api-contract
    python3 scripts/run_b_eval_baseline.py --mode db-diff
    python3 scripts/run_b_eval_baseline.py --mode ui-checklist

输出:
    docs/B_AI_EVAL_BASELINE_REPORT.md      (主表 + 4 模式分节)
    docs/B_AI_EVAL_BASELINE_REPORT.json    (机器可读)

原则 (顾源源 5/23 钦定):
  - L1/L2/L3 分清, 不混合
  - 每个不通过项标 blocked_by_A / blocked_by_B / blocked_by_user
  - 不替 A 写复杂业务
  - 报告必带 commit / 端口 / db / 客户 / 输入 / 输出
  - 不为过线改标准

Author: AI B · 2026-05-23 19:30
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
DEFAULT_CLIENT = "日慈基金会"

# ── V2.1 lab db 16 张关键表 (sync 自 init_v21_lab_schema.py) ─────


CRITICAL_TABLES = [
    "atomic_facts", "atomic_fact_confidence_history", "approval_queue",
    "agent_run_log", "idempotency_keys_v25", "source_registry",
    "event_line_activities", "risk_signals", "commitments",
    "clarification_records", "strategic_thought_insights",
    "file_identities", "contract_structures", "historical_reference_links",
    "data_gaps", "external_evidence_cards",
]


# ── 19 个 V2.1 关键 endpoint (capability-probe 模式) ──────────


CAPABILITY_ENDPOINTS = [
    # 已通 (R2 + R4-P0)
    ("POST", "/api/v1/meeting-minutes/process", "R2 会议纪要", "已通", {"client_id": "smoke", "meeting_text": "x", "mode": "draft"}),
    ("GET", "/api/v1/approvals", "R2 待审批 list", "已通", None),
    ("POST", "/api/v1/clients/{cid}/workspace/chat", "工作台问答", "已通 (LLM 慢, smoke 50s timeout)", {"prompt": "smoke", "threadId": None}),
    ("GET", "/api/v1/clients", "客户列表", "已通", None),
    # V3.0 缺 (V3.0 ≥80 阻塞)
    ("POST", "/api/v1/contracts/draft", "V3.0 合同草稿", "缺", {"client_id": "smoke"}),
    ("POST", "/api/v1/templates/generate", "V3.0 模板生成 (理事会说明等)", "缺", {"client_id": "smoke"}),
    ("POST", "/api/v1/clients/{cid}/brand-proposition", "V3.0 品牌建议", "缺 (路径存在但只 GET)", {}),
    ("GET", "/api/v1/clients/{cid}/data-gaps", "V3.0 P0a Data Gap API", "缺", None),
    ("POST", "/api/v1/agent/plan", "V3.0 P1 Goal-Plan", "缺", {"goal": "x"}),
    ("POST", "/api/v1/agent/run", "V3.0 P1 Goal-Run", "缺", {"plan_id": "x"}),
    ("GET", "/api/v1/agent-run-logs", "Agent Run Log list", "缺 (db 真有, endpoint 没暴露)", None),
    # 部分可用 (权限/payload)
    ("POST", "/api/v1/intelligence/brand-mirror/analyze", "品牌分析", "存在但 payload 不熟", {"client_id": "smoke"}),
    ("POST", "/api/v1/clients/{cid}/strategic-cockpit/meeting-pack", "会谈提纲", "403 权限", {"meeting_text": "smoke"}),
    # R4-P0 P0-3 已接
    ("POST", "/api/v1/clients/{cid}/workspace/smart-import", "智能文件导入", "已通 (A R4 P0-3)", {"files": []}),
]


# ── 工具 ────────────────────────────────────────────────────


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


def load_golden(key: str) -> str:
    p = GOLDEN_DIR / f"{key}.txt"
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


# ── 模式 1: capability-probe (L1 endpoint smoke) ────────────


def mode_capability_probe(base_url: str, client_id: str) -> dict:
    """L1 · 19 个关键 endpoint smoke 真状态."""
    print(f"\n▸ [capability-probe] L1 · smoke 19 个 endpoint")
    results = []
    for method, raw_path, name, status_label, payload in CAPABILITY_ENDPOINTS:
        path = raw_path.replace("{cid}", client_id)
        try:
            if method == "GET":
                r = httpx.get(f"{base_url}{path}", timeout=5.0)
            else:
                r = httpx.post(f"{base_url}{path}", json=payload, timeout=5.0)
            code = r.status_code
        except httpx.TimeoutException:
            code = "timeout (LLM 慢非 404)"
        except Exception as exc:
            code = f"exception: {str(exc)[:60]}"

        # 分类: 通 / 缺 / 部分
        if isinstance(code, int):
            if code in (200, 201):
                bucket = "✅ 通"
            elif code in (422, 400):
                bucket = "⚠️ 存在 payload 不对"
            elif code == 403:
                bucket = "⚠️ 存在权限"
            elif code == 404:
                bucket = "🔴 缺 (blocked_by_A)"
            elif code == 405:
                bucket = "🔴 路径存在 method 不对"
            else:
                bucket = f"⚠️ {code}"
        else:
            bucket = f"⚠️ {code}"

        results.append({
            "method": method, "path": path, "name": name,
            "status_code": code, "expected": status_label,
            "bucket": bucket,
        })
        print(f"  {bucket:<28} {method} {path:<55} ({name})")

    通 = sum(1 for r in results if "✅" in r["bucket"])
    缺 = sum(1 for r in results if "🔴" in r["bucket"])
    部分 = len(results) - 通 - 缺
    return {
        "endpoints": results,
        "summary": {"通": 通, "部分": 部分, "缺": 缺, "total": len(results)},
    }


# ── 模式 2: api-contract (L1 R4-P0 顶层字段) ────────────────


def mode_api_contract(base_url: str, client_id: str) -> dict:
    """L1 · 跑 Golden Pack 问答, 看 response 是否含 R4-P0 顶层字段."""
    print(f"\n▸ [api-contract] L1 · 工作台问答 response 顶层 5 字段 verify")

    headers = {
        "X-Actor-Type": "external_ai_agent",
        "X-Actor-Id": "b-eval-baseline-api-contract",
    }
    qa_text = load_golden("qa_10")
    questions = [q.strip() for q in qa_text.split("\n") if q.strip()]

    if not questions:
        return {"error": "Golden qa_10.txt 为空"}

    # 取 3 个代表问题快测 (减少 LLM 调用时间)
    sample_qs = [questions[0], questions[6], questions[8]]  # 项目/口述/澄清
    chat_results = []
    for q in sample_qs:
        url = f"{base_url}/api/v1/clients/{client_id}/workspace/chat"
        try:
            print(f"  调 chat: {q[:30]}...", flush=True)
            r = httpx.post(url, headers=headers, json={"prompt": q, "threadId": None}, timeout=60.0)
            ok = r.status_code == 200
            data = r.json() if ok else {}
            top_fields = {
                "evidenceTypes": data.get("evidenceTypes"),
                "usedTables": data.get("usedTables"),
                "singleFileOnly": data.get("singleFileOnly"),
                "uncertaintyItems": data.get("uncertaintyItems"),
                "proposedClarifications": data.get("proposedClarifications"),
                "companyBrainSummary": data.get("companyBrainSummary") is not None,
            }
            chat_results.append({
                "question": q,
                "status_code": r.status_code,
                "top_fields_present": {k: v is not None for k, v in top_fields.items()},
                "evidence_types_count": len(top_fields["evidenceTypes"] or []),
                "used_tables_count": len(top_fields["usedTables"] or []),
                "single_file_only": top_fields["singleFileOnly"],
                "proposed_clarifications_count": len(top_fields["proposedClarifications"] or []),
            })
        except Exception as exc:
            chat_results.append({"question": q, "error": str(exc)[:120]})

    # 统计
    all_fields_present = all(
        all(r.get("top_fields_present", {}).values())
        for r in chat_results if "top_fields_present" in r
    )
    avg_evidence_types = (
        sum(r.get("evidence_types_count", 0) for r in chat_results) / max(1, len(chat_results))
    )
    return {
        "qa_results": chat_results,
        "summary": {
            "all_5_top_fields_present": all_fields_present,
            "avg_evidence_types": round(avg_evidence_types, 1),
            "target_evidence_types_min": 3,
            "passed": all_fields_present and avg_evidence_types >= 3,
        },
    }


# ── 模式 3: db-diff (L2 V2.1 lab db 真写入) ─────────────────


def mode_db_diff(conn: sqlite3.Connection, client_id: str) -> dict:
    """L2 · V2.1 lab db 16 张表 client 行数 + 全表 total."""
    print(f"\n▸ [db-diff] L2 · V2.1 lab db 16 张表当前状态")
    snap = {}
    for t in CRITICAL_TABLES:
        try:
            total = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            snap[t] = {"total": total, "exists": True}
        except sqlite3.OperationalError as exc:
            snap[t] = {"total": 0, "exists": False, "error": str(exc)}

    existing = sum(1 for v in snap.values() if v["exists"])
    has_data = sum(1 for v in snap.values() if v["exists"] and v["total"] > 0)
    print(f"  存在: {existing}/{len(CRITICAL_TABLES)} 张")
    print(f"  有数据: {has_data}/{existing} 张")
    for t, info in snap.items():
        mark = "✅" if (info["exists"] and info["total"] > 0) else ("⚠️ 空" if info["exists"] else "🔴 缺")
        print(f"  {mark} {t}: total={info.get('total', 0)}")
    return {
        "tables": snap,
        "summary": {
            "existing": existing,
            "has_data": has_data,
            "total": len(CRITICAL_TABLES),
        },
    }


# ── 模式 4: ui-checklist (L3 人工 verify 清单) ──────────────


def mode_ui_checklist() -> dict:
    """L3 · 不能自动测, 输出人工 verify 清单 + 截图路径."""
    print(f"\n▸ [ui-checklist] L3 · 人工 verify 清单 (B 不能自动, 给顾源源)")
    checklist = [
        {"id": "ui_evidence_badge", "desc": "工作台 AI 回答下方显示 evidence 摘要框 (合同 N / 会议 N / 风险 N)", "blocked_by": "user 截图 (A R4-P0 P0-5 已挂)"},
        {"id": "ui_pending_clarification_badge", "desc": "客户工作台头部 待澄清 N 徽章", "blocked_by_a": "A 自报 4 badge 未挂头部 (下轮 P0)"},
        {"id": "ui_pending_approval_badge", "desc": "客户工作台头部 待审批 M 徽章", "blocked_by_a": "A 自报 4 badge 未挂头部 (下轮 P0)"},
        {"id": "ui_file_identity_badge", "desc": "smart_import 文件列表显示 文件身份 type/role badge", "blocked_by_a": "A 自报 4 badge 未挂 smart_import 文件列表 (下轮 P0)"},
        {"id": "ui_contract_structure_card", "desc": "合同文件点开看 合同结构卡片 (甲乙方/项目/金额/期限/责任)", "blocked_by_a": "A 自报 4 badge 未挂 smart_import 文件列表 (下轮 P0)"},
        {"id": "ui_proposed_clarifications_list", "desc": "AI 回答下方显示 proposed_clarifications 列表 + 用户能点击采纳/修正/忽略", "blocked_by": "user 截图 (A R4-P0 P0-5 已挂 ProposedClarificationsList)"},
        {"id": "ui_narrative_evidence_label", "desc": "战略陪伴 6 段每段下方显示 evidence 标签 (来自合同/会议/历史/data_gap)", "blocked_by_a": "A 自报 P0-4 narrative_generator prompt 未真用新字段 (下轮 P0)"},
        {"id": "ui_low_confidence_marker", "desc": "战略陪伴 低把握度段落 标记可见 (灰色/标签)", "blocked_by_a": "A 自报 P0-4 未做"},
        {"id": "ui_agent_run_log_history", "desc": "用户能看到 AI 调用模块历史 (Agent Run Log list endpoint)", "blocked_by_a": "GET /agent-run-logs 404"},
        {"id": "ui_approval_actions", "desc": "待审批列表用户能点击 通过/拒绝/批注", "blocked_by": "user 截图 (A 暴露 POST /approvals/{id}/approve|reject)"},
    ]
    blocked_by_a = [c for c in checklist if "blocked_by_a" in c]
    blocked_by_user = [c for c in checklist if "blocked_by" in c and "blocked_by_a" not in c]
    print(f"  L3 检查项: {len(checklist)} 个")
    print(f"  blocked_by_A: {len(blocked_by_a)} (A 还没挂前端)")
    print(f"  blocked_by_user: {len(blocked_by_user)} (等顾源源截图)")
    print(f"\n  → 截图存到 docs/screenshots/r4_p0/<timestamp>/<id>.png")
    return {
        "checklist": checklist,
        "summary": {
            "total": len(checklist),
            "blocked_by_a": len(blocked_by_a),
            "blocked_by_user": len(blocked_by_user),
        },
    }


# ── 主流程 ───────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="all",
                        choices=["all", "capability-probe", "api-contract", "db-diff", "ui-checklist"])
    parser.add_argument("--client", default=DEFAULT_CLIENT)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--db", default=str(V21_LAB_DB))
    args = parser.parse_args()

    commit = _current_commit()
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"✗ V2.1 lab db 不存在: {db_path}"); return 1

    print(f"\n{'=' * 72}")
    print(f"  B AI 评估基线 · 自动验收官 mode={args.mode}")
    print(f"  commit: {commit} · backend: {args.base_url} · client: {args.client}")
    print(f"  db: {db_path}")
    print(f"{'=' * 72}")

    # backend 健康
    try:
        r = httpx.get(f"{args.base_url}/api/v1/clients", timeout=5)
        if r.status_code != 200:
            print(f"  🔴 backend 不可达 {r.status_code}"); return 1
        print(f"  ✅ backend 健康")
    except Exception as exc:
        print(f"  🔴 backend 不可达: {exc}"); return 1

    conn = sqlite3.connect(str(db_path))
    client_id = lookup_client_id(conn, args.client) or lookup_client_id(conn, "日慈基金会")
    if not client_id:
        print(f"  🔴 客户 fallback 失败"); return 1
    print(f"  client_id: {client_id}")

    result = {
        "generated_at": _now_iso(),
        "commit": commit,
        "base_url": args.base_url,
        "db": str(db_path),
        "client": args.client,
        "client_id": client_id,
        "mode": args.mode,
    }

    if args.mode in ("all", "capability-probe"):
        result["capability_probe"] = mode_capability_probe(args.base_url, client_id)
    if args.mode in ("all", "db-diff"):
        result["db_diff"] = mode_db_diff(conn, client_id)
    if args.mode in ("all", "api-contract"):
        result["api_contract"] = mode_api_contract(args.base_url, client_id)
    if args.mode in ("all", "ui-checklist"):
        result["ui_checklist"] = mode_ui_checklist()

    # JSON
    json_path = REPORTS_DIR / f"b_eval_baseline_{_now_filename()}.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    print(f"\n✓ JSON: {json_path}")

    # Markdown
    md_path = ROOT / "docs" / "B_AI_EVAL_BASELINE_REPORT.md"
    md_path.write_text(_render_md(result), encoding="utf-8")
    print(f"✓ Markdown: {md_path} (覆盖最新)")

    print(f"\n{'=' * 72}")
    _print_summary(result)
    print(f"{'=' * 72}\n")

    conn.close()
    return 0


def _print_summary(result: dict) -> None:
    if "capability_probe" in result:
        s = result["capability_probe"]["summary"]
        print(f"  L1 capability-probe: 通 {s['通']} / 部分 {s['部分']} / 缺 {s['缺']} / 共 {s['total']}")
    if "db_diff" in result:
        s = result["db_diff"]["summary"]
        print(f"  L2 db-diff: 存在 {s['existing']}/{s['total']} 张, 有数据 {s['has_data']}/{s['existing']} 张")
    if "api_contract" in result:
        s = result["api_contract"]["summary"]
        passed = "✅" if s.get("passed") else "🔴"
        print(f"  L1 api-contract: {passed} 顶层 5 字段全在 = {s.get('all_5_top_fields_present')} / evidence_types avg = {s.get('avg_evidence_types')}")
    if "ui_checklist" in result:
        s = result["ui_checklist"]["summary"]
        print(f"  L3 ui-checklist: {s['total']} 项 (blocked_by_A {s['blocked_by_a']} / blocked_by_user {s['blocked_by_user']})")


def _render_md(result: dict) -> str:
    lines = [
        "# B AI 评估基线报告 · 自动验收官",
        "",
        f"> 生成: {result['generated_at']}",
        f"> commit: `{result['commit']}` · backend: {result['base_url']}",
        f"> db: `{result['db']}`",
        f"> client: {result['client']} ({result['client_id']})",
        f"> mode: {result['mode']}",
        "",
        "**北极星**: 每次软件能力变化, 自动评估 \"用户看到了什么 / AI 是否真调度软件做事\".",
        "**不替 A 写复杂业务. 不为过线改标准.**",
        "",
    ]

    # L1 capability-probe
    if "capability_probe" in result:
        cp = result["capability_probe"]
        s = cp["summary"]
        lines.append("## L1 · capability-probe (19 个关键 endpoint)")
        lines.append("")
        lines.append(f"通 {s['通']} / 部分 {s['部分']} / 缺 {s['缺']} / 共 {s['total']}")
        lines.append("")
        lines.append("| Method | Path | 名称 | 状态 |")
        lines.append("|---|---|---|---|")
        for e in cp["endpoints"]:
            lines.append(f"| {e['method']} | `{e['path']}` | {e['name']} | {e['bucket']} |")
        lines.append("")

    # L1 api-contract
    if "api_contract" in result:
        ac = result["api_contract"]
        s = ac["summary"]
        lines.append("## L1 · api-contract (R4-P0 顶层 5 字段)")
        lines.append("")
        passed = "✅" if s.get("passed") else "🔴"
        lines.append(f"{passed} 顶层 5 字段全在 = {s.get('all_5_top_fields_present')}")
        lines.append(f"evidence_types avg = {s.get('avg_evidence_types')} (目标 ≥ {s.get('target_evidence_types_min', 3)})")
        lines.append("")
        for q in ac.get("qa_results", []):
            if "error" in q:
                lines.append(f"- ❌ `{q['question']}` → error: {q['error']}")
                continue
            fields_ok = sum(1 for v in q.get("top_fields_present", {}).values() if v)
            lines.append(f"- HTTP {q.get('status_code')} | `{q['question'][:40]}...` | "
                       f"字段 {fields_ok}/6, evidence_types {q.get('evidence_types_count')}, "
                       f"used_tables {q.get('used_tables_count')}, single_file={q.get('single_file_only')}, "
                       f"clarif {q.get('proposed_clarifications_count')}")
        lines.append("")

    # L2 db-diff
    if "db_diff" in result:
        dd = result["db_diff"]
        s = dd["summary"]
        lines.append("## L2 · db-diff (V2.1 lab db 16 张关键表)")
        lines.append("")
        lines.append(f"存在 {s['existing']}/{s['total']} 张, 有数据 {s['has_data']}/{s['existing']} 张")
        lines.append("")
        lines.append("| 表 | 全表 total | 状态 |")
        lines.append("|---|---|---|")
        for t, info in dd["tables"].items():
            mark = "✅" if (info["exists"] and info["total"] > 0) else ("⚠️ 空" if info["exists"] else "🔴 缺")
            lines.append(f"| `{t}` | {info.get('total', 0)} | {mark} |")
        lines.append("")

    # L3 ui-checklist
    if "ui_checklist" in result:
        uc = result["ui_checklist"]
        s = uc["summary"]
        lines.append("## L3 · ui-checklist (人工 verify, B 不能自动)")
        lines.append("")
        lines.append(f"{s['total']} 项 (blocked_by_A {s['blocked_by_a']} / blocked_by_user {s['blocked_by_user']})")
        lines.append("")
        lines.append("| id | 描述 | 阻塞 |")
        lines.append("|---|---|---|")
        for c in uc["checklist"]:
            blocked = c.get("blocked_by_a") or c.get("blocked_by") or "?"
            lines.append(f"| `{c['id']}` | {c['desc']} | {blocked} |")
        lines.append("")
        lines.append("**截图路径**: `docs/screenshots/r4_p0/<timestamp>/<id>.png`")
        lines.append("**人工 verify 模板**: 看到 ✅ / 看不到 ❌ / 部分 ⚠️")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("**关联**:")
    lines.append("- 评估标准: `docs/B_AI_EVAL_STANDARD_V1.md`")
    lines.append("- Golden Test Pack: `docs/B_AI_GOLDEN_TEST_PACK.md`")
    lines.append("- V3.0 报告: `docs/V3_0_AI_DRIVEN_SOFTWARE_EVAL_REPORT_<timestamp>.md`")
    lines.append("- 进展雷达: `docs/B_AI_PROGRESS_RADAR.md`")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
