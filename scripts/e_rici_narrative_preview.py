#!/usr/bin/env python3
"""用 worktree 新版 retriever(已切到 knowledge_v2)直接生成日慈 6 段叙事, 打印实物。
不依赖 runtime backend, 不 POST cloud, 只是预览, 让用户在 console 直接看到新 retriever 的产出。
跑完后, 用户重启 backend + UI 点重新生成, 走同一条路 → 在战略陪伴页面看到同质量结果。"""
import sys, os, pathlib, time, traceback, json
DD = pathlib.Path(os.path.expanduser("~/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "backend"))
from app.db import Database
from app.services.ai import AiService, OPENAI_COMPATIBLE_PROVIDER
from app.services.secrets import MacOSKeychainSecretStore, MemorySecretStore
from app.services.narrative_collector import collect_client_fact_bundle
from app.services.narrative_generator import generate_narrative_dimensions, bundle_summary_for_debug

def store(s):
    try:
        st = MacOSKeychainSecretStore(service_name=s, account_name="default"); st.get_api_key(); return st
    except Exception:
        return MemorySecretStore()

db = Database(DD / "app.db")
RICI = "client_284afd836e"
ai = AiService(db, {
    OPENAI_COMPATIBLE_PROVIDER: store("com.yiyu.self-workbench.openai-compatible"),
    "qwen": store("com.yiyu.self-workbench.qwen"),
    "doubao": store("com.yiyu.self-workbench.doubao"),
    "ai_profile:online_primary": store("com.yiyu.self-workbench.ai-profile.online-primary"),
    "ai_profile:local_text_deep": store("com.yiyu.self-workbench.ai-profile.local-text-deep"),
    "ai_profile:local_vision_ocr": store("com.yiyu.self-workbench.ai-profile.local-vision-ocr"),
    "ai_profile:local_fast": store("com.yiyu.self-workbench.ai-profile.local-fast"),
})
print(f"AI ready = {getattr(ai.get_health(),'ready','?')}")

t0 = time.time()
print("\n=== Step 1: collect_client_fact_bundle(日慈)===")
bundle = collect_client_fact_bundle(db, RICI, viewer_user_id="")
summary = bundle_summary_for_debug(bundle)
print(f"  AI 本次看到: {summary['personCount']}人 / {summary['timeAnchorCount']}日期 / "
      f"{summary['atomicAttrCount']}业务事实 / {summary['eventLineCount']}主线 / "
      f"{summary['taskCount']}任务 / {summary['documentCount']}资料 | {round(time.time()-t0,1)}s")

print("\n=== Step 2: generate_narrative_dimensions(LLM, 6 维度, 1-3 分钟)===")
t1 = time.time()
dims, overall, model_used = generate_narrative_dimensions(ai, bundle, db=db)
print(f"  完成 用 {round(time.time()-t1,1)}s | model={model_used}")

print("\n" + "=" * 70)
print("【日慈 · next_steps(下一步)】")
print("=" * 70)
nx = dims.get("next_steps", {})
print(f"narrative:\n{nx.get('narrative','')}")
print(f"\nconfidence: {nx.get('confidence','')}  reason: {nx.get('confidenceReason','')[:120]}")
refs = nx.get("references") or []
print(f"\nreferences({len(refs)}):")
for r in refs[:8]:
    if isinstance(r, dict):
        print(f"  · {str(r.get('title') or r.get('docTitle') or '')[:38]} | {str(r.get('excerpt') or r.get('snippet') or '')[:90]}")
todos = nx.get("structuredTodos") or []
print(f"\nstructuredTodos({len(todos)}):")
for t in todos[:6]:
    if isinstance(t, dict):
        print(f"  · {str(t.get('content') or t.get('title') or '')[:80]}")

print("\n" + "=" * 70)
print(f"6 段总用时 = {round(time.time()-t0,1)}s | overall confidence={overall.get('confidence','')}")
print("=" * 70)
print("done")
