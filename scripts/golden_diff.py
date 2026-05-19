"""
Golden fixtures diff · v2.1 重构验收工具

用法:
    python scripts/golden_diff.py
    # 默认对比 tests/fixtures/golden/ vs 当前数据库
    # exit 0 = 通过(每个客户 >= 95% 字段复现)
    # exit 1 = 失败

    python scripts/golden_diff.py --threshold 0.99 --strict
    # 收紧阈值,任何 changed 都视为失败

设计:
- 不重跑 _scrub 流程(保证跟 baseline 同一规则)
- 按 (entity_id) 做 set diff
- 字段值用 dict 比较,记录 changed 数量
- 输出每客户每表的 added/removed/changed 计数,并算复现率

复现率公式:
    matched_ids = baseline_ids ∩ current_ids 中字段完全一致的数量
    reproduction = matched_ids / max(len(baseline_ids), 1)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

# 复用 dump 脚本逻辑(避免规则漂移)
from dump_golden_fixtures import (  # noqa: E402
    GOLDEN_CLIENTS,
    _safe_filename,
    dump_one_client,
)
from app.db import Database  # noqa: E402


# 业务事实表(diff 对比范围)
RAW_TABLES = ["event_lines", "entities", "glossary_attributes", "commitments", "tasks"]


def _index_by_id(rows: list[dict]) -> dict[str, dict]:
    return {str(r.get("id", "")): r for r in rows if r.get("id")}


def _diff_table(baseline: list[dict], current: list[dict]) -> dict[str, Any]:
    """返回 added/removed/changed/matched 计数 + 复现率"""
    base_idx = _index_by_id(baseline)
    cur_idx = _index_by_id(current)

    base_ids = set(base_idx.keys())
    cur_ids = set(cur_idx.keys())

    added = cur_ids - base_ids
    removed = base_ids - cur_ids
    common = base_ids & cur_ids

    changed_ids: list[tuple[str, list[str]]] = []
    matched = 0
    for entity_id in common:
        b = base_idx[entity_id]
        c = cur_idx[entity_id]
        diff_fields = [k for k in b if b.get(k) != c.get(k)]
        if diff_fields:
            changed_ids.append((entity_id, diff_fields))
        else:
            matched += 1

    # 空 baseline 的复现率定义为 1.0(空表没东西可以复现失败)
    # 但如果 baseline 空 current 有,说明 v2.1 多产了东西,记 0.0 提醒
    if not base_ids:
        reproduction = 1.0 if not cur_ids else 0.0
    else:
        reproduction = matched / len(base_ids)

    return {
        "baseline_count": len(base_ids),
        "current_count": len(cur_ids),
        "added": len(added),
        "removed": len(removed),
        "changed": len(changed_ids),
        "matched": matched,
        "reproduction": round(reproduction, 4),
        "_changed_sample": changed_ids[:3],  # 头 3 个 changed 给 debug 用
        "_removed_sample": list(removed)[:3],
    }


def _diff_one_client(baseline_path: Path, db: Database, client_id: str, client_name: str) -> dict[str, Any]:
    """对比单个客户"""
    if not baseline_path.exists():
        return {"client_name": client_name, "error": f"baseline not found: {baseline_path}"}

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    current = dump_one_client(db, client_id, client_name)

    per_table: dict[str, dict] = {}
    for table in RAW_TABLES:
        base_rows = baseline.get("raw", {}).get(table, [])
        cur_rows = current.get("raw", {}).get(table, [])
        per_table[table] = _diff_table(base_rows, cur_rows)

    # 整体复现率 = 各表 matched 总数 / 各表 baseline 总数
    total_matched = sum(t["matched"] for t in per_table.values())
    total_baseline = sum(t["baseline_count"] for t in per_table.values())
    overall = total_matched / max(total_baseline, 1)

    return {
        "client_name": client_name,
        "client_id": client_id,
        "per_table": per_table,
        "overall_reproduction": round(overall, 4),
    }


def _format_report(reports: list[dict], threshold: float) -> tuple[str, bool]:
    """生成报告 + 是否通过"""
    lines = []
    lines.append("=" * 80)
    lines.append(f"Golden Diff Report — threshold = {threshold:.2%}")
    lines.append("=" * 80)

    all_pass = True
    for r in reports:
        if "error" in r:
            lines.append(f"\n❌ {r['client_name']}: {r['error']}")
            all_pass = False
            continue

        overall = r["overall_reproduction"]
        passed = overall >= threshold
        all_pass = all_pass and passed
        status = "✓" if passed else "❌"
        lines.append(f"\n{status} {r['client_name']} ({r['client_id']}) — overall {overall:.2%}")

        for table, m in r["per_table"].items():
            t_pass = m["reproduction"] >= threshold
            t_mark = "  " if t_pass else "❗"
            lines.append(
                f"{t_mark}   {table:25s} "
                f"baseline={m['baseline_count']:4d} current={m['current_count']:4d} "
                f"matched={m['matched']:4d} added={m['added']} removed={m['removed']} changed={m['changed']} "
                f"→ {m['reproduction']:.2%}"
            )
            if m["changed"] > 0 and not t_pass:
                for entity_id, fields in m["_changed_sample"]:
                    lines.append(f"        · changed [{entity_id[:12]}...] in fields: {fields[:5]}")
            if m["removed"] > 0 and not t_pass:
                for rid in m["_removed_sample"]:
                    lines.append(f"        · removed [{rid[:24]}]")

    lines.append("\n" + "=" * 80)
    lines.append(f"OVERALL: {'PASS' if all_pass else 'FAIL'}")
    lines.append("=" * 80)
    return "\n".join(lines), all_pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare current DB against golden fixtures")
    parser.add_argument("--threshold", type=float, default=0.95, help="Per-client reproduction threshold (default 0.95)")
    parser.add_argument("--baseline-dir", default=str(ROOT / "tests" / "fixtures" / "golden"))
    parser.add_argument("--data-dir", default=None, help="Override YIYU_WORKBENCH_DATA_DIR")
    parser.add_argument("--json-out", default=None, help="Write JSON report to this path")
    args = parser.parse_args()

    data_dir = args.data_dir or os.environ.get(
        "YIYU_WORKBENCH_DATA_DIR",
        os.path.expanduser("~/Library/Application Support/YiyuThinkTankWorkbench2"),
    )
    db_path = Path(data_dir) / "app.db"
    if not db_path.exists():
        print(f"❌ database not found: {db_path}", file=sys.stderr)
        return 1

    baseline_dir = Path(args.baseline_dir)
    db = Database(db_path)

    reports: list[dict] = []
    for client_id, client_name in GOLDEN_CLIENTS:
        baseline_path = baseline_dir / f"{_safe_filename(client_name)}.json"
        reports.append(_diff_one_client(baseline_path, db, client_id, client_name))

    text, passed = _format_report(reports, args.threshold)
    print(text)

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(reports, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
