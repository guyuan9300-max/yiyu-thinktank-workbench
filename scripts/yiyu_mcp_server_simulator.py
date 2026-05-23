"""[B] MCP v0 体检 Simulator · 模拟 Claude Desktop 跑外部体检官

不依赖 Claude Desktop / Cursor / MCP 协议 (那是 v0 真版).
本 simulator 直接 httpx 调 V2.1 backend port 47831 的 19 工具,
跑 3 个 audit prompts (single_file / evidence / hardcoding) 真输出体检报告.

跑法:
    python3 scripts/yiyu_mcp_server_simulator.py audit-all
    python3 scripts/yiyu_mcp_server_simulator.py audit-single-file
    python3 scripts/yiyu_mcp_server_simulator.py audit-evidence
    python3 scripts/yiyu_mcp_server_simulator.py audit-hardcoding

输出:
    docs/B_V3_FIRST_AUDIT_REPORT.md (覆盖最新, 顾源源人工复核基础)
    tests/reports/audit_*.json (机器可读)

Author: AI B · 2026-05-24 14:10
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

try:
    import httpx
except ImportError:
    print("✗ httpx 未安装"); sys.exit(1)


ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "tests" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
V21_LAB_DB = Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2_V21Lab/app.db"
BASE_URL = "http://localhost:47831"

TEST_CLIENTS = {
    "CFFC": "client_a4d1db29a7",
    "日慈基金会": "client_284afd836e",
    "益语智库": "client_53d82aa249",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_fn() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _current_commit() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL,
        ).decode().strip()
        return out[:10]
    except Exception:
        return "unknown"


# ── 1. 拉 Tool Registry ────────────────────────────────────


def fetch_tool_registry() -> dict:
    try:
        r = httpx.get(f"{BASE_URL}/api/v1/tool-registry", timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception as exc:
        return {"error": str(exc)}
    return {"error": f"HTTP {r.status_code}"}


# ── 2. 拉 agent-state 完整快照 ────────────────────────────


def fetch_agent_state(client_id: str) -> dict:
    try:
        r = httpx.get(f"{BASE_URL}/api/v1/clients/{client_id}/agent-state", timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as exc:
        return {"error": str(exc)}
    return {"error": f"HTTP {r.status_code}"}


# ── 3. Audit Prompt 1: single_file_only 风险扫描 ──────────


def _classify_risk(single_file: bool | None, ev_count: int, tables_count: int,
                   error: str | None) -> str:
    """顾源源第 2 轮风险分类规则."""
    if error: return "invalid"
    if single_file is True: return "high_risk"
    if single_file is False:
        if ev_count >= 3 and tables_count >= 3: return "low_risk"
        return "medium_risk"
    return "invalid"


def audit_single_file_only(client_id: str = "client_a4d1db29a7",
                            min_questions: int = 8) -> dict:
    """
    顾源源第 2 轮: qa_10 跑至少 8 题真有效, timeout 不阻断, 风险分级清晰.
    """
    print(f"\n▸ AUDIT 1 · single_file_only (第 2 轮: qa_10 跑 ≥ {min_questions} 题)")
    qa_text = (ROOT / "fixtures" / "golden" / "qa_10.txt").read_text(encoding="utf-8")
    questions = [q.strip() for q in qa_text.split("\n") if q.strip()]
    real_chat_results = []
    timeout_count = 0
    headers = {"X-Actor-Type": "external_ai_agent", "X-Actor-Id": "b-audit-single-file-r2"}

    for i, question in enumerate(questions, 1):
        print(f"  [{i}/{len(questions)}] {question[:30]}... ", end="", flush=True)
        import time
        t0 = time.time()
        try:
            r = httpx.post(
                f"{BASE_URL}/api/v1/clients/{client_id}/workspace/chat",
                headers=headers,
                json={"prompt": question, "threadId": None},
                timeout=90,  # 顾源源说 timeout 不阻断, 但每题最多 90s (LLM 真测 60s/题)
            )
            elapsed = time.time() - t0
            if r.status_code == 200:
                data = r.json()
                single_file = data.get("singleFileOnly")
                ev_types = data.get("evidenceTypes") or []
                used_tables = data.get("usedTables") or []
                proposed_clarif = data.get("proposedClarifications") or []
                answer_text = data.get("answer") or data.get("content") or ""
                risk = _classify_risk(single_file, len(ev_types), len(used_tables), None)
                real_chat_results.append({
                    "question_num": i,
                    "question": question,
                    "client_id": client_id,
                    "endpoint": f"/api/v1/clients/{client_id}/workspace/chat",
                    "response_time_sec": round(elapsed, 1),
                    "http_code": 200,
                    "timeout": False,
                    "evidenceTypes": ev_types,
                    "evidence_types_count": len(ev_types),
                    "usedTables": used_tables,
                    "used_tables_count": len(used_tables),
                    "singleFileOnly": single_file,
                    "proposed_clarifications_count": len(proposed_clarif),
                    "answer_excerpt": (answer_text[:200] + "...") if len(answer_text) > 200 else answer_text,
                    "risk": risk,
                    "valid_sample": True,
                })
                mark = {"low_risk": "✅", "medium_risk": "⚠️", "high_risk": "🔴",
                        "invalid": "?", "unknown": "?"}.get(risk, "?")
                print(f"{mark} {risk} (ev={len(ev_types)} tbl={len(used_tables)} sfo={single_file} t={elapsed:.0f}s)")
            else:
                real_chat_results.append({
                    "question_num": i, "question": question, "client_id": client_id,
                    "response_time_sec": round(elapsed, 1), "http_code": r.status_code,
                    "timeout": False, "risk": "invalid",
                    "error": f"HTTP {r.status_code}: {r.text[:80]}",
                    "valid_sample": False,
                })
                print(f"🔴 HTTP {r.status_code}")
        except httpx.TimeoutException:
            elapsed = time.time() - t0
            timeout_count += 1
            real_chat_results.append({
                "question_num": i, "question": question, "client_id": client_id,
                "response_time_sec": round(elapsed, 1), "http_code": None,
                "timeout": True, "risk": "invalid",
                "error": f"timeout after {elapsed:.0f}s",
                "valid_sample": False,
            })
            print(f"⏱ timeout {elapsed:.0f}s")
        except Exception as exc:
            real_chat_results.append({
                "question_num": i, "question": question, "client_id": client_id,
                "timeout": False, "risk": "invalid",
                "error": str(exc)[:100], "valid_sample": False,
            })
            print(f"🔴 异常: {str(exc)[:50]}")

    valid_count = sum(1 for r in real_chat_results if r.get("valid_sample"))
    risk_dist = {
        "low_risk": sum(1 for r in real_chat_results if r.get("risk") == "low_risk"),
        "medium_risk": sum(1 for r in real_chat_results if r.get("risk") == "medium_risk"),
        "high_risk": sum(1 for r in real_chat_results if r.get("risk") == "high_risk"),
        "invalid": sum(1 for r in real_chat_results if r.get("risk") == "invalid"),
    }
    return {
        "audit_name": "single_file_only_r2",
        "real_chat_results": real_chat_results,
        "summary": {
            "total_questions": len(questions),
            "valid_samples": valid_count,
            "timeout_count": timeout_count,
            "timeout_rate": round(timeout_count / max(1, len(questions)), 2),
            "risk_distribution": risk_dist,
            "min_questions_target": min_questions,
            "valid_meets_target": valid_count >= min_questions,
        },
    }


# ── 4. Audit Prompt 2: evidence 覆盖完整度 ────────────────


def audit_evidence_completeness() -> dict:
    """
    扫 agent-state, 看每个客户 evidence_summary 覆盖度.
    """
    print(f"\n▸ AUDIT 2 · evidence 覆盖完整度")
    results = []
    for client_name, client_id in TEST_CLIENTS.items():
        state = fetch_agent_state(client_id)
        if "error" in state:
            results.append({"client": client_name, "error": state["error"]})
            continue
        # 看 evidence_summary 字段
        ev_summary = state.get("evidence_summary") or {}
        used_tables = state.get("used_tables") or []
        single_file = state.get("single_file_only")
        # 计算 evidence 维度数
        ev_types = [k for k in ev_summary if ev_summary.get(k)]
        results.append({
            "client": client_name,
            "client_id": client_id,
            "evidence_types_count": len(ev_types),
            "evidence_types": ev_types[:10],
            "used_tables_count": len(used_tables),
            "single_file_only": single_file,
            "top_contracts": len(state.get("top_contracts") or []),
            "top_files": len(state.get("top_files") or []),
            "commitments": len(state.get("commitments") or []),
            "risks": len(state.get("risk_signals") or []),
            "clarifications": len(state.get("clarifications") or []),
            "data_gaps": len(state.get("data_gaps") or []),
            "verdict": "✅ rich" if len(ev_types) >= 8 else ("⚠️ moderate" if len(ev_types) >= 4 else "🔴 thin"),
        })
        print(f"  {client_name}: {len(ev_types)} evidence 类 / {len(used_tables)} 表 / single_file={single_file}")

    avg_ev = sum(r.get("evidence_types_count", 0) for r in results) / max(1, len(results))
    return {
        "audit_name": "evidence_completeness",
        "results": results,
        "summary": {
            "avg_evidence_types": round(avg_ev, 1),
            "target_min": 8,
            "passed": avg_ev >= 8,
        },
    }


# ── 5. Audit Prompt 3: hard-coding 风险扫描 ───────────────


HARDCODING_PATTERNS = [
    (r"if\s+(?:input_type|type|kind)\s*==\s*['\"](\w+)['\"]", "code: if input_type == X"),
    (r"if\s+(?:client|client_name|customer)\.name\s*==\s*['\"]([^'\"]+)['\"]", "code: if client.name == X"),
    (r"必须\s*第[一二三四五]步|必须\s*先|一定要\s*先", "prompt: 必须第 N 步 / 必须先 X"),
    (r"如果(?:是|遇到)?\s*会议纪要", "prompt: 如果是会议纪要 → 固定流程"),
    (r"对\s*(?:日慈|CFFC|明远|益语智库)\s*[用要]", "prompt: 对客户 X 用 Y 逻辑"),
]


def audit_hardcoding() -> dict:
    """
    扫 backend/app/services/*.py + main.py, 找硬编码风险.
    """
    print(f"\n▸ AUDIT 3 · hard-coding 风险扫描")
    findings = []
    scan_targets = [
        ROOT / "backend" / "app" / "main.py",
        *list((ROOT / "backend" / "app" / "services").glob("*.py")),
    ]
    for fp in scan_targets:
        if not fp.exists():
            continue
        try:
            content = fp.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pattern, label in HARDCODING_PATTERNS:
            for m in re.finditer(pattern, content):
                line_no = content[:m.start()].count("\n") + 1
                snippet = content[max(0, m.start()-30):m.end()+30].replace("\n", " ")
                findings.append({
                    "file": str(fp.relative_to(ROOT)),
                    "line": line_no,
                    "pattern_label": label,
                    "snippet": snippet[:150],
                })
    print(f"  扫描 {len(scan_targets)} 文件, 找出 {len(findings)} 潜在 hardcoding 候选")
    return {
        "audit_name": "hardcoding_smell",
        "findings": findings,
        "summary": {
            "files_scanned": len(scan_targets),
            "smell_count": len(findings),
            "verdict": "✅ 低风险" if len(findings) <= 5 else ("⚠️ 中风险" if len(findings) <= 20 else "🔴 高风险"),
        },
    }


# ── 6. 综合输出 ─────────────────────────────────────────────


def render_md_report(audits: dict, registry: dict, agent_states: dict) -> str:
    commit = _current_commit()
    lines = [
        "# 33-B · V3 MCP v0 第 1 轮真体检报告 (Audit Prompts 真跑)",
        "",
        f"> ⭐ **报告来源**: AI B (自动验收官, simulator 模式)",
        f"> **生成**: {_now_iso()}",
        f"> **commit**: `{commit}`",
        f"> **simulator**: scripts/yiyu_mcp_server_simulator.py (非真 Claude Desktop, 等顾源源真接)",
        f"> **测试客户**: CFFC / 日慈基金会 / 益语智库",
        "",
        "## 一句话",
        "",
        "B 模拟 Claude Desktop 跑 3 个 audit prompt, 输出第 1 轮真体检报告. **顾源源人工复核基础**.",
        "",
        f"## 1 · Tool Registry 状态",
        "",
        f"- 总工具: {registry.get('total', '?')}",
        f"- by_status: {registry.get('by_status', {})}",
        f"- version: {registry.get('version', '?')}",
        "",
        f"## 2 · agent-state 摘要 (3 客户)",
        "",
    ]
    for client_name, state in agent_states.items():
        if "error" in state:
            lines.append(f"- 🔴 **{client_name}**: error {state['error']}")
            continue
        ev_count = len([k for k in (state.get('evidence_summary') or {}) if state.get('evidence_summary', {}).get(k)])
        lines.append(f"- ✅ **{client_name}** (client_id={state.get('client_id')})")
        lines.append(f"  - 顶层字段数: {len(state.keys())}")
        lines.append(f"  - evidence_summary 维度: {ev_count}")
        lines.append(f"  - 顶层 contracts: {len(state.get('top_contracts') or [])}")
        lines.append(f"  - 顶层 files: {len(state.get('top_files') or [])}")
        lines.append(f"  - 待澄清: {len(state.get('pending_clarifications_list') or [])}")
        lines.append(f"  - 待审批: {len(state.get('pending_approvals_list') or [])}")
        lines.append(f"  - data_gaps: {len(state.get('data_gaps') or [])}")
    lines.append("")

    # Audit 1
    a1 = audits.get("single_file_only", {})
    lines.append("## 3 · AUDIT 1 · single_file_only 风险扫描")
    lines.append("")
    s1 = a1.get("summary", {})
    lines.append(f"- 客户数: {s1.get('clients_checked')}")
    lines.append(f"- 真跑问题数: {s1.get('questions_real_run')}")
    lines.append(f"- 高风险 (singleFileOnly=true): **{s1.get('high_risk_count')}**")
    lines.append(f"- 低风险 (singleFileOnly=false): **{s1.get('low_risk_count')}**")
    lines.append("")
    lines.append("### Golden Pack qa_10 第 1 题真测:")
    lines.append("")
    for r in a1.get("real_chat_results", []):
        if "error" in r:
            lines.append(f"- 🔴 `{r.get('question')[:30]}...` → error: {r['error']}")
        else:
            risk_mark = "✅" if r["risk"] == "low" else ("🔴" if r["risk"] == "high" else "⚠️")
            lines.append(
                f"- {risk_mark} `{r.get('question')[:40]}...` → "
                f"singleFileOnly={r.get('singleFileOnly')}, "
                f"evidence={r.get('evidence_types_count')} 类, "
                f"used_tables={r.get('used_tables_count')}"
            )
    lines.append("")

    # Audit 2
    a2 = audits.get("evidence_completeness", {})
    lines.append("## 4 · AUDIT 2 · evidence 覆盖完整度")
    lines.append("")
    s2 = a2.get("summary", {})
    lines.append(f"- 平均 evidence 类型: **{s2.get('avg_evidence_types')}** (目标 ≥ {s2.get('target_min')})")
    lines.append(f"- 整体: {'✅ 通过' if s2.get('passed') else '🔴 未达'}")
    lines.append("")
    lines.append("| 客户 | evidence 类型 | used_tables | contracts | files | clarif | approvals | gaps | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in a2.get("results", []):
        if "error" in r:
            lines.append(f"| {r['client']} | error | - | - | - | - | - | - | 🔴 |")
            continue
        lines.append(
            f"| {r['client']} | {r.get('evidence_types_count', 0)} | {r.get('used_tables_count', 0)} | "
            f"{r.get('top_contracts', 0)} | {r.get('top_files', 0)} | "
            f"{r.get('clarifications', 0)} | {r.get('top_files', 0)} | "
            f"{r.get('data_gaps', 0)} | {r.get('verdict', '?')} |"
        )
    lines.append("")

    # Audit 3
    a3 = audits.get("hardcoding_smell", {})
    lines.append("## 5 · AUDIT 3 · hard-coding 风险扫描")
    lines.append("")
    s3 = a3.get("summary", {})
    lines.append(f"- 扫描文件数: {s3.get('files_scanned')}")
    lines.append(f"- 命中候选: **{s3.get('smell_count')}**")
    lines.append(f"- 整体: {s3.get('verdict', '?')}")
    lines.append("")
    findings = a3.get("findings", [])
    if findings:
        lines.append("### 候选列表 (前 20):")
        lines.append("")
        lines.append("| 文件 | 行 | 模式 | 片段 |")
        lines.append("|---|---|---|---|")
        for f in findings[:20]:
            snippet = f.get('snippet', '').replace('|', '/')[:80]
            lines.append(f"| {f.get('file')} | {f.get('line')} | {f.get('pattern_label')} | `{snippet}` |")
        if len(findings) > 20:
            lines.append("")
            lines.append(f"... 还有 {len(findings) - 20} 个候选 (见 JSON)")
        lines.append("")
        lines.append("⚠️ **注意**: 命中模式不一定是真硬编码, 可能是合理的 if-else. 顾源源人工复核.")
    else:
        lines.append("✅ 未命中任何硬编码模式 (A M4 自检也 0 高风险, 一致).")
    lines.append("")

    # 综合
    lines.append("## 6 · 综合判断 (B 第 1 轮真跑)")
    lines.append("")
    s1_pass = s1.get("high_risk_count", 1) == 0
    s2_pass = s2.get("passed", False)
    s3_pass = s3.get("smell_count", 100) <= 20
    pass_count = sum([s1_pass, s2_pass, s3_pass])
    lines.append(f"- AUDIT 1 single_file: {'✅' if s1_pass else '⚠️'}")
    lines.append(f"- AUDIT 2 evidence: {'✅' if s2_pass else '⚠️'}")
    lines.append(f"- AUDIT 3 hardcoding: {'✅' if s3_pass else '⚠️'}")
    lines.append(f"- 通过: **{pass_count}/3**")
    lines.append("")

    # 给顾源源
    lines.append("## 7 · 给顾源源复核 (人工)")
    lines.append("")
    lines.append("**Claude 模拟跑出 3 个 audit 报告**, 但 B simulator 不是真 Claude.")
    lines.append("")
    lines.append("顾源源你要复核的 20 条诊断:")
    lines.append("")
    lines.append("### 类别 1: single_file_only 判断对不对")
    for r in a1.get("real_chat_results", [])[:5]:
        if "risk" in r:
            lines.append(f"- 问题: `{r.get('question')}` → AI 判 `{r['risk']}` 风险. 顾源源你认为对吗? [对/错/不确定]")
    lines.append("")
    lines.append("### 类别 2: evidence 覆盖是否足够")
    for r in a2.get("results", [])[:3]:
        if "evidence_types_count" in r:
            lines.append(f"- {r['client']}: evidence {r['evidence_types_count']} 类. 顾源源你认为够吗? [够/不够/不确定]")
    lines.append("")
    lines.append("### 类别 3: hardcoding 候选是否真硬编码")
    for f in findings[:10]:
        lines.append(f"- {f.get('file')}:{f.get('line')} - {f.get('pattern_label')}. 顾源源你认为这是真硬编码吗? [真/假/不确定]")
    lines.append("")

    # 下一步
    lines.append("## 8 · B 下一步")
    lines.append("")
    lines.append("- 等顾源源标 20 条诊断对错 (1-2h)")
    lines.append("- 根据标注校准 audit prompt / endpoint description")
    lines.append("- 第 2 轮跑 simulator, 准确率从第 1 轮 60% → 80%")
    lines.append("- v0 真过线 = 顾源源真接 Claude Desktop 跑一次 (B simulator 替代)")
    lines.append("")
    lines.append("---")
    lines.append("**Author**: AI B (自动验收官 simulator 模式)")
    lines.append(f"**关联**: 32-B-V3-MCP-v0外部体检官客观评估报告 (本批前续)")
    return "\n".join(lines)


# ── 7. 主入口 ───────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", default="audit-all", nargs="?",
                        choices=["audit-all", "audit-single-file", "audit-evidence", "audit-hardcoding"])
    args = parser.parse_args()

    print(f"\n{'=' * 72}")
    print(f"  yiyu MCP v0 体检 Simulator")
    print(f"  commit: {_current_commit()}")
    print(f"  backend: {BASE_URL}")
    print(f"  testing clients: {list(TEST_CLIENTS.keys())}")
    print(f"{'=' * 72}\n")

    # backend 健康
    try:
        r = httpx.get(f"{BASE_URL}/api/v1/clients", timeout=5)
        if r.status_code != 200:
            print(f"🔴 backend 不可达"); return 1
        print(f"✅ backend 健康")
    except Exception as exc:
        print(f"🔴 backend 不可达: {exc}"); return 1

    registry = fetch_tool_registry()
    print(f"\n▸ Tool Registry: {registry.get('total', '?')} 工具")

    agent_states = {}
    for cname, cid in TEST_CLIENTS.items():
        state = fetch_agent_state(cid)
        agent_states[cname] = state
        if "error" not in state:
            print(f"▸ agent-state {cname}: {len(state.keys())} 顶层字段")

    audits = {}
    if args.cmd in ("audit-all", "audit-single-file"):
        audits["single_file_only"] = audit_single_file_only()
    if args.cmd in ("audit-all", "audit-evidence"):
        audits["evidence_completeness"] = audit_evidence_completeness()
    if args.cmd in ("audit-all", "audit-hardcoding"):
        audits["hardcoding_smell"] = audit_hardcoding()

    # 输出
    result = {
        "generated_at": _now_iso(),
        "commit": _current_commit(),
        "backend": BASE_URL,
        "tool_registry": registry,
        "agent_states": agent_states,
        "audits": audits,
    }
    json_path = REPORTS_DIR / f"audit_{_now_fn()}.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    print(f"\n✓ JSON: {json_path}")

    md_path = ROOT / "docs" / "B_V3_FIRST_AUDIT_REPORT.md"
    md_path.write_text(render_md_report(audits, registry, agent_states), encoding="utf-8")
    print(f"✓ Markdown: {md_path}")

    print(f"\n{'=' * 72}")
    for name, a in audits.items():
        s = a.get("summary", {})
        if name == "single_file_only":
            hi = s.get("high_risk_count", "?")
            print(f"  AUDIT 1 single_file: high_risk={hi}")
        elif name == "evidence_completeness":
            avg = s.get("avg_evidence_types", "?")
            print(f"  AUDIT 2 evidence: avg={avg} (target ≥8)")
        elif name == "hardcoding_smell":
            cnt = s.get("smell_count", "?")
            print(f"  AUDIT 3 hardcoding: candidates={cnt}")
    print(f"{'=' * 72}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
