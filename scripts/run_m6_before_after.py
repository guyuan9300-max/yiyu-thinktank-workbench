"""M6 · 战略陪伴语义检索改造 before/after 真实对照 (B客户 + A组织).

方法 (诚实):
- before = 旧路径 _retrieve_top_chunks(固定关键词 LIKE, limit=2)
- after  = 新路径 snr.retrieve_dimension(语义优先 + LIKE 兜底)
- 6 维度都量输入差 (chunk 数 / 覆盖 / fallback / 来源构成)。
- essence + business_intro 两维真调 qwen2.5:7b (同模型、同提示模板, 只换喂进去的资料), 对比输出。
- 只读库 + 只调本地 ollama, 不写任何表、不 POST 云端。

跑法: 用主仓库 backend/.venv 的 python, cwd=本 worktree backend。
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

from app.db import Database
from app.services import strategic_narrative_semantic_retriever as snr
from app.services.narrative_collector import _DIMENSION_BASE_KEYWORDS, _retrieve_top_chunks

DATA_DIR = Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2"
DB_PATH = DATA_DIR / "app.db"
CLIENTS = {"B客户": "client_demo_beta", "A组织": "client_demo_alpha"}
DIMS = ["essence", "cooperation", "business_intro", "people", "timeline", "next_steps"]
DIM_CN = {
    "essence": "组织介绍", "cooperation": "合作关系", "business_intro": "业务介绍",
    "people": "关键人物", "timeline": "时间线", "next_steps": "本阶段战略思路",
}
LLM_DIMS = ["essence", "business_intro"]
MODEL = "qwen2.5:7b"


def ollama(prompt: str) -> tuple[str, float]:
    body = json.dumps({
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.3, "num_ctx": 8192},
    }).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate", data=body,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=180) as r:
        resp = json.load(r).get("response", "")
    return resp.strip(), time.time() - t0


def build_prompt(dim: str, chunks_text: list[str]) -> str:
    joined = "\n\n".join(f"[资料{i+1}] {c}" for i, c in enumerate(chunks_text)) or "(无资料)"
    return (
        f"你是战略陪伴顾问。请根据下面的资料，写一段关于该客户「{DIM_CN[dim]}」的内容"
        f"（150-300 字，只用资料中出现的事实，不要编造，没有的就不写）：\n\n"
        f"资料：\n{joined}\n\n请直接输出内容，不要前言。"
    )


def before_chunks(db, cid, dim):
    kws = _DIMENSION_BASE_KEYWORDS.get(dim, (dim,))
    rows = _retrieve_top_chunks(db, cid, kws, limit=2, excerpt_len=400)
    return [(mt, dt, ex) for mt, dt, ex in rows]


def main():
    db = Database(str(DB_PATH))
    out = {"model": MODEL, "db": str(DB_PATH), "clients": {}}
    for name, cid in CLIENTS.items():
        print(f"\n===== {name} ({cid}) =====", flush=True)
        c_rec = {"dims": {}, "llm": {}}
        for dim in DIMS:
            b = before_chunks(db, cid, dim)
            a = snr.retrieve_dimension(
                db, cid, dim,
                like_keywords=_DIMENSION_BASE_KEYWORDS.get(dim, ()),
                like_fallback_fn=_retrieve_top_chunks,
            )
            c_rec["dims"][dim] = {
                "before_chunks": len(b),
                "after_chunks": len(a.chunks),
                "after_candidates": a.candidate_count,
                "after_coverage": round(a.coverage, 3),
                "after_fallback_used": a.fallback_used,
                "after_source_breakdown": a.source_breakdown,
                "warnings": a.warnings,
            }
            print(f"  {dim:14s} before={len(b)}  after={len(a.chunks)} "
                  f"(cand={a.candidate_count}, cov={a.coverage:.2f}, "
                  f"sem={a.source_breakdown.get('semantic',0)}, fb={a.fallback_used})", flush=True)

        for dim in LLM_DIMS:
            b = before_chunks(db, cid, dim)
            a = snr.retrieve_dimension(
                db, cid, dim,
                like_keywords=_DIMENSION_BASE_KEYWORDS.get(dim, ()),
                like_fallback_fn=_retrieve_top_chunks,
            )
            b_text = [ex for _, _, ex in b]
            a_text = [c.excerpt for c in a.chunks]
            print(f"  [LLM] {name}/{dim} 生成 before...", flush=True)
            before_out, bt = ollama(build_prompt(dim, b_text))
            print(f"  [LLM] {name}/{dim} 生成 after...", flush=True)
            after_out, at = ollama(build_prompt(dim, a_text))
            c_rec["llm"][dim] = {
                "before_input_chunks": len(b_text), "after_input_chunks": len(a_text),
                "before_narrative": before_out, "after_narrative": after_out,
                "before_len": len(before_out), "after_len": len(after_out),
                "before_gen_s": round(bt, 1), "after_gen_s": round(at, 1),
            }
            print(f"        before {len(before_out)}字 / after {len(after_out)}字", flush=True)
        out["clients"][name] = c_rec

    dest = Path(__file__).resolve().parents[1] / "docs" / "E_M6_BEFORE_AFTER_RAW.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n写入 {dest}", flush=True)


if __name__ == "__main__":
    main()
