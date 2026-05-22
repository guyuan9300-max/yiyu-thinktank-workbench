"""[A] 阶段 1: dogfood 主仓库 narrative_generator 6 段叙事 baseline

服务: docs/V2.2_NEW_PLAN_20260522.md 阶段 1

目的:
1. 用主仓库 narrative_generator + collector 跑日慈基金会一次完整 6 段叙事
2. dump 输出到 docs/dogfood_narrative_6dim_baseline_20260522.md
3. 检查 5/19 张真会议 7 道金标准在 6 段中的命中率
4. 列每段:LLM 输出 / 把握度 / 引用源 / 数据缺口
5. 用 顾源源 review

入口 (主仓库):
  collect_client_fact_bundle(db, client_id) → ClientFactBundle
  generate_narrative_dimensions(ai, bundle, db=db) → (6dim dict, confidence, model)

DIMENSIONS = essence / cooperation / business_intro / people / timeline / next_steps

跑法:
    cd ~/openclaw/workspace/V2.1
    ~/openclaw/workspace/yiyu-thinktank-workbench/backend/.venv/bin/python3 \\
        scripts/run_v22_dogfood_6dim_baseline.py [client_name=日慈基金会]
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# 用主仓库的 backend (有 narrative_generator + collector + ai_service)
MAIN_REPO = Path.home() / "openclaw/workspace/yiyu-thinktank-workbench"
sys.path.insert(0, str(MAIN_REPO / "backend"))
sys.path.insert(0, str(MAIN_REPO))

REPORTS_DIR = ROOT / "tests" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
DOGFOOD_OUT = ROOT / "docs" / "dogfood_narrative_6dim_baseline_20260522.md"

PROD_DB = Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2/app.db"
DEFAULT_CLIENT_NAME = "日慈基金会"

# 5/19 张真会议 7 道金标准
GOLDEN_KEYWORDS_5_19 = ["法人", "理事长", "强哥", "秘书长", "兴盛", "心理魔法学院", "安心妈妈"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    client_name = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CLIENT_NAME
    print(f"\n{'=' * 72}")
    print(f"  [A] 阶段 1 dogfood · 主仓库 6 段叙事 baseline")
    print(f"  客户: {client_name}")
    print(f"  prod db: {PROD_DB}")
    print(f"{'=' * 72}\n")

    if not PROD_DB.exists():
        print(f"✗ prod db 不存在: {PROD_DB}")
        return 1

    started = time.perf_counter()
    report = {
        "started_at": _now(),
        "client_name": client_name,
        "client_id": "",
        "bundle_stats": {},
        "dims": {},
        "overall_confidence": 0.0,
        "model_used": "",
        "golden_keywords_5_19": {kw: 0 for kw in GOLDEN_KEYWORDS_5_19},
        "golden_hits": 0,
        "errors": [],
        "tmp_data_dir": "",
        "duration_seconds": 0.0,
    }

    try:
        # ─── Phase 1: 复制 prod db ──────────────────────────
        print("▸ 1/4 复制 prod db 到 tmp...", flush=True)
        tmp_dir = Path(tempfile.mkdtemp(prefix="dogfood_6dim_"))
        data_dir = tmp_dir / "data"
        data_dir.mkdir()
        shutil.copy(PROD_DB, data_dir / "app.db")
        for ext in ("-wal", "-shm"):
            wal = data_dir / f"app.db{ext}"
            if wal.exists():
                wal.unlink()
        report["tmp_data_dir"] = str(tmp_dir)
        print(f"  ✓ tmp data_dir: {data_dir}", flush=True)

        # ─── Phase 2: 起 FastAPI app (拿 ai_service + db) ───
        print("▸ 2/4 起 FastAPI app (跑 migrations, 30-60 秒)...", flush=True)
        from fastapi.testclient import TestClient
        from app.main import create_app

        app = create_app(data_dir)
        client = TestClient(app)
        client.__enter__()
        state = app.state.app_state  # type: ignore[attr-defined]
        db = state.db
        ai = state.ai
        print(f"  ✓ ai_service ready: {ai is not None}, health: {ai.get_health().ready if ai else False}", flush=True)

        # 找 client_id
        client_row = db.fetchone(
            "SELECT id, name FROM clients WHERE name LIKE ? LIMIT 1",
            (f"%{client_name}%",),
        )
        if not client_row:
            print(f"✗ 找不到客户: {client_name}")
            return 1
        report["client_id"] = str(client_row["id"])
        print(f"  ✓ client_id={report['client_id'][:24]}.. / name={client_row['name']}", flush=True)

        # ─── Phase 3: 跑 collector + generator ──────────────
        print("▸ 3/4 collect_client_fact_bundle (拉 13 张现成表)...", flush=True)
        from app.services.narrative_collector import collect_client_fact_bundle
        bundle = collect_client_fact_bundle(db, report["client_id"])
        report["bundle_stats"] = {
            "persons": len(bundle.persons) if hasattr(bundle, "persons") else 0,
            "time_anchors": len(bundle.time_anchors) if hasattr(bundle, "time_anchors") else 0,
            "money_anchors": len(bundle.money_anchors) if hasattr(bundle, "money_anchors") else 0,
            "atomic_facts": len(bundle.atomic_facts_by_dim) if hasattr(bundle, "atomic_facts_by_dim") else 0,
            "event_lines": len(bundle.event_lines) if hasattr(bundle, "event_lines") else 0,
            "activities": len(bundle.activities) if hasattr(bundle, "activities") else 0,
            "tasks": len(bundle.tasks) if hasattr(bundle, "tasks") else 0,
            "documents": len(bundle.documents) if hasattr(bundle, "documents") else 0,
        }
        print(f"  ✓ bundle 拉到: {report['bundle_stats']}", flush=True)

        print("▸ 4/4 generate_narrative_dimensions (调 LLM, 1-5 分钟)...", flush=True)
        from app.services.narrative_generator import generate_narrative_dimensions
        dims, overall, model_used = generate_narrative_dimensions(
            ai, bundle, db=db, enable_clarification_pre_search=False,
        )
        report["dims"] = dims
        report["overall_confidence"] = overall
        report["model_used"] = model_used
        print(f"  ✓ 6 段生成完毕, confidence={overall:.2f}, model={model_used}", flush=True)

        # ─── Phase 4: 5/19 金标准命中检查 ───────────────────
        print("▸ 5/19 张真会议 7 道金标准命中检查...", flush=True)
        all_narrative_text = "\n".join(
            str(d.get("narrative", "") if isinstance(d, dict) else "") for d in dims.values()
        )
        for kw in GOLDEN_KEYWORDS_5_19:
            cnt = all_narrative_text.count(kw)
            report["golden_keywords_5_19"][kw] = cnt
            marker = "✓" if cnt > 0 else "✗"
            print(f"    {marker} {kw}: {cnt} 次出现", flush=True)
        report["golden_hits"] = sum(1 for v in report["golden_keywords_5_19"].values() if v > 0)
        print(f"  → 命中 {report['golden_hits']}/7\n", flush=True)

        client.__exit__(None, None, None)

    except Exception as exc:
        tb = traceback.format_exc()
        report["errors"].append(f"{exc}\n{tb[-2000:]}")
        print(f"\n✗ 出错:\n{tb[-2000:]}", flush=True)
        return 1
    finally:
        report["duration_seconds"] = time.perf_counter() - started

    # ─── 写 markdown dogfood 报告 (顾源源 review) ────────────
    md = []
    md.append(f"# dogfood · 主仓库 6 段叙事 baseline · {client_name}")
    md.append("")
    md.append(f"> 生成: {report['started_at']} · 耗时 {report['duration_seconds']:.0f}s · model={report['model_used']}")
    md.append(f"> 客户 id: `{report['client_id']}`")
    md.append(f"> overall_confidence: **{report['overall_confidence']:.2f}**")
    md.append(f"> tmp db: `{report['tmp_data_dir']}`")
    md.append("")
    md.append(f"## bundle 拉到的现成表统计")
    md.append("")
    for k, v in report["bundle_stats"].items():
        md.append(f"- {k}: {v}")
    md.append("")
    md.append(f"## 5/19 张真会议 7 道金标准命中(顾源源 N2 评估基线)")
    md.append("")
    md.append(f"**命中**: {report['golden_hits']}/7")
    md.append("")
    md.append("| 关键词 | 在 6 段叙事中出现次数 | 命中 |")
    md.append("|---|---|---|")
    for kw, cnt in report["golden_keywords_5_19"].items():
        marker = "✓" if cnt > 0 else "✗"
        md.append(f"| {kw} | {cnt} | {marker} |")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 6 段叙事真实输出(顾源源 review)")
    md.append("")
    DIM_LABELS = {
        "essence": "组织介绍 (essence)",
        "cooperation": "合作关系 (cooperation)",
        "business_intro": "业务介绍 (business_intro)",
        "people": "关键人物 (people)",
        "timeline": "时间线 (timeline)",
        "next_steps": "本阶段战略思路 (next_steps)",
    }
    for dim_key in ("essence", "cooperation", "business_intro", "people", "timeline", "next_steps"):
        label = DIM_LABELS.get(dim_key, dim_key)
        dim = report["dims"].get(dim_key, {})
        if not isinstance(dim, dict):
            md.append(f"### {label}\n\n_(段输出异常: {type(dim).__name__})_\n")
            continue
        md.append(f"### {label}")
        md.append("")
        md.append(f"- **confidence**: `{dim.get('confidence', 'N/A')}`")
        md.append(f"- **confidenceReason**: {dim.get('confidenceReason', '(无)')}")
        md.append(f"- **buildsOn**: {dim.get('buildsOn', '(无)')}")
        md.append(f"- **dataLayerGap**: {dim.get('dataLayerGap', '(无)')}")
        md.append("")
        md.append("**narrative**:")
        md.append("")
        md.append(f"> {dim.get('narrative', '(空)')}".replace("\n", "\n> "))
        md.append("")
        refs = dim.get("references", []) or []
        if refs:
            md.append(f"**references ({len(refs)} 条)**:")
            md.append("")
            for r in refs[:10]:
                if isinstance(r, dict):
                    md.append(f"- `{r.get('sourceType', '')}` / `{r.get('sourceId', '')}` · {r.get('label', '')}")
            if len(refs) > 10:
                md.append(f"- ...(还有 {len(refs)-10} 条)")
            md.append("")
        clars = dim.get("openClarifications", []) or []
        if clars:
            md.append(f"**openClarifications ({len(clars)} 条 待澄清)**:")
            md.append("")
            for c in clars[:5]:
                md.append(f"- {c}")
            md.append("")
        md.append("---")
        md.append("")

    if report["errors"]:
        md.append("## 错误")
        md.append("")
        for e in report["errors"]:
            md.append(f"```\n{e}\n```")

    md.append("")
    md.append(f"## 顾源源评估打分(请填)")
    md.append("")
    md.append("| 段 | 把握度 (high/med/low) | 是否符合产品手册 §03 期望 | 备注 |")
    md.append("|---|---|---|---|")
    for dim_key in ("essence", "cooperation", "business_intro", "people", "timeline", "next_steps"):
        md.append(f"| {dim_key} | | | |")
    md.append("")
    md.append("**N2 北极星 5/19 评估**:")
    md.append(f"- 7 道金标准命中: **{report['golden_hits']}/7** (目标 ≥ 5)")
    md.append("- 是否过线: " + ("✅ 是" if report['golden_hits'] >= 5 else "❌ 否, 阶段 2 补 collector 8 张表后再测"))

    DOGFOOD_OUT.write_text("\n".join(md), encoding="utf-8")
    print(f"\n✓ dogfood 报告写入: {DOGFOOD_OUT.relative_to(ROOT)}", flush=True)

    # 同时写 JSON 报告供机器消费
    json_path = REPORTS_DIR / f"dogfood_6dim_baseline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ JSON 报告: {json_path.relative_to(ROOT)}", flush=True)

    print(f"\n{'=' * 72}")
    print(f"  命中 {report['golden_hits']}/7 · confidence {report['overall_confidence']:.2f} · {report['duration_seconds']:.0f}s")
    print(f"  ★ 接下来顾源源 review: {DOGFOOD_OUT.relative_to(ROOT)}")
    print(f"{'=' * 72}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
