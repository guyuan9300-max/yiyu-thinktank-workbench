"""M1/M6 机制验证: 在最小客户上跑 deep_read_client(真 qwen), 验证
深读 → document surrogate → 语义可检索(sem 0→>0) 这条通用链路成立。
只动这一个最小客户(验证用), 机制本身客户无关。
"""
from __future__ import annotations

import sys
from pathlib import Path

from app.db import Database
from app.services.ai import AiService, OPENAI_COMPATIBLE_PROVIDER
from app.services.secrets import MacOSKeychainSecretStore, MemorySecretStore
from app.services import document_deep_read_service as drs
from app.services import strategic_narrative_semantic_retriever as snr
from app.services.narrative_collector import _DIMENSION_BASE_KEYWORDS, _retrieve_top_chunks

DATA_DIR = Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2"


def build_secret_store(name: str):
    try:
        s = MacOSKeychainSecretStore(service_name=name)
        s.get_api_key()
        return s
    except Exception:
        return MemorySecretStore()


def make_ai(db):
    return AiService(db, {
        OPENAI_COMPATIBLE_PROVIDER: build_secret_store("com.yiyu.self-workbench.openai-compatible"),
        "qwen": build_secret_store("com.yiyu.self-workbench.qwen"),
        "doubao": build_secret_store("com.yiyu.self-workbench.doubao"),
        "ai_profile:online_primary": build_secret_store("com.yiyu.self-workbench.ai-profile.online-primary"),
        "ai_profile:local_text_deep": build_secret_store("com.yiyu.self-workbench.ai-profile.local-text-deep"),
        "ai_profile:local_vision_ocr": build_secret_store("com.yiyu.self-workbench.ai-profile.local-vision-ocr"),
        "ai_profile:local_fast": build_secret_store("com.yiyu.self-workbench.ai-profile.local-fast"),
    })


def probe(db, cid):
    r = snr.retrieve_dimension(db, cid, "essence",
                               like_keywords=_DIMENSION_BASE_KEYWORDS.get("essence", ()),
                               like_fallback_fn=_retrieve_top_chunks)
    return r.source_breakdown.get("semantic", 0), r.source_breakdown.get("like_fallback", 0)


def main():
    db = Database(str(DATA_DIR / "app.db"))
    # 挑最小的有文档客户(验证快); 排除 CFFC(已 semantic-rich)
    rows = db.fetchall("""
        SELECT id, name, n FROM (
          SELECT c.id AS id, c.name AS name,
                 (SELECT COUNT(*) FROM v2_documents vd WHERE vd.client_id=c.id) AS n
          FROM clients c
        ) WHERE n>0 AND id!='client_a4d1db29a7' ORDER BY n ASC LIMIT 1""")
    cid, name, n = rows[0][0], rows[0][1], rows[0][2]
    print(f"验证客户: {name} ({cid}) 文档 {n}", flush=True)

    before_deep = drs.coverage_for_client(db, cid)["deep_read_done"]
    before_sem, before_fb = probe(db, cid)
    print(f"改前: deep={before_deep} sem={before_sem} fb={before_fb}", flush=True)

    ai = make_ai(db)
    health = ai.get_health()
    print(f"AiService ready={getattr(health,'ready',None)} provider={ai.current_provider() if hasattr(ai,'current_provider') else '?'}", flush=True)

    print("跑 deep_read_client (hydrate 富化 + reindex 嵌入)...", flush=True)
    import time as _t; t0 = _t.time()
    result = drs.deep_read_client(db, client_id=cid, ai_service=ai, force=False)
    print(f"reindex 结果: {result}  耗时 {round(_t.time()-t0,1)}s", flush=True)

    after_deep = drs.coverage_for_client(db, cid)
    after_sem, after_fb = probe(db, cid)
    print(f"改后: deep={after_deep['deep_read_done']}/{after_deep['documents']} "
          f"({int(after_deep['deep_read_coverage']*100)}%) sem={after_sem} fb={after_fb}", flush=True)
    print("")
    print(f"=== 判定 ===", flush=True)
    print(f"深读 surrogate: {before_deep} → {after_deep['deep_read_done']} ({'↑成立' if after_deep['deep_read_done']>before_deep else '✗没增加'})")
    print(f"语义命中: sem {before_sem} → {after_sem} ({'↑机制成立' if after_sem>before_sem else '✗仍0,签名/collection bug未解(M6)'})")


if __name__ == "__main__":
    main()
