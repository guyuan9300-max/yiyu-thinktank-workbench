#!/usr/bin/env python3
"""V2.3 数据中心质量测试 命令行入口

跑青禾测试 + 输出报告 markdown.

用法:
    python scripts/run_qinghe_quality_test.py
    python scripts/run_qinghe_quality_test.py --output docs/V2.3_QUALITY_TEST_REPORT.md
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from backend.tests.quality.qinghe_runner import run_full_quality_test  # noqa: E402


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def render_report_markdown(result: dict) -> str:
    """6 段报告 markdown."""
    meta = result["test_meta"]
    scoring = result["scoring"]
    scores = scoring["scores"]

    lines = []
    lines.append(f"# V2.3 数据中心质量测试报告 · {meta['client_name']}")
    lines.append("")
    lines.append(f"**测试时间**: {meta['run_at']}")
    lines.append(f"**测试客户**: {meta['client_name']} (`{meta['client_id']}`)")
    lines.append(f"**测试项目**: {meta['project_name']}")
    lines.append(f"**数据量**: {meta['data_count']} 条 / **问题量**: {meta['question_count']} 问")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 🎯 总分与等级")
    lines.append("")
    lines.append(f"### **{scores['TOTAL']:.1f} / 100 分 · 等级 {scoring['grade']}**")
    lines.append(f"### **{scoring['verdict']}**")
    lines.append("")
    lines.append("| 维度 | 满分 | 得分 | 占比 |")
    lines.append("|---|---|---|---|")
    for k, v in scores.items():
        if k == "TOTAL":
            continue
        lines.append(f"| {k} | 20 | {v:.1f} | {v / 20:.0%} |")
    lines.append(f"| **总分** | **100** | **{scores['TOTAL']:.1f}** | **{scores['TOTAL'] / 100:.0%}** |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 1. 数据进入报告
    lines.append("## 1️⃣ 数据进入报告 (12 条)")
    lines.append("")
    lines.append(f"实际写入 atomic_facts: **{len(result['ingest_results'])} 条**")
    lines.append("")
    by_datum: dict[str, list] = {}
    for r in result["ingest_results"]:
        by_datum.setdefault(r.get("datum_id", "?"), []).append(r)
    lines.append("| Datum | Facts | 错误? |")
    lines.append("|---|---|---|")
    for datum_id, rs in by_datum.items():
        err = next((r.get("error") for r in rs if r.get("error")), None)
        lines.append(f"| {datum_id} | {len(rs)} | {err or '-'} |")
    lines.append("")

    # 2. 抽取结果报告 (D2)
    lines.append("## 2️⃣ 抽取结果报告 (D2 实体召回)")
    lines.append("")
    d2 = scoring["details"]["D2"]
    lines.append(f"召回率: **{d2['recalled']} / {d2['expected_total']} = {d2['recall_rate']:.0%}**")
    lines.append("")
    for cat, items in d2["detail"].items():
        hits = sum(1 for i in items if i["ok"])
        lines.append(f"### {cat} · {hits}/{len(items)}")
        for i in items:
            mark = "✅" if i["ok"] else "❌"
            lines.append(f"- {mark} {i['item']}")
        lines.append("")

    # 3. 冲突与澄清报告
    lines.append("## 3️⃣ 冲突与澄清报告 (D3)")
    lines.append("")
    d3 = scoring["details"]["D3"]
    lines.append(f"**核心冲突命中**: {d3['core_conflicts_hit']} / {d3['core_conflicts_expected']}")
    lines.append(f"**澄清记录总数**: {d3['clarifications_total']}")
    lines.append("")
    lines.append("### 核心冲突命中详情")
    for c in d3["core_hit_detail"]:
        mark = "✅" if c["hit"] else "❌"
        lines.append(f"- {mark} {c['conflict']}")
    lines.append("")
    cs = result["cross_source_stats"]
    lines.append(f"**cross_source 嫌疑对**: {cs['candidates_found']} 对")
    if cs.get("candidates"):
        lines.append("\n前 10 对:")
        for c in cs["candidates"][:10]:
            lines.append(
                f"- 「{c.get('text_a','?')}」 vs 「{c.get('text_b','?')}」 "
                f"suspicion={c.get('suspicion', 0):.2f} → {c.get('action', '?')}"
            )
    lines.append("")

    # 4. 项目故事卡
    lines.append("## 4️⃣ 项目故事卡 (D4)")
    lines.append("")
    d4 = scoring["details"]["D4"]
    lines.append(f"10 段有内容: **{d4['sections_with_content']} / 10**")
    lines.append(f"故事卡字符数: {d4['card_length']}")
    lines.append("")
    lines.append("### 段落详情")
    for s in d4["sections_detail"]:
        mark = "✅" if s["has_content"] else "❌"
        lines.append(f"- {mark} {s['title']}")
    lines.append("")
    lines.append("### 故事卡全文")
    lines.append("")
    lines.append("```markdown")
    lines.append(result["story_card_md"])
    lines.append("```")
    lines.append("")

    # 5. 50 问测试结果
    lines.append("## 5️⃣ 50 问测试结果 (D5)")
    lines.append("")
    d5 = scoring["details"]["D5"]
    lines.append(f"**正确率**: {d5['correct']} / {d5['total']} = **{d5['correct_rate']:.0%}**")
    lines.append(f"**有证据**: {d5['has_evidence_count']} / {d5['total']}")
    lines.append(f"**Violations (说了不该说的)**: {d5['violations_count']}")
    lines.append("")
    lines.append("### 逐题结果")
    lines.append("")
    lines.append("| Qid | 类型 | 命中关键词 | 评判 |")
    lines.append("|---|---|---|---|")
    for r in result["qa_results"]:
        mark = "✅" if r["correct"] else "❌"
        hits = ", ".join(r["must_contain_hits"][:3]) + ("..." if len(r["must_contain_hits"]) > 3 else "")
        lines.append(f"| {r['qid']} | {r['prompt'][:30]}... | {hits} | {mark} |")
    lines.append("")
    if d5["wrong_questions"]:
        lines.append("### 错题清单 (前 10)")
        for wq in d5["wrong_questions"]:
            lines.append(f"- **{wq['qid']}**: {wq['prompt']}")
    lines.append("")

    # 6. 最需要修的 3 个问题
    lines.append("## 6️⃣ 总分与最需要修的 3 个问题")
    lines.append("")
    lines.append(f"### 总分: {scores['TOTAL']:.1f} / 100 ({scoring['grade']} 级)")
    lines.append("")
    lines.append("### 最低分维度排行")
    sorted_dims = sorted(
        [(k, v) for k, v in scores.items() if k != "TOTAL"],
        key=lambda x: x[1],
    )
    for k, v in sorted_dims[:3]:
        lines.append(f"- 🔴 **{k}**: {v:.1f}/20 ({v / 20:.0%})")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 后续行动")
    lines.append("")
    if scoring["grade"] == "A":
        lines.append("- ✅ 可 cherry-pick V2.3 到主仓库")
        lines.append("- ✅ 可启动 V2.4 (蓝图 § 十 breakpoints)")
    elif scoring["grade"] == "B":
        lines.append("- ⚠️ 不可 cherry-pick, 继续修缺陷")
        lines.append("- 优先修上面 3 个最低分维度")
    else:
        lines.append("- ❌ 数据中心核心假设未成立")
        lines.append("- 必须重做底层抽取链路, 才能讨论 V2.4")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", "-o", type=Path,
        default=ROOT / "docs" / "V2.3_QUALITY_TEST_REPORT.md",
    )
    parser.add_argument(
        "--json-output", type=Path,
        default=ROOT / "docs" / "V2.3_QUALITY_TEST_REPORT.json",
    )
    args = parser.parse_args()

    print("🚀 跑 V2.3 数据中心质量测试 · 青禾公益基金会")
    result = run_full_quality_test()
    print("✅ 测试完成, 渲染报告...")

    md = render_report_markdown(result)
    args.output.write_text(md, encoding="utf-8")
    print(f"📝 报告: {args.output}")

    # JSON 详情 (机读)
    args.json_output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"📊 JSON: {args.json_output}")

    scoring = result["scoring"]
    print(f"\n🎯 总分: {scoring['scores']['TOTAL']:.1f}/100 · 等级 {scoring['grade']}")
    print(f"   {scoring['verdict']}")
    print("\n维度分:")
    for k, v in scoring["scores"].items():
        if k == "TOTAL":
            continue
        print(f"  {k}: {v:.1f}/20 ({v / 20:.0%})")


if __name__ == "__main__":
    main()
