#!/usr/bin/env python3
"""验证富化后战略陪伴 FTS 召回(只走 search_master_index_fts, 不碰 Qdrant)。"""
import sys, os, pathlib
DD = pathlib.Path(os.path.expanduser("~/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "backend"))
from app.db import Database
from app.services import knowledge_base as KB
db = Database(DD / "app.db")
RICI = "client_284afd836e"
for q in ["日慈第二曲线增长与儿童心理韧性战略", "心盛计划研讨会议核心内容", "品牌传播策略规划"]:
    sc = KB.search_master_index_fts(db, RICI, q, limit=8)
    print(f"\nQ: {q} → 命中 {len(sc)}")
    for mid, s in sorted(sc.items(), key=lambda x: -x[1])[:5]:
        r = db.fetchone("SELECT title FROM knowledge_master_index WHERE id=?", (mid,))
        print(f"  {round(s,3)}  {str(r['title'])[:38] if r else mid}")
print("\ndone")
