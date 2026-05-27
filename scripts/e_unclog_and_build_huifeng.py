#!/usr/bin/env python3
"""清障 + 建汇丰卡: ①DB关path_opt ②清queued path_opt/visual_ocr积压(解worker饥饿) ③直接建汇丰6篇card。真库,豆包。"""
import sys, os, json, time, pathlib, traceback
DD = pathlib.Path(os.path.expanduser("~/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "backend"))
from app.db import Database
from app.services.ai import AiService, OPENAI_COMPATIBLE_PROVIDER
from app.services.secrets import MacOSKeychainSecretStore, MemorySecretStore
from app.services import local_model_optimizer as LMO
CID = "client_ae97e0a2cd"
db = Database(DD / "app.db")
def store(s):
    try:
        st = MacOSKeychainSecretStore(service_name=s, account_name="default"); st.get_api_key(); return st
    except Exception:
        return MemorySecretStore()
def cards():
    return db.scalar("SELECT COUNT(1) FROM document_cards dc JOIN knowledge_documents kd ON kd.id=dc.knowledge_document_id WHERE kd.client_id=?", (CID,))
res={}
try:
    print("===== 清障 + 建汇丰卡 =====")
    # ① DB 关 path_opt
    krow = db.fetchone("SELECT key, value FROM settings WHERE key LIKE '%local_model%optim%' OR key LIKE '%local_ai%optim%' LIMIT 1")
    if krow:
        k=str(krow["key"]); v=json.loads(krow["value"]); v["autoEnqueuePathOptimization"]=False
        db.set_setting(k, json.dumps(v, ensure_ascii=False)); print(f"① DB {k}.autoEnqueuePathOptimization -> False")
    else:
        print("① 未找到 local_model 设置 key(默认已 False,无 DB 覆盖)")
    # ② 清 queued path_opt / visual_ocr 积压
    upd = db.execute("UPDATE local_model_tasks SET status='skipped', last_error='E: path_opt/ocr 链路broken, 清障跳过' WHERE status IN ('queued','running') AND task_type IN ('document_path_optimization','visual_ocr')")
    print(f"② 清 path_opt/visual_ocr queued -> skipped: {getattr(upd,'rowcount','?')} 行")
    # ③ 直接建汇丰 6 篇 card(绕开 worker 队列排序, M5 已证处理逻辑可用)
    ai = AiService(db, {OPENAI_COMPATIBLE_PROVIDER: store("com.yiyu.self-workbench.openai-compatible"),
        "qwen": store("com.yiyu.self-workbench.qwen"), "doubao": store("com.yiyu.self-workbench.doubao"),
        "ai_profile:online_primary": store("com.yiyu.self-workbench.ai-profile.online-primary"),
        "ai_profile:local_text_deep": store("com.yiyu.self-workbench.ai-profile.local-text-deep"),
        "ai_profile:local_vision_ocr": store("com.yiyu.self-workbench.ai-profile.local-vision-ocr"),
        "ai_profile:local_fast": store("com.yiyu.self-workbench.ai-profile.local-fast")})
    print(f"AI ready={getattr(ai.get_health(),'ready','?')} | BEFORE 汇丰 cards={cards()}")
    tasks = db.fetchall("SELECT * FROM local_model_tasks t JOIN knowledge_documents kd ON kd.id=t.knowledge_document_id WHERE kd.client_id=? AND t.task_type='document_card_generation' AND t.status='queued'", (CID,))
    print(f"汇丰 queued card-gen: {len(tasks)} 篇, 逐篇直接处理(计时)…")
    t0=time.time(); ok=0; fail=0; times=[]
    for i,t in enumerate(tasks):
        td={k:t[k] for k in t.keys()}
        ts=time.time()
        try:
            LMO._process_document_card_task(db, ai, td)
            db.execute("UPDATE local_model_tasks SET status='success', attempts=attempts+1 WHERE id=?", (td['id'],))
            ok+=1; dt=time.time()-ts; times.append(dt); print(f"   {i+1}/{len(tasks)} ✅ {dt:.0f}s")
        except Exception as e:
            fail+=1; print(f"   {i+1}/{len(tasks)} ❌ {str(e)[:80]}")
    el=time.time()-t0; after=cards()
    print(f">>> 完成 用时 {el:.0f}s | 成功 {ok} 失败 {fail} | 汇丰 cards {after}/6 | 平均 {sum(times)/len(times):.0f}s/篇" if times else f">>> 用时 {el:.0f}s ok{ok} fail{fail} cards{after}")
    samp=db.fetchone("SELECT title, length(summary_200) s, substr(summary_200,1,140) p FROM document_cards dc JOIN knowledge_documents kd ON kd.id=dc.knowledge_document_id WHERE kd.client_id=? ORDER BY dc.updated_at DESC LIMIT 1",(CID,))
    if samp: print(f"抽样:《{samp['title']}》{samp['s']}字: {samp['p']}…")
    res={"elapsed_sec":round(el),"cards_after":after,"ok":ok,"fail":fail,"avg_sec_per_doc":round(sum(times)/len(times)) if times else None}
except Exception:
    print("‼\n"+traceback.format_exc()[-1200:])
finally:
    json.dump(res, open("/tmp/e_huifeng_build.json","w"), ensure_ascii=False); print("done")
