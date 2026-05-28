#!/usr/bin/env python3
"""实测日慈 next_steps 维度取材结果: 语义(我富化的)vs LIKE兜底(v2_chunks)各贡献多少。"""
import sys, os, pathlib, traceback
DD = pathlib.Path(os.path.expanduser("~/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "backend"))
from app.db import Database
from app.services import strategic_narrative_semantic_retriever as snr
from app.services.narrative_collector import _retrieve_top_chunks, _DIMENSION_BASE_KEYWORDS
db = Database(DD / "app.db")
RICI = "client_284afd836e"
try:
    retr = snr.retrieve_dimension(
        db, RICI, "next_steps",
        like_keywords=_DIMENSION_BASE_KEYWORDS.get("next_steps", ()),
        like_fallback_fn=_retrieve_top_chunks, viewer_user_id="",
    )
    chunks = list(retr.chunks)
    by_path = {}
    for c in chunks:
        by_path[c.retrieval_path] = by_path.get(c.retrieval_path, 0) + 1
    print(f"retrieval_mode = {retr.retrieval_mode}")
    print(f"coverage(语义) = {retr.coverage}")
    print(f"candidate_count = {retr.candidate_count}  fallback_used = {retr.fallback_used}  fallback_reason = {retr.fallback_reason}")
    print(f"最终 chunks = {len(chunks)}  路径分布 = {by_path}")
    print("抽样(前 6):")
    for c in chunks[:6]:
        print(f"  [{c.retrieval_path}] {round(c.score,3)} {c.doc_title[:24]} | {c.excerpt[:70].strip()}")
except Exception:
    print("ERR\n" + traceback.format_exc()[-1200:])
print("\ndone")
