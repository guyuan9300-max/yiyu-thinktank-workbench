#!/usr/bin/env python3
"""E 检索底座真相测试 · 只读 harness (M1-M4).
不改 knowledge_base.py / 不 reindex / 不 populate。只调用现有读路径 + 直读 Qdrant 点数。
用法: <backend-venv-python> scripts/e_search_stack_probe.py
"""
import sys, os, json, pathlib, re, traceback

DD = pathlib.Path(os.path.expanduser("~/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab"))
REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.db import Database
from app.services import knowledge_base as kb

db = Database(DD / "app.db")
data_dir = DD
COLL_DIR = data_dir / "vector_store" / "_qdrant" / "collection"

CLIENTS = {
    "CFFC": "client_a4d1db29a7", "日慈": "client_284afd836e", "士平": "client_55f5a8c847",
    "益语智库": "client_53d82aa249", "善加": "client_256d89c5ef",
    "为爱黔行": "client_85d5c52575", "云南儿童": "client_bda0f1d379",
}
QUERIES = ["组织介绍", "合作关系", "业务项目", "关键人物", "时间线", "下一步", "合同协议", "风险与待澄清"]

def disk_colls(cid):
    if not COLL_DIR.exists():
        return []
    return sorted([p.name for p in COLL_DIR.iterdir() if cid in p.name])

qclient = kb.qdrant_client_for(data_dir)

def pcount(name):
    if qclient is None:
        return -1
    try:
        return kb.qdrant_payload_count(qclient, name)
    except Exception:
        return -1

def bundle_len(b):
    best = 0
    for a in dir(b):
        if a.startswith("_"):
            continue
        try:
            v = getattr(b, a)
        except Exception:
            continue
        if isinstance(v, (list, tuple)):
            best = max(best, len(v))
    return best

out = {"clients": {}, "m3_side_effect": {}, "m4": {}}

# ---- M1 + M2 ----
for name, cid in CLIENTS.items():
    rec = {"client_id": cid}
    try:
        names = kb.resolve_vector_collection_names(db, data_dir=data_dir, client_id=cid)
        rec["runtime_signature"] = names.get("signature", "")
        rec["runtime_master_active"] = names["masterActive"]
        rec["runtime_master_legacy"] = names["masterLegacy"]
        dc = disk_colls(cid)
        rec["disk_collections"] = dc
        rec["runtime_active_exists"] = names["masterActive"] in dc
        # manifest (latest row per client)
        mrows = db.fetchall("SELECT embedding_signature, active_collection, status, master_indexed, chunk_indexed, updated_at FROM vector_index_manifests WHERE client_id=? ORDER BY updated_at DESC", (cid,))
        rec["manifest_rows"] = [{"sig": str(r["embedding_signature"]), "active": str(r["active_collection"]), "status": str(r["status"]), "master_indexed": int(r["master_indexed"]), "chunk_indexed": int(r["chunk_indexed"]), "updated_at": str(r["updated_at"])} for r in mrows]
        latest = rec["manifest_rows"][0] if rec["manifest_rows"] else None
        rec["manifest_active"] = latest["active"] if latest else ""
        rec["signature_drift"] = bool(latest and latest["active"] != names["masterActive"])
        # M2 point counts for every disk collection of this client
        rec["point_counts"] = {c: pcount(c) for c in dc}
        # payload sample from runtime active (or any non-empty)
        rec["payload_sample"] = None
        if qclient is not None:
            for c in dc:
                if rec["point_counts"].get(c, 0) > 0:
                    try:
                        pts, _ = qclient.scroll(collection_name=c, limit=1, with_payload=True)
                        if pts:
                            pl = pts[0].payload or {}
                            rec["payload_sample"] = {"collection": c, "keys": sorted(pl.keys())[:12], "has_client_id": "client_id" in pl, "has_document_id": ("document_id" in pl or "entry_id" in pl)}
                    except Exception as e:
                        rec["payload_sample"] = {"error": str(e)[:120]}
                    break
        # surrogate / master_index base counts (the lexical workhorse)
        rec["surrogate_count"] = int(db.scalar("SELECT COUNT(1) FROM knowledge_surrogates WHERE client_id=?", (cid,)))
        rec["master_index_count"] = int(db.scalar("SELECT COUNT(1) FROM knowledge_master_index WHERE client_id=?", (cid,)))
        rec["deep_read_done"] = int(db.scalar("SELECT COUNT(1) FROM knowledge_documents WHERE client_id=? AND deep_read=1", (cid,)))
    except Exception:
        rec["error"] = traceback.format_exc()[-600:]
    out["clients"][name] = rec

# ---- M3: 查询是否对不存在客户创建空 collection ----
fake = "client_PROBEZZZ999"
before = sorted([p.name for p in COLL_DIR.iterdir()]) if COLL_DIR.exists() else []
try:
    qd = kb.search_master_index_qdrant(data_dir, fake, "测试探针", db=db)
    after = sorted([p.name for p in COLL_DIR.iterdir()]) if COLL_DIR.exists() else []
    created = [c for c in after if c not in before]
    out["m3_side_effect"] = {"fake_client": fake, "qdrant_hits": len(qd), "new_collections_created": created, "new_collection_point_counts": {c: pcount(c) for c in created}}
except Exception:
    out["m3_side_effect"] = {"error": traceback.format_exc()[-600:]}

# ---- M4: 三路贡献拆分 ----
for name, cid in CLIENTS.items():
    out["m4"][name] = []
    for q in QUERIES:
        row = {"query": q}
        try:
            fts = kb.search_master_index_fts(db, cid, q)
            row["fts_hits"] = len(fts)
        except Exception as e:
            row["fts_hits"] = -1; row["fts_err"] = str(e)[:100]
        try:
            qd = kb.search_master_index_qdrant(data_dir, cid, q, db=db)
            row["qdrant_hits"] = len(qd)
        except Exception as e:
            row["qdrant_hits"] = -1; row["qd_err"] = str(e)[:100]
        try:
            b = kb.retrieve_knowledge_bundle(db, data_dir, cid, q)
            row["bundle_count"] = bundle_len(b)
        except Exception as e:
            row["bundle_count"] = -1; row["bundle_err"] = str(e)[:100]
        qh, fh, bc = row.get("qdrant_hits", 0), row.get("fts_hits", 0), row.get("bundle_count", 0)
        if qh > 0:
            row["dominant"] = "qdrant"
        elif fh > 0:
            row["dominant"] = "fts"
        elif bc > 0:
            row["dominant"] = "lexical/surrogate"
        else:
            row["dominant"] = "none"
        out["m4"][name].append(row)

print(json.dumps(out, ensure_ascii=False, indent=2))
