"""M3 · 日慈首批验证: 跑部分 worker(消化已 queued 的 document_card) → hydrate → reindex → 5维探针。
日慈已有 114 queued document_card 任务(原卡死批)。本轮只跑一批验证厚客户链路成立, 不求全量。
"""
from __future__ import annotations

import time
from pathlib import Path

from app.db import Database
from app.services.ai import AiService, OPENAI_COMPATIBLE_PROVIDER
from app.services.secrets import MacOSKeychainSecretStore, MemorySecretStore
from app.services import strategic_narrative_semantic_retriever as snr
from app.services.narrative_collector import _DIMENSION_BASE_KEYWORDS, _retrieve_top_chunks
from app.services.local_model_optimizer import run_due_local_model_tasks
from app.services.knowledge_base import hydrate_missing_surrogates, reindex_client_vector

DATA_DIR = Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2"
CID = "client_284afd836e"  # 日慈基金会
DIMS = ["essence", "cooperation", "business_intro", "people", "timeline", "next_steps"]
TARGET_CARDS = 25  # 首批目标(指令 ≥20)


def _ss(name):
    try:
        s = MacOSKeychainSecretStore(service_name=name); s.get_api_key(); return s
    except Exception:
        return MemorySecretStore()


def make_ai(db):
    keys = ["openai-compatible", "qwen", "doubao", "ai-profile.online-primary",
            "ai-profile.local-text-deep", "ai-profile.local-vision-ocr", "ai-profile.local-fast"]
    names = [OPENAI_COMPATIBLE_PROVIDER, "qwen", "doubao", "ai_profile:online_primary",
             "ai_profile:local_text_deep", "ai_profile:local_vision_ocr", "ai_profile:local_fast"]
    return AiService(db, {n: _ss(f"com.yiyu.self-workbench.{k}") for n, k in zip(names, keys)})


def cards_count(db):
    return db.fetchall("SELECT COUNT(*) FROM document_cards WHERE knowledge_document_id IN (SELECT id FROM knowledge_documents WHERE client_id=?)", (CID,))[0][0]


def probe(db):
    out = {}
    for d in DIMS:
        r = snr.retrieve_dimension(db, CID, d, like_keywords=_DIMENSION_BASE_KEYWORDS.get(d, ()), like_fallback_fn=_retrieve_top_chunks)
        out[d] = (r.source_breakdown.get("semantic", 0), r.source_breakdown.get("like_fallback", 0))
    return out


def main():
    db = Database(str(DATA_DIR / "app.db"))
    before = cards_count(db)
    print(f"=== 日慈首批 === 改前 document_cards={before} probe={probe(db)}", flush=True)
    ai = make_ai(db)

    print(f"[worker] 跑到 document_cards 增至 ~{before+TARGET_CARDS} 或队列空 ...", flush=True)
    t0 = time.time()
    for i in range(40):
        res = run_due_local_model_tasks(db, ai, force=True, batch_size=10)
        cc = cards_count(db)
        print(f"  batch{i}: {res} cards={cc} ({round(time.time()-t0)}s)", flush=True)
        if int(res.get("processed", 0)) + int(res.get("failed", 0)) == 0:
            print("  队列空", flush=True); break
        if cc - before >= TARGET_CARDS:
            print(f"  达首批目标 {TARGET_CARDS}", flush=True); break

    print("[hydrate] 富化 surrogate(非force, 只补有card缺surrogate的) ...", flush=True)
    hydrate_missing_surrogates(db, data_dir=DATA_DIR, client_id=CID, ai_service=ai, force_refresh=False)
    print("[reindex] ...", flush=True)
    rr = reindex_client_vector(db, data_dir=DATA_DIR, client_id=CID, ai_service=ai)
    print(f"  reindex: {rr}", flush=True)

    after = cards_count(db); ap = probe(db)
    sem_pass = sum(1 for d in DIMS if ap[d][0] > 0)
    print("", flush=True)
    print(f"=== 判定 === document_cards {before}→{after}(共234) | 语义 {ap}", flush=True)
    print(f"sem>0 维度: {sem_pass}/6 | business_intro: {'有料' if ap['business_intro'][0]>0 else '仍空'}")
    print(f"结论: {'日慈厚客户链路成立(部分覆盖, 可扩全量)' if after-before>=20 and sem_pass>=2 else '看哪环断'}")


if __name__ == "__main__":
    main()
