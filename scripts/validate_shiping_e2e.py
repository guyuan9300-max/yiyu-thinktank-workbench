"""M2 · 士平 14 篇 document_card_generation 端到端验证.
链路: enqueue → run_due_local_model_tasks(worker,force) → document_cards
      → hydrate_missing_surrogates(force) → reindex_client_vector → semantic probe(5维)。
只动士平(最小客户验证用); 机制客户无关。写 live db(加 document_cards/surrogate/qdrant, 加性)。
"""
from __future__ import annotations

import time
from pathlib import Path

from app.db import Database
from app.services.ai import AiService, OPENAI_COMPATIBLE_PROVIDER
from app.services.secrets import MacOSKeychainSecretStore, MemorySecretStore
from app.services import strategic_narrative_semantic_retriever as snr
from app.services.narrative_collector import _DIMENSION_BASE_KEYWORDS, _retrieve_top_chunks
from app.services.local_model_optimizer import (
    enqueue_local_model_optimization_tasks, run_due_local_model_tasks, TASK_TYPE_DOCUMENT_CARD,
)
from app.services.knowledge_base import hydrate_missing_surrogates, reindex_client_vector

DATA_DIR = Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2"
CID = "client_55f5a8c847"  # 士平——足球
DIMS = ["essence", "cooperation", "business_intro", "people", "timeline"]


def _ss(name):
    try:
        s = MacOSKeychainSecretStore(service_name=name); s.get_api_key(); return s
    except Exception:
        return MemorySecretStore()


def make_ai(db):
    return AiService(db, {
        OPENAI_COMPATIBLE_PROVIDER: _ss("com.yiyu.self-workbench.openai-compatible"),
        "qwen": _ss("com.yiyu.self-workbench.qwen"),
        "doubao": _ss("com.yiyu.self-workbench.doubao"),
        "ai_profile:online_primary": _ss("com.yiyu.self-workbench.ai-profile.online-primary"),
        "ai_profile:local_text_deep": _ss("com.yiyu.self-workbench.ai-profile.local-text-deep"),
        "ai_profile:local_vision_ocr": _ss("com.yiyu.self-workbench.ai-profile.local-vision-ocr"),
        "ai_profile:local_fast": _ss("com.yiyu.self-workbench.ai-profile.local-fast"),
    })


def cards_count(db):
    return db.fetchall("SELECT COUNT(*) FROM document_cards WHERE knowledge_document_id IN (SELECT id FROM knowledge_documents WHERE client_id=?)", (CID,))[0][0]


def surr_stats(db):
    r = db.fetchall("SELECT COUNT(*), CAST(AVG(LENGTH(COALESCE(searchable_text,''))) AS INT) FROM knowledge_master_index WHERE client_id=?", (CID,))[0]
    return r[0], (r[1] or 0)


def probe(db):
    out = {}
    for d in DIMS:
        r = snr.retrieve_dimension(db, CID, d, like_keywords=_DIMENSION_BASE_KEYWORDS.get(d, ()), like_fallback_fn=_retrieve_top_chunks)
        out[d] = (r.source_breakdown.get("semantic", 0), r.source_breakdown.get("like_fallback", 0))
    return out


def main():
    db = Database(str(DATA_DIR / "app.db"))
    print(f"=== 士平 e2e ===", flush=True)
    print(f"改前: document_cards={cards_count(db)} surrogate={surr_stats(db)} probe={probe(db)}", flush=True)
    ai = make_ai(db)

    print("[1] enqueue document_card tasks ...", flush=True)
    enq = enqueue_local_model_optimization_tasks(db, client_id=CID, task_types=[TASK_TYPE_DOCUMENT_CARD])
    print("   enqueue:", enq, flush=True)

    print("[2] run worker (force) 直到排空 ...", flush=True)
    t0 = time.time(); total_p = total_f = 0
    for i in range(20):
        res = run_due_local_model_tasks(db, ai, force=True, batch_size=10)
        p, f = int(res.get("processed", 0)), int(res.get("failed", 0))
        total_p += p; total_f += f
        print(f"   batch{i}: {res}", flush=True)
        if p + f == 0:
            break
    print(f"   worker done: processed={total_p} failed={total_f} 耗时{round(time.time()-t0,1)}s document_cards={cards_count(db)}", flush=True)

    print("[3] hydrate(force=True) 富化 surrogate ...", flush=True)
    hydrate_missing_surrogates(db, data_dir=DATA_DIR, client_id=CID, ai_service=ai, force_refresh=True)
    print(f"   surrogate={surr_stats(db)}", flush=True)

    print("[4] reindex ...", flush=True)
    rr = reindex_client_vector(db, data_dir=DATA_DIR, client_id=CID, ai_service=ai)
    print("   reindex:", rr, flush=True)

    after_probe = probe(db)
    cc, (sc, savg) = cards_count(db), surr_stats(db)
    print("", flush=True)
    print(f"=== 判定 ===", flush=True)
    print(f"document_cards: → {cc} (士平14篇, 覆盖{int(cc/14*100) if cc else 0}%)")
    print(f"surrogate: {sc} 条, 均长 {savg} 字 (v2_instant约231, 目标≥700)")
    sem_pass = sum(1 for d in DIMS if after_probe[d][0] > 0)
    print(f"语义探针5维: {after_probe}")
    print(f"sem>0 维度: {sem_pass}/5 (目标≥3)")
    print(f"结论: {'端到端成立! document_cards→饱满surrogate→sem>0' if cc>=12 and sem_pass>=3 else '未达标, 看上面哪环断'}")


if __name__ == "__main__":
    main()
