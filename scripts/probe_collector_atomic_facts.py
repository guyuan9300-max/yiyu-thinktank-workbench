"""[A] M-C.1 probe: 不调 LLM, 只测 narrative_collector 拉到多少 atomic_facts (L1 P%)

跑法:
    ~/openclaw/workspace/yiyu-thinktank-workbench/backend/.venv/bin/python3 \\
        scripts/probe_collector_atomic_facts.py
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN_REPO = Path.home() / "openclaw/workspace/yiyu-thinktank-workbench"
sys.path.insert(0, str(ROOT / "backend"))      # V2.1 优先
sys.path.insert(0, str(ROOT))
sys.path.append(str(MAIN_REPO / "backend"))
sys.path.append(str(MAIN_REPO))

PROD_DB = Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2/app.db"
CID = "client_284afd836e"  # 日慈
GOLDEN_KEYWORDS = ["法人", "理事长", "强哥", "秘书长", "兴盛", "心理魔法学院", "安心妈妈"]


def main():
    # 复制 db 到 tmp (不污染 prod)
    tmp_dir = Path(tempfile.mkdtemp(prefix="collector_probe_"))
    data_dir = tmp_dir / "data"
    data_dir.mkdir()
    shutil.copy(PROD_DB, data_dir / "app.db")
    print(f"tmp db: {data_dir}/app.db")

    # 起 FastAPI app
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(data_dir)
    client = TestClient(app)
    client.__enter__()
    state = app.state.app_state
    db = state.db

    # 验证用的 narrative_collector 是 V2.1 (有 M-C.1 改动)
    from app.services import narrative_collector
    print(f"narrative_collector 文件: {narrative_collector.__file__}")

    # 调 collector
    from app.services.narrative_collector import collect_client_fact_bundle
    bundle = collect_client_fact_bundle(db, CID)

    # L1 命中检查 — 7 关键词在 atomic_facts_by_attribute 里
    total_facts = sum(len(v) for v in bundle.atomic_facts_by_attribute.values())
    print(f"\n=== Collector 拉到 atomic_facts ===")
    print(f"  attributes: {len(bundle.atomic_facts_by_attribute)}")
    print(f"  total facts: {total_facts}")

    # 算 L1 P%
    all_text = ""
    for attr, facts in bundle.atomic_facts_by_attribute.items():
        for f in facts:
            all_text += f" {f.subject} {f.attribute} {f.value}"

    print(f"\n=== L1 命中 (atomic_facts 层) ===")
    l1_hits = 0
    for kw in GOLDEN_KEYWORDS:
        cnt = all_text.count(kw)
        marker = "✓" if cnt > 0 else "✗"
        if cnt > 0: l1_hits += 1
        print(f"  [{kw}] {cnt} 次  {marker}")
    print(f"\n→ L1 命中 {l1_hits}/7\n")

    # 也看 bundle 别的 field 命中 (v2_chunks dimension_chunks)
    print(f"=== bundle 其他字段 ===")
    print(f"  persons: {len(bundle.persons)}")
    print(f"  documents: {len(bundle.documents)}")
    print(f"  event_lines: {len(bundle.event_lines)}")
    print(f"  activities: {len(bundle.activities)}")
    print(f"  tasks: {len(bundle.tasks)}")
    print(f"  glossary: {len(bundle.glossary)}")
    print(f"  glossary_attributes: {len(bundle.glossary_attributes)}")
    print(f"  risk_signals: {len(bundle.risk_signals)}")
    print(f"  commitments: {len(bundle.commitments)}")
    print(f"  dimension_chunks: {[(d, len(c)) for d, c in bundle.dimension_chunks.items()]}")

    # dimension_chunks 里 7 关键词
    print(f"\n=== dimension_chunks 7 关键词命中 ===")
    chunk_text = ""
    for dim, chunks in bundle.dimension_chunks.items():
        for c in chunks:
            chunk_text += f" {c.excerpt}"
    chunk_hits = 0
    for kw in GOLDEN_KEYWORDS:
        cnt = chunk_text.count(kw)
        marker = "✓" if cnt > 0 else "✗"
        if cnt > 0: chunk_hits += 1
        print(f"  [{kw}] {cnt} 次  {marker}")
    print(f"\n→ dimension_chunks 命中 {chunk_hits}/7\n")

    print(f"=== 总结 (M-C.1 后) ===")
    print(f"  atomic_facts: {total_facts} 条, L1 命中 {l1_hits}/7")
    print(f"  dimension_chunks 命中 {chunk_hits}/7")
    print(f"  应做 M-C.2: {'是' if l1_hits < 5 else '否'}")

    client.__exit__(None, None, None)


if __name__ == "__main__":
    main()
