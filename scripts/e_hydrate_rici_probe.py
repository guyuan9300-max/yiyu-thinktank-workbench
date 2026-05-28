#!/usr/bin/env python3
"""验证: 对日慈调 hydrate_missing_surrogates(从已建 card 确定性拼 surrogate, 不调 LLM, 不碰 Qdrant)。
看 surrogate 0→? + master_index + catalog_index + 抽样 retrieval_summary。只读+建 surrogate, 不调 reindex。"""
import sys, os, pathlib, time, traceback
DD = pathlib.Path(os.path.expanduser("~/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "backend"))
from app.db import Database
from app.services.knowledge_base import hydrate_missing_surrogates
RICI = "client_284afd836e"
db = Database(DD / "app.db")
def cnt(sql, args=()):
    return db.fetchall(sql, args)[0][0]
try:
    b_sur = cnt("SELECT COUNT(*) FROM knowledge_surrogates WHERE client_id=? AND source_type='document'", (RICI,))
    b_mi = cnt("SELECT COUNT(*) FROM knowledge_master_index WHERE client_id=?", (RICI,))
    b_cat = cnt("SELECT COUNT(*) FROM document_catalog_index dci JOIN knowledge_documents kd ON kd.id=dci.knowledge_document_id WHERE kd.client_id=?", (RICI,))
    print(f"BEFORE 日慈 surrogate={b_sur} master_index={b_mi} catalog_index={b_cat}")
    print("调 hydrate_missing_surrogates(force_refresh=False, ai_service=None)…")
    t0 = time.time()
    hydrate_missing_surrogates(db, data_dir=DD, client_id=RICI, ai_service=None, force_refresh=False)
    el = time.time() - t0
    a_sur = cnt("SELECT COUNT(*) FROM knowledge_surrogates WHERE client_id=? AND source_type='document'", (RICI,))
    a_mi = cnt("SELECT COUNT(*) FROM knowledge_master_index WHERE client_id=?", (RICI,))
    a_cat = cnt("SELECT COUNT(*) FROM document_catalog_index dci JOIN knowledge_documents kd ON kd.id=dci.knowledge_document_id WHERE kd.client_id=?", (RICI,))
    print(f"AFTER  日慈 surrogate={a_sur} master_index={a_mi} catalog_index={a_cat} | 用时 {round(el,1)}s")
    print("抽样 3 条 surrogate retrieval_summary:")
    for r in db.fetchall("SELECT title, document_role, substr(retrieval_summary,1,150) FROM knowledge_surrogates WHERE client_id=? AND source_type='document' ORDER BY updated_at DESC LIMIT 3", (RICI,)):
        print(f"  · [{r[1]}] {str(r[0])[:30]} | {r[2]}")
except Exception:
    print("‼\n" + traceback.format_exc()[-2000:])
print("done")
