#!/usr/bin/env python3
"""E 深读全链路验证 · 汇丰 · 豆包 · 计时+评估。
链路: card-generation(LocalAi worker) -> hydrate(deep_read_client) -> 量 coverage。
临时切 provider->doubao, finally 还原。app 必须已退出。"""
import sys, os, json, time, pathlib, traceback
DD = pathlib.Path(os.path.expanduser("~/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "backend"))
from app.db import Database
from app.services.ai import AiService, OPENAI_COMPATIBLE_PROVIDER
from app.services.secrets import MacOSKeychainSecretStore, MemorySecretStore
from app.services import strategic_narrative_semantic_retriever as R
from app.services import document_deep_read_service as DRS
from app.services.local_model_optimizer import (
    enqueue_local_model_optimization_tasks, run_due_local_model_tasks, TASK_TYPE_DOCUMENT_CARD,
)
CID = "client_ae97e0a2cd"  # 汇丰
DIMS = ["essence", "cooperation", "business_intro", "people", "timeline", "next_steps"]
DOUBAO_MODEL = "doubao-seed-2-0-pro-260215"
db = Database(DD / "app.db")

def store(svc):
    try:
        s = MacOSKeychainSecretStore(service_name=svc, account_name="default"); s.get_api_key(); return s
    except Exception:
        return MemorySecretStore()

def snap(tag):
    cards = db.scalar("SELECT COUNT(1) FROM document_cards dc JOIN knowledge_documents kd ON kd.id=dc.knowledge_document_id WHERE kd.client_id=?", (CID,))
    doc_surr = db.scalar("SELECT COUNT(1) FROM knowledge_surrogates WHERE client_id=? AND source_type='document'", (CID,))
    mi = db.scalar("SELECT COUNT(1) FROM knowledge_master_index WHERE client_id=?", (CID,))
    avg_len = db.scalar("SELECT CAST(AVG(length(COALESCE(searchable_text,''))) AS INT) FROM knowledge_master_index WHERE client_id=?", (CID,)) or 0
    sem = {}
    for dim in DIMS:
        try:
            r = R.retrieve_dimension(db, CID, dim, like_fallback_fn=None, data_dir=DD, semantic_enabled=True)
            sem[dim] = (r.source_breakdown.get("semantic", 0), round(r.coverage, 2))
        except Exception as e:
            sem[dim] = ("err", str(e)[:40])
    tot = sum(v[0] for v in sem.values() if isinstance(v[0], int))
    print(f"\n--- [{tag}] 汇丰 --- cards={cards} doc_surrogate={doc_surr} master_index={mi} avg_searchable={avg_len} | 6维语义chunk={tot}")
    print("     " + ", ".join(f"{k}={v[0]}(cov{v[1]})" for k,v in sem.items()))
    return {"cards": cards, "doc_surrogate": doc_surr, "master_index": mi, "avg_searchable_len": avg_len, "total_semantic": tot, "dims": {k: list(v) for k,v in sem.items()}}

op, om = db.get_setting("ai_provider",""), db.get_setting("ai_model","")
res = {"client":"汇丰","model":"doubao"}
try:
    print("===== 全链路验证 · 汇丰 · 豆包 =====")
    db.set_setting("ai_provider","doubao"); db.set_setting("ai_model", DOUBAO_MODEL)
    ai = AiService(db, {
        OPENAI_COMPATIBLE_PROVIDER: store("com.yiyu.self-workbench.openai-compatible"),
        "qwen": store("com.yiyu.self-workbench.qwen"), "doubao": store("com.yiyu.self-workbench.doubao"),
        "ai_profile:online_primary": store("com.yiyu.self-workbench.ai-profile.online-primary"),
        "ai_profile:local_text_deep": store("com.yiyu.self-workbench.ai-profile.local-text-deep"),
        "ai_profile:local_vision_ocr": store("com.yiyu.self-workbench.ai-profile.local-vision-ocr"),
        "ai_profile:local_fast": store("com.yiyu.self-workbench.ai-profile.local-fast"),
    })
    h = ai.get_health(); print(f"AI: provider={getattr(h,'provider','?')} ready={getattr(h,'ready','?')} model={getattr(h,'model','?')}")
    res["before"] = snap("BEFORE")

    kids = [str(r[0]) for r in db.fetchall("SELECT id FROM knowledge_documents WHERE client_id=?", (CID,))]
    print(f"\n汇丰 knowledge_documents: {len(kids)} 篇 → 入队 card-generation")
    enq = enqueue_local_model_optimization_tasks(db, document_ids=kids, task_types=[TASK_TYPE_DOCUMENT_CARD])
    print(f"入队结果: {enq}")

    print(">>> [阶段1] card-generation worker (force) 计时…")
    t0 = time.time(); total_proc = 0
    for i in range(15):
        rr = run_due_local_model_tasks(db, ai, force=True, batch_size=10)
        p = int(rr.get("processed",0)); total_proc += p
        print(f"   iter{i}: {rr}")
        if p == 0: break
    t_card = time.time()-t0
    print(f">>> 阶段1 完成: 处理 {total_proc} 任务, 用时 {t_card:.1f}s")

    print(">>> [阶段2] deep_read_client hydrate (force) 计时…")
    t1 = time.time(); dr = DRS.deep_read_client(db, client_id=CID, ai_service=ai, force=True, data_dir=DD); t_hyd = time.time()-t1
    print(f">>> 阶段2 完成, 用时 {t_hyd:.1f}s, 返回: {json.dumps(dr, ensure_ascii=False)[:200]}")
    res["card_gen_sec"] = round(t_card,1); res["hydrate_sec"] = round(t_hyd,1); res["card_tasks_processed"] = total_proc

    res["after"] = snap("AFTER")
    samp = db.fetchone("SELECT title, substr(searchable_text,1,300) s FROM knowledge_master_index WHERE client_id=? ORDER BY updated_at DESC LIMIT 1",(CID,))
    if samp: print(f"\n--- surrogate 抽样 ---\n《{samp['title']}》\n{samp['s']}")
except Exception:
    print("‼ 出错:\n"+traceback.format_exc()[-1400:])
finally:
    db.set_setting("ai_provider", op); db.set_setting("ai_model", om)
    print(f"\n✅ 已还原 provider/model: {op}/{om}")
    json.dump(res, open("/tmp/e_deepread_huifeng.json","w"), ensure_ascii=False, indent=2)
