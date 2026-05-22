"""[B] M-G · 双层 L1+L2 baseline runner

服务: docs/B_AI_SYNC_20260522_M_G_EVALUATOR_AUTOMATION.md
触发: B K-3 异议 4 "双层 eval 避免 L1/L2 bug 互相掩盖" 顾源源已采纳

L1 = atomic_facts 抽取层 eval (LLM extractor 抽的 fact 对不对)
L2 = 6 段叙事拼合层 eval (collector + generator 拼的对不对)

为什么必须双层 (K-3 异议 4):
- 单 L2 命中低: 可能 collector 漏拉, 也可能 LLM 抽漏, 两种 bug 互相掩盖
- L1 + L2 同时跑:
  · L1 高 L2 低 → collector / generator 问题 (atomic_facts 有但没被拼上)
  · L1 低 L2 低 → LLM extractor / 入库链路问题
  · L1 高 L2 高 → PASS

数据基础: prod db copy 到 tmp, 不污染本机.
入口: 跟 dogfood 一致 (collect_client_fact_bundle + generate_narrative_dimensions).
跑法:
    cd ~/openclaw/workspace/V2.1
    ~/openclaw/workspace/yiyu-thinktank-workbench/backend/.venv/bin/python3 \\
        scripts/run_v22_dual_layer_baseline.py [client_name=日慈基金会]

输出:
- JSON: tests/reports/dual_layer_baseline_<timestamp>.json
- Markdown: docs/AUTO_EVAL_LATEST.md (覆盖, 含历史对比)
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# V2.1 backend 优先 (A 5/22 autonomous loop 在 V2.1 改了 narrative_generator/collector/extractor)
# 顾源源红线: V2.1 改的不污染主仓库, 但 baseline 必须测 V2.1 真实效果
# 跟 scripts/run_v22_dogfood_6dim_baseline.py 同 sys.path 策略 (A M-C.1 修过, f5dde56)
MAIN_REPO = Path.home() / "openclaw/workspace/yiyu-thinktank-workbench"
sys.path.insert(0, str(ROOT / "backend"))   # ★ V2.1 backend 第一优先
sys.path.insert(0, str(ROOT))
sys.path.append(str(MAIN_REPO / "backend"))  # fallback (V2.1 没的从主仓库取)
sys.path.append(str(MAIN_REPO))

REPORTS_DIR = ROOT / "tests" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
AUTO_EVAL_MD = ROOT / "docs" / "AUTO_EVAL_LATEST.md"

PROD_DB = Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2/app.db"
DEFAULT_CLIENT_NAME = "日慈基金会"

# 5/19 张真会议 7 道金标准 (跟 dogfood 一致, V2.2 阶段唯一 dataset)
GOLDEN_KEYWORDS_5_19 = [
    "法人",
    "理事长",
    "强哥",
    "秘书长",
    "兴盛",
    "心理魔法学院",
    "安心妈妈",
]

# 命中阈值 (sync 指令 §2.4)
L1_PASS_THRESHOLD = 70.0  # %
L2_PASS_THRESHOLD = 70.0
L2_PARTIAL_THRESHOLD = 50.0


# ── L1 命中: 查 atomic_facts 表 ─────────────────────────


def measure_l1_atomic_facts(
    db_conn: sqlite3.Connection,
    client_id: str,
    keywords: list[str],
) -> dict:
    """L1 eval: atomic_facts 层是否有 7 个金标准关键词.

    每关键词跑 SQL:
        SELECT COUNT(*) FROM atomic_facts
        WHERE client_id = ?
          AND status = 'active'
          AND validity_status != 'superseded'
          AND (subject_text LIKE ? OR attribute LIKE ? OR value_text LIKE ?)

    命中 = COUNT > 0.
    """
    by_keyword: dict[str, int] = {}
    for kw in keywords:
        pat = f"%{kw}%"
        row = db_conn.execute(
            """
            SELECT COUNT(*) AS n FROM atomic_facts
            WHERE client_id = ?
              AND status = 'active'
              AND validity_status != 'superseded'
              AND (subject_text LIKE ? OR attribute LIKE ? OR value_text LIKE ?)
            """,
            (client_id, pat, pat, pat),
        ).fetchone()
        by_keyword[kw] = int(row["n"] if hasattr(row, "keys") else row[0])
    hits = sum(1 for v in by_keyword.values() if v > 0)
    pct = round(hits / len(keywords) * 100, 1)
    return {
        "level": "atomic_facts",
        "pct": pct,
        "hits": hits,
        "total": len(keywords),
        "by_keyword": by_keyword,
    }


# ── L2 命中: 跑 6 段叙事 → keyword 匹配 ─────────────────


def measure_l2_narrative(
    ai_service,
    db,
    client_id: str,
    keywords: list[str],
) -> dict:
    """L2 eval: 战略陪伴 6 段叙事最终输出里是否有 7 个金标准关键词.

    复用 dogfood 同链路:
        collect_client_fact_bundle(db, client_id) → bundle
        generate_narrative_dimensions(ai, bundle, db=db) → (dims, overall, model)

    命中 = 关键词在任一段 body_markdown 出现.
    """
    from app.services.narrative_collector import collect_client_fact_bundle
    from app.services.narrative_generator import generate_narrative_dimensions

    bundle = collect_client_fact_bundle(db, client_id)
    dims, overall, model_used = generate_narrative_dimensions(
        ai_service, bundle, db=db, enable_clarification_pre_search=False,
    )

    all_narrative_text = "\n".join(
        str(d.get("narrative", "") if isinstance(d, dict) else "")
        for d in dims.values()
    )

    by_keyword: dict[str, int] = {}
    for kw in keywords:
        by_keyword[kw] = all_narrative_text.count(kw)
    hits = sum(1 for v in by_keyword.values() if v > 0)
    pct = round(hits / len(keywords) * 100, 1)
    return {
        "level": "narrative_6_dim_output",
        "pct": pct,
        "hits": hits,
        "total": len(keywords),
        "by_keyword": by_keyword,
        "model_used": model_used,
        "overall_confidence": round(overall, 3),
        "dims_count": len(dims),
    }


# ── diagnosis (双层综合判决, sync 指令 §2.4) ───────────


def diagnose(l1_pct: float, l2_pct: float) -> str:
    """根据 L1/L2 数字给出诊断 + 修复建议路径"""
    if l1_pct < L1_PASS_THRESHOLD and l2_pct < L1_PASS_THRESHOLD:
        return (
            "🔴 L1+L2 都低 → 系统性问题. "
            "排查全链路: ingest_pipeline → document_llm_extractor → "
            "narrative_collector → narrative_generator"
        )
    if l1_pct < L1_PASS_THRESHOLD:
        return (
            "🔴 L1 低 (atomic_facts 没抽到) → "
            "LLM extractor 或入库链路问题. "
            "查 ingest_pipeline + document_llm_extractor + "
            "smart_file_import (是否走 IngestPipeline)"
        )
    if l2_pct < L2_PARTIAL_THRESHOLD:
        return (
            "🟡 L1 高但 L2 低 (atomic_facts 有但没拼上) → "
            "collector 漏拉 或 generator prompt 没用上. "
            "查 narrative_collector + narrative_generator"
        )
    if l2_pct < L2_PASS_THRESHOLD:
        return (
            "🟡 L1 高 L2 部分高 (collector 拉了但 generator 没全融入). "
            "查 generator prompt 是否引导 LLM 引用对应 fact"
        )
    return "🟢 PASS — L1 + L2 都高, atomic_facts 有, 6 段也讲到"


# ── 历史对比 (扫 tests/reports/*.json) ────────────────


def collect_history(current_l1: float, current_l2: float, max_rows: int = 5) -> list[dict]:
    """从 tests/reports/dual_layer_baseline_*.json 收集历史 P% 对比"""
    history: list[dict] = []
    for jf in sorted(REPORTS_DIR.glob("dual_layer_baseline_*.json"), reverse=True)[:max_rows]:
        try:
            d = json.loads(jf.read_text())
            history.append({
                "generated_at": d.get("generated_at", ""),
                "L1_pct": d.get("L1", {}).get("pct"),
                "L2_pct": d.get("L2", {}).get("pct"),
                "trigger": d.get("trigger_summary", ""),
            })
        except Exception:
            continue
    return history


# ── markdown 报告 ─────────────────────────────────────


def render_markdown(report: dict, history: list[dict]) -> str:
    lines: list[str] = []
    lines.append(f"# 自动 eval · 双层 L1+L2 baseline · {report['client_name']}")
    lines.append("")
    lines.append(
        f"> 生成: {report['generated_at']} · "
        f"耗时 {report['duration_seconds']:.0f}s · "
        f"trigger: {report.get('trigger_summary', '(manual)')}"
    )
    lines.append(f"> client_id: `{report['client_id']}`")
    lines.append(f"> dataset: 5/19 张真会议 7 关键词 (V2.2 阶段唯一 dataset)")
    lines.append("")

    lines.append("## L1 vs L2 命中对比")
    lines.append("")
    lines.append("| 维度 | 命中 | P% | 含义 |")
    lines.append("|---|---|---|---|")
    lines.append(
        f"| **L1** atomic_facts | {report['L1']['hits']}/{report['L1']['total']} | "
        f"**{report['L1']['pct']:.1f}%** | LLM extractor 抽到 + IngestPipeline 入库 |"
    )
    lines.append(
        f"| **L2** 6 段叙事 | {report['L2']['hits']}/{report['L2']['total']} | "
        f"**{report['L2']['pct']:.1f}%** | 用户在战略陪伴看到的内容 |"
    )
    lines.append("")

    lines.append("## 诊断")
    lines.append("")
    lines.append(report.get("diagnosis", ""))
    lines.append("")

    lines.append("## 7 关键词逐项 (L1 vs L2)")
    lines.append("")
    lines.append("| 关键词 | L1 atomic_facts 计数 | L2 6 段叙事计数 | L1 命中? | L2 命中? |")
    lines.append("|---|---|---|---|---|")
    for kw in GOLDEN_KEYWORDS_5_19:
        l1_n = report["L1"]["by_keyword"].get(kw, 0)
        l2_n = report["L2"]["by_keyword"].get(kw, 0)
        l1_mark = "✓" if l1_n > 0 else "✗"
        l2_mark = "✓" if l2_n > 0 else "✗"
        lines.append(f"| {kw} | {l1_n} | {l2_n} | {l1_mark} | {l2_mark} |")
    lines.append("")

    lines.append("## 历史对比 (last 5 runs)")
    lines.append("")
    if history:
        lines.append("| 时间 | L1 P% | L2 P% | trigger |")
        lines.append("|---|---|---|---|")
        for h in history:
            lines.append(
                f"| {h['generated_at'][:19]} | "
                f"{h.get('L1_pct', '-'):.1f}% | "
                f"{h.get('L2_pct', '-'):.1f}% | "
                f"{h.get('trigger', '-')} |"
            )
    else:
        lines.append("_(首次跑, 没历史)_")
    lines.append("")

    lines.append("## 元信息")
    lines.append("")
    lines.append(f"- model_used: `{report['L2'].get('model_used', '?')}`")
    lines.append(f"- overall_confidence: `{report['L2'].get('overall_confidence', '?')}`")
    lines.append(f"- 6 段生成数量: {report['L2'].get('dims_count', 0)}")
    lines.append(f"- atomic_facts 客户行数: {report.get('atomic_facts_total', '?')}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "**触发**: 跑 `python3 scripts/run_v22_dual_layer_baseline.py [client_name]` "
        "或 git post-commit hook 自动触发 (改 ingest/collector/generator/extractor)."
    )
    lines.append("")
    lines.append(
        "**修 bug 路径**: 查 diagnosis 章节给的提示."
    )
    return "\n".join(lines)


# ── 主流程 ────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_filename() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def main() -> int:
    client_name = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CLIENT_NAME
    trigger_summary = sys.argv[2] if len(sys.argv) > 2 else "manual"

    print(f"\n{'=' * 72}")
    print(f"  [B] M-G · 双层 L1+L2 baseline runner")
    print(f"  客户: {client_name} · trigger: {trigger_summary}")
    print(f"  prod db: {PROD_DB}")
    print(f"{'=' * 72}\n")

    if not PROD_DB.exists():
        print(f"✗ prod db 不存在: {PROD_DB}")
        return 1

    started = time.perf_counter()
    report: dict = {
        "generated_at": _now_iso(),
        "client_name": client_name,
        "client_id": "",
        "dataset_version": "5/19 张真会议 7 关键词",
        "trigger_summary": trigger_summary,
        "L1": {},
        "L2": {},
        "diagnosis": "",
        "atomic_facts_total": 0,
        "duration_seconds": 0.0,
        "errors": [],
        "tmp_data_dir": "",
    }

    try:
        # ─── Phase 1: 复制 prod db 到 tmp ───
        print("▸ 1/5 复制 prod db 到 tmp...", flush=True)
        tmp_dir = Path(tempfile.mkdtemp(prefix="dual_layer_"))
        data_dir = tmp_dir / "data"
        data_dir.mkdir()
        shutil.copy(PROD_DB, data_dir / "app.db")
        for ext in ("-wal", "-shm"):
            wal = data_dir / f"app.db{ext}"
            if wal.exists():
                wal.unlink()
        report["tmp_data_dir"] = str(tmp_dir)
        print(f"  ✓ tmp data_dir: {data_dir}", flush=True)

        # ─── Phase 2: 起 FastAPI app ───
        print("▸ 2/5 起 FastAPI app (30-60 秒 migrations)...", flush=True)
        from fastapi.testclient import TestClient
        from app.main import create_app

        app = create_app(data_dir)
        test_client = TestClient(app)
        test_client.__enter__()
        state = app.state.app_state  # type: ignore[attr-defined]
        db = state.db
        ai = state.ai

        # 找 client_id
        client_row = db.fetchone(
            "SELECT id, name FROM clients WHERE name LIKE ? LIMIT 1",
            (f"%{client_name}%",),
        )
        if not client_row:
            print(f"✗ 找不到客户: {client_name}")
            test_client.__exit__(None, None, None)
            return 1
        report["client_id"] = str(client_row["id"])
        print(f"  ✓ client_id={report['client_id'][:24]}.. ", flush=True)

        # ─── Phase 3: L1 (atomic_facts 层) ───
        print("▸ 3/5 L1 atomic_facts 层命中检查...", flush=True)
        raw_conn = sqlite3.connect(str(data_dir / "app.db"))
        raw_conn.row_factory = sqlite3.Row
        try:
            report["L1"] = measure_l1_atomic_facts(
                raw_conn, report["client_id"], GOLDEN_KEYWORDS_5_19,
            )
            total_row = raw_conn.execute(
                "SELECT COUNT(*) AS n FROM atomic_facts WHERE client_id = ?",
                (report["client_id"],),
            ).fetchone()
            report["atomic_facts_total"] = int(total_row["n"])
        finally:
            raw_conn.close()

        l1_pct = report["L1"]["pct"]
        print(f"  ✓ L1 P% = {l1_pct:.1f}% ({report['L1']['hits']}/7)", flush=True)
        for kw, n in report["L1"]["by_keyword"].items():
            marker = "✓" if n > 0 else "✗"
            print(f"    {marker} {kw}: {n} 条", flush=True)

        # ─── Phase 4: L2 (6 段叙事层) ───
        print("▸ 4/5 L2 6 段叙事层命中检查 (调 LLM, 1-5 分钟)...", flush=True)
        report["L2"] = measure_l2_narrative(
            ai, db, report["client_id"], GOLDEN_KEYWORDS_5_19,
        )
        l2_pct = report["L2"]["pct"]
        print(f"  ✓ L2 P% = {l2_pct:.1f}% ({report['L2']['hits']}/7)", flush=True)

        test_client.__exit__(None, None, None)

        # ─── Phase 5: diagnosis ───
        print("▸ 5/5 综合诊断...", flush=True)
        report["diagnosis"] = diagnose(l1_pct, l2_pct)
        print(f"  → {report['diagnosis']}", flush=True)

    except Exception as exc:
        tb = traceback.format_exc()
        report["errors"].append(f"{exc}\n{tb[-2000:]}")
        print(f"\n✗ 出错:\n{tb[-2000:]}", flush=True)
        return 1
    finally:
        report["duration_seconds"] = time.perf_counter() - started

    # ─── 写 JSON 报告 ───
    json_path = REPORTS_DIR / f"dual_layer_baseline_{_now_filename()}.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n✓ JSON 报告: {json_path}", flush=True)

    # ─── 写 markdown (含历史对比, 覆盖 AUTO_EVAL_LATEST.md) ───
    history = collect_history(report["L1"]["pct"], report["L2"]["pct"])
    md = render_markdown(report, history)
    AUTO_EVAL_MD.write_text(md)
    print(f"✓ Markdown 报告: {AUTO_EVAL_MD}", flush=True)

    # ─── 终端总结 ───
    print(f"\n{'=' * 72}")
    print(f"  双层 baseline 完成 · 总耗时 {report['duration_seconds']:.0f}s")
    print(f"  L1 atomic_facts: {report['L1']['hits']}/7 = {l1_pct:.1f}%")
    print(f"  L2 6 段叙事:     {report['L2']['hits']}/7 = {l2_pct:.1f}%")
    print(f"  诊断: {report['diagnosis']}")
    print(f"{'=' * 72}\n")

    # exit code: L2 ≥ 70 → 0; 否则 1 (CI 能用)
    return 0 if l2_pct >= L2_PASS_THRESHOLD else 1


if __name__ == "__main__":
    sys.exit(main())
