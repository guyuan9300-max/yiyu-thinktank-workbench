#!/usr/bin/env python3
"""专跑日慈 card-gen 到完成(151篇)。全量已停, 无 claim 竞争。直接处理日慈 queued card-gen。"""
import sys, os, json, time, pathlib, traceback
DD=pathlib.Path(os.path.expanduser("~/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab"))
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"backend"))
from app.db import Database
from app.services.ai import AiService, OPENAI_COMPATIBLE_PROVIDER
from app.services.secrets import MacOSKeychainSecretStore, MemorySecretStore
from app.services import local_model_optimizer as LMO
RC="client_284afd836e"; db=Database(DD/"app.db")
def store(s):
    try:
        st=MacOSKeychainSecretStore(service_name=s,account_name="default"); st.get_api_key(); return st
    except Exception: return MemorySecretStore()
def cards(): return db.scalar("SELECT COUNT(*) FROM document_cards dc JOIN knowledge_documents kd ON kd.id=dc.knowledge_document_id WHERE kd.client_id=?",(RC,))
def prog(d): json.dump(d,open("/tmp/e_rici_progress.json","w"),ensure_ascii=False,indent=2)
try:
    ai=AiService(db,{OPENAI_COMPATIBLE_PROVIDER:store("com.yiyu.self-workbench.openai-compatible"),"qwen":store("com.yiyu.self-workbench.qwen"),"doubao":store("com.yiyu.self-workbench.doubao"),"ai_profile:online_primary":store("com.yiyu.self-workbench.ai-profile.online-primary"),"ai_profile:local_text_deep":store("com.yiyu.self-workbench.ai-profile.local-text-deep"),"ai_profile:local_vision_ocr":store("com.yiyu.self-workbench.ai-profile.local-vision-ocr"),"ai_profile:local_fast":store("com.yiyu.self-workbench.ai-profile.local-fast")})
    print(f"AI ready={getattr(ai.get_health(),'ready','?')} | 日慈起始 cards={cards()}/151")
    tasks=db.fetchall("SELECT * FROM local_model_tasks t JOIN knowledge_documents kd ON kd.id=t.knowledge_document_id WHERE kd.client_id=? AND t.task_type='document_card_generation' AND t.status IN ('queued','running')",(RC,))
    print(f"日慈待跑 card-gen: {len(tasks)} 篇")
    t0=time.time(); ok=0; fail=0
    for i,t in enumerate(tasks):
        td={k:t[k] for k in t.keys()}
        try:
            LMO._process_document_card_task(db,ai,td)
            db.execute("UPDATE local_model_tasks SET status='success', attempts=attempts+1 WHERE id=?",(td['id'],)); ok+=1
        except Exception as e:
            fail+=1
            db.execute("UPDATE local_model_tasks SET status='queued', last_error=? WHERE id=?",(str(e)[:200],td['id']))
        if (i+1)%5==0 or i==len(tasks)-1:
            print(f"  {i+1}/{len(tasks)} | 日慈 cards={cards()}/151 | {round((time.time()-t0)/60,1)}min")
            prog({"done_idx":i+1,"total":len(tasks),"ok":ok,"fail":fail,"cards":cards(),"elapsed_min":round((time.time()-t0)/60,1),"running":True})
    el=time.time()-t0
    print(f">>> 日慈 card-gen 完成 用时 {round(el/60,1)}min | 成功{ok} 失败{fail} | cards {cards()}/151")
    prog({"done":True,"ok":ok,"fail":fail,"cards":cards(),"elapsed_min":round(el/60,1),"running":False})
except Exception:
    print("‼\n"+traceback.format_exc()[-1200:])
print("done")
