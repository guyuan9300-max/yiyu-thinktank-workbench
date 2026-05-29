#!/usr/bin/env python3
"""E 深读验证 benchmark · 士平 · 用豆包 · 计时 + 效果评估。
临时切 provider→doubao, 跑完还原。app 必须已退出(独占 db+Qdrant)。"""
import sys, os, json, time, pathlib, traceback

DD = pathlib.Path(os.path.expanduser("~/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab"))
REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.db import Database
from app.services.ai import AiService, OPENAI_COMPATIBLE_PROVIDER
from app.services.secrets import MacOSKeychainSecretStore, MemorySecretStore
from app.services import knowledge_base as kb
from app.services import strategic_narrative_semantic_retriever as R
from app.services import document_deep_read_service as DRS

CID = "client_55f5a8c847"  # 士平——足球
DIMS = ["essence", "cooperation", "business_intro", "people", "timeline", "next_steps"]
DOUBAO_MODEL = "doubao-seed-2-0-pro-260215"

db = Database(DD / "app.db")

def build_store(svc):
    try:
        s = MacOSKeychainSecretStore(service_name=svc, account_name="default"); s.get_api_key(); return s
    except Exception:
        return MemorySecretStore()

def snapshot(tag):
    doc_surr = db.scalar("SELECT COUNT(1) FROM knowledge_surrogates WHERE client_id=? AND source_type='document'", (CID,))
    all_surr = db.scalar("SELECT COUNT(1) FROM knowledge_surrogates WHERE client_id=?", (CID,))
    mi = db.scalar("SELECT COUNT(1) FROM knowledge_master_index WHERE client_id=?", (CID,))
    deep = db.scalar("SELECT COUNT(1) FROM knowledge_documents WHERE client_id=? AND deep_read=1", (CID,))
    avg_len = db.scalar("SELECT CAST(AVG(length(COALESCE(searchable_text,''))) AS INT) FROM knowledge_master_index WHERE client_id=?", (CID,)) or 0
    sem = {}
    for dim in DIMS:
        try:
            r = R.retrieve_dimension(db, CID, dim, like_fallback_fn=None, data_dir=DD, semantic_enabled=True)
            sem[dim] = {"semantic_chunks": r.source_breakdown.get("semantic", 0), "coverage": round(r.coverage, 3)}
        except Exception as e:
            sem[dim] = {"err": str(e)[:80]}
    total_sem = sum(v.get("semantic_chunks", 0) for v in sem.values())
    print(f"\n--- [{tag}] 士平 ---")
    print(f"  document surrogate: {doc_surr} | 全部 surrogate: {all_surr} | master_index: {mi} | deep_read=1: {deep} | avg searchable_len: {avg_len}")
    print(f"  6 维语义 chunk 合计: {total_sem}  明细: " + ", ".join(f"{k}={v.get('semantic_chunks','?')}(cov{v.get('coverage','?')})" for k,v in sem.items()))
    return {"doc_surrogate": doc_surr, "all_surrogate": all_surr, "master_index": mi, "deep_read": deep, "avg_searchable_len": avg_len, "total_semantic_chunks": total_sem, "dims": sem}

orig_provider = db.get_setting("ai_provider", "")
orig_model = db.get_setting("ai_model", "")
result = {"client": "士平", "model": "doubao", "before": None, "after": None, "elapsed_sec": None}
try:
    print("===== E 深读 benchmark · 士平 · 豆包 =====")
    print(f"原 provider/model: {orig_provider}/{orig_model}  → 临时切 doubao/{DOUBAO_MODEL}")
    db.set_setting("ai_provider", "doubao")
    db.set_setting("ai_model", DOUBAO_MODEL)
    ai = AiService(db, {
        OPENAI_COMPATIBLE_PROVIDER: build_store("com.yiyu.self-workbench.openai-compatible"),
        "qwen": build_store("com.yiyu.self-workbench.qwen"),
        "doubao": build_store("com.yiyu.self-workbench.doubao"),
        "ai_profile:online_primary": build_store("com.yiyu.self-workbench.ai-profile.online-primary"),
        "ai_profile:local_text_deep": build_store("com.yiyu.self-workbench.ai-profile.local-text-deep"),
        "ai_profile:local_vision_ocr": build_store("com.yiyu.self-workbench.ai-profile.local-vision-ocr"),
        "ai_profile:local_fast": build_store("com.yiyu.self-workbench.ai-profile.local-fast"),
    })
    try:
        h = ai.get_health()
        print(f"AI health: provider={getattr(h,'provider','?')} ready={getattr(h,'ready','?')} model={getattr(h,'model','?')}")
    except Exception as e:
        print(f"AI health 检查异常: {e}")

    result["before"] = snapshot("BEFORE")

    print("\n>>> 跑 deep_read_client(士平, force=True) … 计时中")
    t0 = time.time()
    dr = DRS.deep_read_client(db, client_id=CID, ai_service=ai, force=True, data_dir=DD)
    elapsed = time.time() - t0
    result["elapsed_sec"] = round(elapsed, 1)
    print(f">>> 完成,用时 {elapsed:.1f} 秒。deep_read_client 返回: {json.dumps(dr, ensure_ascii=False)[:300]}")

    result["after"] = snapshot("AFTER")
    # 抽一条 surrogate 看质量
    samp = db.fetchone("SELECT title, substr(searchable_text,1,260) AS s FROM knowledge_master_index WHERE client_id=? ORDER BY updated_at DESC LIMIT 1", (CID,))
    if samp:
        print(f"\n--- surrogate 内容抽样 ---\n  《{samp['title']}》\n  {samp['s']}")
except Exception:
    print("‼ 出错:\n" + traceback.format_exc()[-1200:])
finally:
    db.set_setting("ai_provider", orig_provider)
    db.set_setting("ai_model", orig_model)
    print(f"\n✅ 已还原 provider/model: {orig_provider}/{orig_model}")
    json.dump(result, open("/tmp/e_deepread_shiping.json","w"), ensure_ascii=False, indent=2)
