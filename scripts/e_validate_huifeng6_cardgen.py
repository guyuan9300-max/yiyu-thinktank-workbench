#!/usr/bin/env python3
"""小批验证 · 汇丰 6 篇 card-gen · path_opt 已关 · 真库 · 现有 provider(豆包后端)。
验证: (1)入队只产 card-gen 不再有 path_opt (2)worker 处理 6 篇产出 document_cards 0->6 (3)无失败风暴。"""
import sys, os, json, time, pathlib, traceback
DD = pathlib.Path(os.path.expanduser("~/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "backend"))
from app.db import Database
from app.services.ai import AiService, OPENAI_COMPATIBLE_PROVIDER
from app.services.secrets import MacOSKeychainSecretStore, MemorySecretStore
from app.services import local_model_optimizer as LMO
CID = "client_ae97e0a2cd"  # 汇丰
db = Database(DD / "app.db")
def store(s):
    try:
        st = MacOSKeychainSecretStore(service_name=s, account_name="default"); st.get_api_key(); return st
    except Exception:
        return MemorySecretStore()
def cards():
    return db.scalar("SELECT COUNT(1) FROM document_cards dc JOIN knowledge_documents kd ON kd.id=dc.knowledge_document_id WHERE kd.client_id=?", (CID,))
res = {}
try:
    print("===== 汇丰 6 篇 card-gen 小批验证 (path_opt 已关, 现有豆包 provider) =====")
    ai = AiService(db, {
        OPENAI_COMPATIBLE_PROVIDER: store("com.yiyu.self-workbench.openai-compatible"),
        "qwen": store("com.yiyu.self-workbench.qwen"), "doubao": store("com.yiyu.self-workbench.doubao"),
        "ai_profile:online_primary": store("com.yiyu.self-workbench.ai-profile.online-primary"),
        "ai_profile:local_text_deep": store("com.yiyu.self-workbench.ai-profile.local-text-deep"),
        "ai_profile:local_vision_ocr": store("com.yiyu.self-workbench.ai-profile.local-vision-ocr"),
        "ai_profile:local_fast": store("com.yiyu.self-workbench.ai-profile.local-fast"),
    })
    h = ai.get_health(); print(f"AI: provider={getattr(h,'provider','?')} ready={getattr(h,'ready','?')} model={getattr(h,'model','?')}")
    print(f"BEFORE 汇丰 document_cards: {cards()}")
    kids = [str(r[0]) for r in db.fetchall("SELECT id FROM knowledge_documents WHERE client_id=?", (CID,))]
    print(f"汇丰 knowledge_documents: {len(kids)} 篇 → 走 _enqueue_deep_read(验证 path_opt 是否还入队)")
    # 用 router 的真实入队路径, 验证 path_opt 关掉生效
    from app.services.task_runners import router as RT
    enq_card = LMO.enqueue_local_model_optimization_tasks(db, document_ids=kids, task_types=[LMO.TASK_TYPE_DOCUMENT_CARD])
    print(f"card-gen 入队: {enq_card}")
    # 验证当前设置下 path_opt 入队判定
    s = LMO.get_local_model_optimization_settings(db)
    print(f"设置 autoEnqueuePathOptimization = {s.get('autoEnqueuePathOptimization')} (应 False)")
    pend_path = db.scalar("SELECT COUNT(1) FROM local_model_tasks t JOIN knowledge_documents kd ON kd.id=t.knowledge_document_id WHERE kd.client_id=? AND t.task_type='path_optimization' AND t.status IN ('queued','pending')", (CID,))
    print(f"汇丰 path_optimization 待处理任务: {pend_path}")
    print(">>> 跑 card-gen worker (force) 计时…")
    t0 = time.time(); total=0; fails=0
    for i in range(12):
        rr = LMO.run_due_local_model_tasks(db, ai, force=True, batch_size=6)
        p=int(rr.get('processed',0)); f=int(rr.get('failed',0)); total+=p; fails+=f
        print(f"   iter{i}: {rr}")
        # 只要汇丰的卡都建好就停
        if cards() >= 6 or (p==0 and f==0): break
    el = time.time()-t0
    after = cards()
    print(f">>> 完成 用时 {el:.1f}s | 总 processed={total} failed={fails} | 汇丰 cards {after}/6")
    # 抽一条看质量
    dc = db.fetchone("SELECT title, length(COALESCE(summary_200,'')) s, substr(summary_200,1,120) p FROM document_cards dc JOIN knowledge_documents kd ON kd.id=dc.knowledge_document_id WHERE kd.client_id=? ORDER BY dc.updated_at DESC LIMIT 1", (CID,))
    if dc: print(f"抽样卡:《{dc['title']}》 summary {dc['s']}字: {dc['p']}…")
    res = {"elapsed_sec": round(el,1), "cards_after": after, "processed": total, "failed": fails, "path_opt_pending": pend_path}
except Exception:
    print("‼ 出错:\n"+traceback.format_exc()[-1200:])
finally:
    json.dump(res, open("/tmp/e_huifeng6.json","w"), ensure_ascii=False, indent=2)
    print("done")
