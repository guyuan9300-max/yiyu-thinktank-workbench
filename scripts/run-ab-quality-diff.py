"""[A] 方案 C: 双 app A/B 同比质量排查脚本

服务: 顾源源 5/22 方案 C — V2.1 lab + 主仓库 同跑, 相同输入对比 6 段叙事质量

跑法 (前置: 主仓库 app + V2.1 lab app 都在跑):
    cd ~/openclaw/workspace/V2.1
    ~/openclaw/workspace/yiyu-thinktank-workbench/backend/.venv/bin/python3 \\
        scripts/run-ab-quality-diff.py [client_name=日慈基金会]

输入:
- 主仓库 backend: http://127.0.0.1:47829
- V2.1 lab backend: http://127.0.0.1:47831
- 同一客户 (默认日慈基金会)

输出:
- docs/AB_DIFF_<date>.md (人读对比)
- tests/reports/ab_diff_<timestamp>.json (机器消费)

对比维度:
1. 6 段叙事每段的 confidence 差异
2. 6 段 narrative 文本长度差异
3. 5/19 张真会议 7 道金标准命中率差异
4. references 数量差异 (说明引用源多少)
5. openClarifications 数量差异 (说明数据缺口多少)
6. 整体 confidence 差异
7. 耗时差异 (主仓库 vs V2.1)
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "tests" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

MAIN_BACKEND = "http://127.0.0.1:47829"
LAB_BACKEND = "http://127.0.0.1:47831"

GOLDEN_KEYWORDS_5_19 = ["法人", "理事长", "强哥", "秘书长", "兴盛", "心理魔法学院", "安心妈妈"]
DIMENSIONS = ("essence", "cooperation", "business_intro", "people", "timeline", "next_steps")


def _http_get(url: str, timeout: float = 600.0) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"  ✗ {url} 失败: {e}", flush=True)
        return None


def _fetch_narrative(backend: str, client_id: str, label: str) -> dict | None:
    """从 backend 拿 6 段 narrative.

    Endpoint 假设是 /api/v1/clients/{client_id}/narrative 或主仓库现有 endpoint.
    具体 URL 待 B AI 阶段 1 报告确认 (docs/B_AI_PHASE_1_FRONTEND_AUDIT.md).
    """
    url = f"{backend}/api/v1/clients/{client_id}/narrative"
    print(f"▸ 拉 {label}: {url}", flush=True)
    t0 = time.perf_counter()
    data = _http_get(url)
    dt = time.perf_counter() - t0
    if data:
        print(f"  ✓ {label} 耗时 {dt:.1f}s, confidence={data.get('overallConfidence', 'N/A')}", flush=True)
    return {"data": data, "duration_s": dt, "url": url, "label": label}


def _golden_hits(dims: dict) -> dict[str, int]:
    """跑 5/19 金标准命中检查"""
    text = ""
    for d in dims.values() if isinstance(dims, dict) else []:
        if isinstance(d, dict):
            text += str(d.get("narrative", ""))
    return {kw: text.count(kw) for kw in GOLDEN_KEYWORDS_5_19}


def _diff_dims(main_dims: dict, lab_dims: dict) -> dict:
    """每段对比"""
    diff = {}
    for d in DIMENSIONS:
        m = main_dims.get(d, {}) if isinstance(main_dims, dict) else {}
        l = lab_dims.get(d, {}) if isinstance(lab_dims, dict) else {}
        if not isinstance(m, dict): m = {}
        if not isinstance(l, dict): l = {}
        diff[d] = {
            "main_confidence": m.get("confidence", "N/A"),
            "lab_confidence": l.get("confidence", "N/A"),
            "main_chars": len(str(m.get("narrative", ""))),
            "lab_chars": len(str(l.get("narrative", ""))),
            "main_refs": len(m.get("references", []) or []),
            "lab_refs": len(l.get("references", []) or []),
            "main_clars": len(m.get("openClarifications", []) or []),
            "lab_clars": len(l.get("openClarifications", []) or []),
        }
    return diff


def main() -> int:
    client_name = sys.argv[1] if len(sys.argv) > 1 else "日慈基金会"
    print(f"\n{'=' * 72}")
    print(f"  方案 C 双 app A/B 同比质量排查")
    print(f"  客户: {client_name}")
    print(f"  主仓库 (47829) vs V2.1 lab (47831)")
    print(f"{'=' * 72}\n")

    # 找 client_id (从主仓库 backend)
    # NOTE: 真实 endpoint 待 B AI 阶段 1 报告确认; 暂用日慈基金会 client_id 写死
    client_id = "client_284afd836e"  # 日慈基金会 (从之前 dogfood 知道)

    main_result = _fetch_narrative(MAIN_BACKEND, client_id, "主仓库 (旧 collector)")
    lab_result = _fetch_narrative(LAB_BACKEND, client_id, "V2.1 lab (新 collector + atomic_facts)")

    if not main_result["data"] or not lab_result["data"]:
        print("\n✗ 至少一个 backend 拉取失败. 检查:")
        print(f"  - 主仓库 app 是否在跑? (端口 {MAIN_BACKEND})")
        print(f"  - V2.1 lab app 是否在跑? (端口 {LAB_BACKEND})")
        print(f"  - endpoint URL 是否正确? (本脚本假设 /api/v1/clients/.../narrative,")
        print(f"     待 B AI 阶段 1 报告 docs/B_AI_PHASE_1_FRONTEND_AUDIT.md 确认)")
        return 1

    main_dims = main_result["data"].get("dimensions", {}) or main_result["data"].get("dims", {})
    lab_dims = lab_result["data"].get("dimensions", {}) or lab_result["data"].get("dims", {})

    diff = _diff_dims(main_dims, lab_dims)
    main_golden = _golden_hits(main_dims)
    lab_golden = _golden_hits(lab_dims)
    main_hits = sum(1 for v in main_golden.values() if v > 0)
    lab_hits = sum(1 for v in lab_golden.values() if v > 0)

    # 写 markdown 报告
    md = []
    md.append(f"# AB 同比质量排查 · {client_name} · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    md.append("")
    md.append(f"## 主仓库 (47829) vs V2.1 lab (47831)")
    md.append("")
    md.append(f"| 维度 | 主仓库 (旧 collector) | V2.1 lab (新 collector + atomic_facts) | 改善 |")
    md.append(f"|---|---|---|---|")
    md.append(f"| overall_confidence | {main_result['data'].get('overallConfidence', 'N/A')} | {lab_result['data'].get('overallConfidence', 'N/A')} | — |")
    md.append(f"| 耗时 (s) | {main_result['duration_s']:.1f} | {lab_result['duration_s']:.1f} | {(lab_result['duration_s'] - main_result['duration_s']):+.1f} |")
    md.append(f"| 5/19 金标准命中 | {main_hits}/7 | {lab_hits}/7 | {lab_hits - main_hits:+d} |")
    md.append("")
    md.append(f"## 5/19 张真会议 7 道金标准逐项")
    md.append(f"| 关键词 | 主仓库出现次数 | V2.1 lab 出现次数 |")
    md.append(f"|---|---|---|")
    for kw in GOLDEN_KEYWORDS_5_19:
        m = main_golden.get(kw, 0)
        l = lab_golden.get(kw, 0)
        marker = "🆙" if l > m else ("⬇️" if l < m else "—")
        md.append(f"| {kw} | {m} | {l} {marker}|")
    md.append("")
    md.append(f"## 6 段逐段对比")
    md.append("")
    md.append(f"| 段 | 主仓库 conf | lab conf | 主仓库 chars | lab chars | 主仓库 refs | lab refs | clars 差 |")
    md.append(f"|---|---|---|---|---|---|---|---|")
    for d in DIMENSIONS:
        dd = diff[d]
        md.append(
            f"| {d} | {dd['main_confidence']} | {dd['lab_confidence']} | "
            f"{dd['main_chars']} | {dd['lab_chars']} ({dd['lab_chars'] - dd['main_chars']:+d}) | "
            f"{dd['main_refs']} | {dd['lab_refs']} ({dd['lab_refs'] - dd['main_refs']:+d}) | "
            f"{dd['lab_clars'] - dd['main_clars']:+d} |"
        )
    md.append("")
    md.append(f"## 结论")
    md.append("")
    if lab_hits >= 5 and lab_hits > main_hits:
        md.append(f"✅ **V2.1 lab 显著优于主仓库** — 5/19 金标准命中 {main_hits}/7 → {lab_hits}/7,确认 atomic_facts + 8 张表补充有效。")
    elif lab_hits == main_hits:
        md.append(f"⚠️ **V2.1 lab 跟主仓库持平** — 命中都是 {main_hits}/7,可能 collector 改动还没生效或 LLM prompt 没用新数据。")
    else:
        md.append(f"🔴 **V2.1 lab 不如主仓库** — 改动可能引入回归,需要排查。")
    md.append("")

    out_path = ROOT / "docs" / f"AB_DIFF_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    out_path.write_text("\n".join(md), encoding="utf-8")
    print(f"\n✓ 同比报告: {out_path.relative_to(ROOT)}", flush=True)

    # JSON 报告
    json_report = {
        "client_name": client_name,
        "client_id": client_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "main": {
            "backend": MAIN_BACKEND,
            "duration_s": main_result["duration_s"],
            "overall_confidence": main_result["data"].get("overallConfidence"),
            "golden_hits": main_hits,
            "golden_by_keyword": main_golden,
        },
        "lab": {
            "backend": LAB_BACKEND,
            "duration_s": lab_result["duration_s"],
            "overall_confidence": lab_result["data"].get("overallConfidence"),
            "golden_hits": lab_hits,
            "golden_by_keyword": lab_golden,
        },
        "per_dimension_diff": diff,
    }
    json_path = REPORTS_DIR / f"ab_diff_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    json_path.write_text(json.dumps(json_report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ JSON 报告: {json_path.relative_to(ROOT)}", flush=True)

    print(f"\n{'=' * 72}")
    print(f"  主仓库 {main_hits}/7  →  V2.1 lab {lab_hits}/7")
    print(f"{'=' * 72}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
