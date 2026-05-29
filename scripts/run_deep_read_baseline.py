"""M0 · 全客户文档深读地基基线 (深读修复前冻结).

只读真库 + 本地语义探针(无 LLM 生成)。输出 docs/E_DEEP_READ_M0_BASELINE_REPORT.json。
口径: deep_read_done = document 型 surrogate 数(深加工产物); never_queued = 没进过 local_model_tasks 的文档。
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.db import Database
from app.services import strategic_narrative_semantic_retriever as snr
from app.services.narrative_collector import _DIMENSION_BASE_KEYWORDS, _retrieve_top_chunks

DATA_DIR = Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2"
DB = DATA_DIR / "app.db"
STUCK_HOURS = 24


def one(db, sql, params=()):
    r = db.fetchall(sql, params)
    return r[0][0] if r else 0


def main():
    db = Database(str(DB))
    now = datetime.now(timezone.utc)
    stuck_before = (now - timedelta(hours=STUCK_HOURS)).isoformat()

    g = {
        "v2_documents": one(db, "SELECT COUNT(*) c FROM v2_documents"),
        "document_surrogates": one(db, "SELECT COUNT(*) c FROM knowledge_surrogates WHERE source_type='document'"),
        "all_surrogates": one(db, "SELECT COUNT(*) c FROM knowledge_surrogates"),
        "lmt_total": one(db, "SELECT COUNT(*) c FROM local_model_tasks"),
        "lmt_queued": one(db, "SELECT COUNT(*) c FROM local_model_tasks WHERE status='queued'"),
        "lmt_failed": one(db, "SELECT COUNT(*) c FROM local_model_tasks WHERE status='failed'"),
        "lmt_completed": one(db, "SELECT COUNT(*) c FROM local_model_tasks WHERE status='completed'"),
        "lmt_distinct_docs": one(db, "SELECT COUNT(DISTINCT knowledge_document_id) c FROM local_model_tasks"),
        "lmt_stuck_24h": one(db, "SELECT COUNT(*) c FROM local_model_tasks WHERE status='queued' AND created_at < ?", (stuck_before,)),
    }
    g["never_queued_docs"] = g["v2_documents"] - g["lmt_distinct_docs"]
    g["deep_read_coverage"] = round(g["document_surrogates"] / g["v2_documents"], 4) if g["v2_documents"] else 0

    clients = db.fetchall("SELECT id, name FROM clients ORDER BY name")
    per = []
    for c in clients:
        cid, name = c["id"], c["name"]
        docs = one(db, "SELECT COUNT(*) c FROM v2_documents WHERE client_id=?", (cid,))
        if not docs:
            continue
        doc_surr = one(db, "SELECT COUNT(*) c FROM knowledge_surrogates WHERE client_id=? AND source_type='document'", (cid,))
        all_surr = one(db, "SELECT COUNT(*) c FROM knowledge_surrogates WHERE client_id=?", (cid,))
        queued = one(db, "SELECT COUNT(*) c FROM local_model_tasks WHERE client_id=? AND status='queued'", (cid,))
        stuck = one(db, "SELECT COUNT(*) c FROM local_model_tasks WHERE client_id=? AND status='queued' AND created_at<?", (cid, stuck_before))
        failed = one(db, "SELECT COUNT(*) c FROM local_model_tasks WHERE client_id=? AND status='failed'", (cid,))
        in_queue_docs = one(db, "SELECT COUNT(DISTINCT knowledge_document_id) c FROM local_model_tasks WHERE client_id=?", (cid,))
        # 语义探针: essence 维度
        try:
            r = snr.retrieve_dimension(db, cid, "essence",
                                       like_keywords=_DIMENSION_BASE_KEYWORDS.get("essence", ()),
                                       like_fallback_fn=_retrieve_top_chunks)
            sem = r.source_breakdown.get("semantic", 0)
            fb = r.source_breakdown.get("like_fallback", 0)
        except Exception as e:
            sem, fb = -1, -1
        total_ret = sem + fb
        fallback_ratio = round(fb / total_ret, 2) if total_ret > 0 else None
        cov = round(doc_surr / docs, 3) if docs else 0
        grade = ("semantic-rich" if sem > 0 and cov >= 0.5
                 else "fallback-rich" if all_surr > 0 or fb > 0
                 else "data-thin")
        per.append({
            "client": name, "client_id": cid,
            "documents": docs, "deep_read_done": doc_surr, "surrogate_total": all_surr,
            "deep_read_coverage": cov,
            "queued": queued, "stuck_24h": stuck, "failed": failed,
            "never_queued": max(docs - in_queue_docs, 0),
            "semantic_hits": sem, "fallback_hits": fb, "fallback_ratio": fallback_ratio,
            "reindex_required": bool(sem == 0 and docs > 0),
            "grade": grade,
        })
        print(f"{name:14s} docs={docs:4d} deep={doc_surr:4d}({int(cov*100):3d}%) "
              f"queued={queued} stuck={stuck} neverQ={max(docs-in_queue_docs,0):4d} "
              f"sem={sem} fb={fb} [{grade}]", flush=True)

    out = {"generated_at": now.isoformat(), "stuck_threshold_h": STUCK_HOURS,
           "global": g, "clients": per}
    dest = Path(__file__).resolve().parents[1] / "docs" / "E_DEEP_READ_M0_BASELINE_REPORT.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== 全库 ===")
    print(f"文档 {g['v2_documents']} | 深读 {g['document_surrogates']} ({int(g['deep_read_coverage']*100)}%) | "
          f"从没入队 {g['never_queued_docs']} | 队列queued {g['lmt_queued']} (stuck24h {g['lmt_stuck_24h']}) | failed {g['lmt_failed']}")
    print(f"写入 {dest}")


if __name__ == "__main__":
    main()
