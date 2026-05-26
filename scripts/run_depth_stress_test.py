"""战略陪伴页面数据库读取深度强测试 (M1-M5/M8/M9).

对应 ~/Downloads/E线程_战略陪伴数据库读取深度强测试方案_2026-05-26.md。
真库 + 真 ollama qwen2.5:7b, 只读, 不写表/不 POST 云端。
输出 docs/E_STRATEGIC_COMPANION_DEPTH_TEST_REPORT.json。
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

from app.db import Database
from app.services import strategic_narrative_semantic_retriever as snr
from app.services.narrative_collector import (
    _DIMENSION_BASE_KEYWORDS, _retrieve_top_chunks, collect_client_fact_bundle,
)

DATA_DIR = Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2"
DB_PATH = DATA_DIR / "app.db"
VS = DATA_DIR / "vector_store"
CLIENTS = {
    "CFFC": "client_a4d1db29a7",
    "日慈基金会": "client_284afd836e",
    "益语智库": "client_53d82aa249",
}
DIMS = ["essence", "cooperation", "business_intro", "people", "timeline", "next_steps"]
DIM_CN = {"essence": "组织介绍", "cooperation": "合作关系", "business_intro": "业务介绍",
          "people": "关键人物", "timeline": "时间线", "next_steps": "本阶段战略思路"}
LLM_CLIENTS = ["CFFC", "日慈基金会"]
MODEL = "qwen2.5:7b"
# 跨客户隔离 heuristic: 各客户独有标记词
MARKERS = {
    "CFFC": ["基业长青", "鸿鹄", "cfforum"],
    "日慈基金会": ["日慈", "心灵魔法", "心盛", "心益"],
    "益语智库": ["益语智库"],
}


def ollama(prompt: str) -> tuple[str, float]:
    body = json.dumps({"model": MODEL, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0.3, "num_ctx": 8192}}).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r).get("response", "").strip(), round(time.time() - t0, 1)


def build_prompt(dim, chunks_text):
    joined = "\n\n".join(f"[资料{i+1}] {c}" for i, c in enumerate(chunks_text)) or "(无资料)"
    return (f"你是战略陪伴顾问。根据下面资料写一段该客户「{DIM_CN[dim]}」的内容"
            f"（150-300字，只用资料中的事实，没有的不写）：\n\n资料：\n{joined}\n\n直接输出。")


def safe_count(db, sql, params=()):
    try:
        row = db.fetchall(sql, params)
        return int(row[0][list(row[0].keys())[0]]) if row else 0
    except Exception:
        return None


def m1_health(db, name, cid):
    h = {}
    h["v2_documents"] = safe_count(db, "SELECT COUNT(*) c FROM v2_documents WHERE client_id=?", (cid,))
    h["v2_chunks"] = safe_count(db, "SELECT COUNT(*) c FROM v2_chunks vc JOIN v2_documents vd ON vd.id=vc.v2_document_id WHERE vd.client_id=?", (cid,))
    h["atomic_facts"] = safe_count(db, "SELECT COUNT(*) c FROM atomic_facts WHERE client_id=?", (cid,))
    h["commitments"] = safe_count(db, "SELECT COUNT(*) c FROM commitments WHERE client_id=?", (cid,))
    h["contract_structures"] = safe_count(db, "SELECT COUNT(*) c FROM contract_structures WHERE client_id=?", (cid,))
    h["file_identities"] = safe_count(db, "SELECT COUNT(*) c FROM file_identities WHERE client_id=?", (cid,))
    h["risk_signals"] = safe_count(db, "SELECT COUNT(*) c FROM risk_signals WHERE client_id=?", (cid,))
    h["clarification_records"] = safe_count(db, "SELECT COUNT(*) c FROM clarification_records WHERE scope_id=?", (cid,))
    h["data_gaps"] = safe_count(db, "SELECT COUNT(*) c FROM data_gaps WHERE client_id=?", (cid,))
    h["event_line_activities"] = safe_count(db, "SELECT COUNT(*) c FROM event_line_activities a JOIN event_lines e ON e.id=a.event_line_id WHERE e.primary_client_id=?", (cid,))
    h["surrogate_files"] = len(list((VS / cid / "surrogates").glob("*"))) if (VS / cid / "surrogates").exists() else 0
    return h


def main():
    db = Database(str(DB_PATH))
    out = {"meta": {"model": MODEL, "db": str(DB_PATH), "branch": "feat/strategic-narrative-semantic-retrieval"},
           "clients": {}}

    for name, cid in CLIENTS.items():
        print(f"\n========== {name} ({cid}) ==========", flush=True)
        rec = {"client_id": cid, "m1_health": {}, "m2_retrieval": {}, "m3_coverage": {},
               "m4_sources": {}, "m8_isolation": {}, "m9_timing": {}, "m5_llm": {}}

        # M1 健康度
        rec["m1_health"] = m1_health(db, name, cid)
        print(f"  M1 health: {rec['m1_health']}", flush=True)

        # M2 检索路径 + M3 覆盖 (per dim, 用 retrieve_dimension)
        sem_total = 0
        t_dims0 = time.time()
        per_dim_ms = {}
        cross_leak = 0
        for dim in DIMS:
            td0 = time.time()
            b = _retrieve_top_chunks(db, cid, _DIMENSION_BASE_KEYWORDS.get(dim, (dim,)), limit=2, excerpt_len=400)
            a = snr.retrieve_dimension(db, cid, dim,
                                       like_keywords=_DIMENSION_BASE_KEYWORDS.get(dim, ()),
                                       like_fallback_fn=_retrieve_top_chunks)
            dt = round((time.time() - td0) * 1000)
            per_dim_ms[dim] = dt
            sem = a.source_breakdown.get("semantic", 0)
            fb = a.source_breakdown.get("like_fallback", 0)
            sem_total += sem
            path = "semantic" if fb == 0 and sem > 0 else ("fallback_only" if sem == 0 else "semantic+fallback")
            rec["m2_retrieval"][dim] = {
                "semantic_query": snr.DIMENSION_SEMANTIC_QUERIES.get(dim, "")[:40],
                "semantic_hits": sem, "fallback_hits": fb,
                "chunks_candidates": a.candidate_count, "chunks_selected": len(a.chunks),
                "fallback_used": a.fallback_used, "retrieval_path": path,
                "client_filter_applied": True, "coverage": round(a.coverage, 3),
                "warnings": a.warnings,
            }
            rec["m3_coverage"][dim] = {"before_chunks": len(b), "after_selected": len(a.chunks),
                                       "after_candidates": a.candidate_count}
            # M8 跨客户泄漏 heuristic
            other_markers = [m for on, ms in MARKERS.items() if on != name for m in ms]
            for c in a.chunks:
                if any(m in c.excerpt for m in other_markers):
                    cross_leak += 1
        rec["m9_timing"]["per_dim_retrieve_ms"] = per_dim_ms
        rec["m9_timing"]["six_dim_retrieve_s"] = round(time.time() - t_dims0, 1)
        rec["m8_isolation"]["cross_client_marker_hits"] = cross_leak

        # M4 数据源广度 + M3 集成覆盖 (collect_client_fact_bundle 全管线)
        tb0 = time.time()
        bundle = collect_client_fact_bundle(db, cid)
        rec["m9_timing"]["collect_bundle_s"] = round(time.time() - tb0, 1)
        src = {}
        for fname, val in vars(bundle).items():
            if isinstance(val, list):
                src[fname] = len(val)
            elif isinstance(val, dict):
                src[fname] = {k: len(v) if hasattr(v, "__len__") else 1 for k, v in val.items()}
        rec["m4_sources"] = {k: v for k, v in src.items() if v}
        bi = bundle.dimension_chunks.get("business_intro", [])
        proj = sorted(set(c.matched_term for c in bi if c.matched_term != "business_intro"))
        rec["m3_coverage"]["business_intro_projects"] = {"count": len(proj), "terms": proj}
        print(f"  M3 bi projects: {len(proj)} | M9 bundle {rec['m9_timing']['collect_bundle_s']}s | M8 leak {cross_leak}", flush=True)

        out["clients"][name] = rec

    # M5 before/after 六段 (CFFC + 日慈)
    for name in LLM_CLIENTS:
        cid = CLIENTS[name]
        print(f"\n  M5 LLM 六段 before/after: {name}", flush=True)
        llm = {}
        for dim in DIMS:
            b = _retrieve_top_chunks(db, cid, _DIMENSION_BASE_KEYWORDS.get(dim, (dim,)), limit=2, excerpt_len=400)
            a = snr.retrieve_dimension(db, cid, dim,
                                       like_keywords=_DIMENSION_BASE_KEYWORDS.get(dim, ()),
                                       like_fallback_fn=_retrieve_top_chunks)
            bt = [ex for _, _, ex in b]
            at = [c.excerpt for c in a.chunks]
            bo, bsec = ollama(build_prompt(dim, bt))
            ao, asec = ollama(build_prompt(dim, at))
            llm[dim] = {"before_input": len(bt), "after_input": len(at),
                        "before_narrative": bo, "after_narrative": ao,
                        "before_len": len(bo), "after_len": len(ao),
                        "gen_s": {"before": bsec, "after": asec}}
            print(f"    {dim:14s} before {len(bo)}字 / after {len(ao)}字", flush=True)
        out["clients"][name]["m5_llm"] = llm

    dest = Path(__file__).resolve().parents[1] / "docs" / "E_STRATEGIC_COMPANION_DEPTH_TEST_REPORT.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n写入 {dest}", flush=True)


if __name__ == "__main__":
    main()
