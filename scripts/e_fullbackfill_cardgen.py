#!/usr/bin/env python3
"""全量 card-gen backfill: 给所有无卡 knowledge_documents 入队 card-gen, 用(已修饥饿/已关path_opt的)worker
force 跑通豆包, 直到排空。进度落盘 /tmp/e_fullbackfill_progress.json。claim 用 running 锁, 与 app worker 并行安全。"""
import sys, os, json, time, pathlib, traceback
DD = pathlib.Path(os.path.expanduser("~/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "backend"))
from app.db import Database
from app.services.ai import AiService, OPENAI_COMPATIBLE_PROVIDER
from app.services.secrets import MacOSKeychainSecretStore, MemorySecretStore
from app.services import local_model_optimizer as LMO
db = Database(DD / "app.db")
def store(s):
    try:
        st = MacOSKeychainSecretStore(service_name=s, account_name="default"); st.get_api_key(); return st
    except Exception:
        return MemorySecretStore()
def total_cards():
    return db.scalar("SELECT COUNT(1) FROM document_cards")
def no_card_left():
    return db.scalar("SELECT COUNT(1) FROM knowledge_documents kd LEFT JOIN document_cards dc ON dc.knowledge_document_id=kd.id WHERE dc.knowledge_document_id IS NULL")
def prog(d): json.dump(d, open("/tmp/e_fullbackfill_progress.json","w"), ensure_ascii=False, indent=2)
try:
    print("===== 全量 card-gen backfill (豆包) =====")
    ai = AiService(db, {OPENAI_COMPATIBLE_PROVIDER: store("com.yiyu.self-workbench.openai-compatible"),
        "qwen": store("com.yiyu.self-workbench.qwen"), "doubao": store("com.yiyu.self-workbench.doubao"),
        "ai_profile:online_primary": store("com.yiyu.self-workbench.ai-profile.online-primary"),
        "ai_profile:local_text_deep": store("com.yiyu.self-workbench.ai-profile.local-text-deep"),
        "ai_profile:local_vision_ocr": store("com.yiyu.self-workbench.ai-profile.local-vision-ocr"),
        "ai_profile:local_fast": store("com.yiyu.self-workbench.ai-profile.local-fast")})
    print(f"AI ready={getattr(ai.get_health(),'ready','?')}")
    # 入队所有无卡文档的 card-gen
    miss = [str(r[0]) for r in db.fetchall("SELECT kd.id FROM knowledge_documents kd LEFT JOIN document_cards dc ON dc.knowledge_document_id=kd.id WHERE dc.knowledge_document_id IS NULL")]
    enq = LMO.enqueue_local_model_optimization_tasks(db, document_ids=miss, task_types=[LMO.TASK_TYPE_DOCUMENT_CARD]) if miss else {}
    start_cards = total_cards(); start_miss = no_card_left()
    print(f"无卡文档 {len(miss)} 篇, 入队 {enq.get('created','?')} | 起始 cards={start_cards} 待建={start_miss}")
    t0=time.time(); built=0; fails=0; it=0
    MAX_ITERS=2000; MAX_HOURS=8
    while it < MAX_ITERS:
        rr = LMO.run_due_local_model_tasks(db, ai, force=True, batch_size=10)
        p=int(rr.get('processed',0)); f=int(rr.get('failed',0)); built+=p; fails+=f; it+=1
        left = no_card_left(); cards_now = total_cards()
        prog({"iter":it,"processed_total":built,"failed_total":fails,"cards_now":cards_now,
              "no_card_left":left,"elapsed_min":round((time.time()-t0)/60,1),"running":True})
        if it % 5 == 0 or p==0:
            print(f"iter{it}: +{p}/-{f} | cards={cards_now} 待建={left} | {round((time.time()-t0)/60,1)}min")
        if left <= 0 or (p==0 and f==0): break
        if (time.time()-t0)/3600 > MAX_HOURS: print("⏱ 到时限停"); break
    el=time.time()-t0
    end_cards=total_cards()
    print(f">>> 完成 用时 {round(el/60,1)}min | 处理 {built} 失败 {fails} | cards {start_cards}→{end_cards}(+{end_cards-start_cards}) | 剩余无卡 {no_card_left()}")
    prog({"done":True,"processed_total":built,"failed_total":fails,"cards_start":start_cards,"cards_end":end_cards,"no_card_left":no_card_left(),"elapsed_min":round(el/60,1),"running":False})
except Exception:
    print("‼\n"+traceback.format_exc()[-1500:])
print("done")
