"""[A] V2.4 P1-6 · LLM 受限问答测试 (evidence-constrained answering)

管理员甲 5/23 钦定:
> LLM 受限问答: 让 LLM 回答, 但必须:
>   · 只能基于数据中心给出的 evidence
>   · 每个关键结论必须带来源
>   · 不允许编造
>   · 不确定必须说不确定
>   · 回答后由评测器检查事实、证据和不确定标注

验收:
  · 50 问 ≥ 42/50
  · 严重幻觉 = 0
  · 关键引用覆盖率 ≥ 90%

LLM: 本地 ollama qwen2.5:14b
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

from app.db import Database  # noqa: E402

try:
    from backend.tests.quality.qinghe_dataset import CLIENT_ID  # noqa: E402
    from backend.tests.quality.qinghe_questions import QINGHE_50_QUESTIONS  # noqa: E402
    from backend.tests.quality.qinghe_runner import setup_db, ingest_all_12_data  # noqa: E402
    from backend.tests.quality.qinghe_runner import run_cross_source_scan  # noqa: E402
    from app.services.atomic_fact_semantic_deriver import derive_all  # noqa: E402
    from app.services.formal_conflict_detector import detect_all as detect_conflicts_all  # noqa: E402
except ModuleNotFoundError:
    sys.path.insert(0, str(ROOT))
    from tests.quality.qinghe_dataset import CLIENT_ID  # type: ignore  # noqa: E402
    from tests.quality.qinghe_questions import QINGHE_50_QUESTIONS  # type: ignore  # noqa: E402


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:14b"
TIMEOUT_SECONDS = 60


def _call_ollama(prompt: str) -> str | None:
    data = json.dumps({
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.1, "num_predict": 800},
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL, data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read().decode("utf-8")).get("response", "")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return f"__ERROR__: {exc}"


def build_evidence_pack(db: Database, client_id: str) -> tuple[str, set[str]]:
    """把 atomic_facts 拼成 evidence markdown + 所有提到的数字集合."""
    rows = db.fetchall(
        """SELECT id, subject_text, attribute, value_text, source_type,
                  confidence, time_anchor, status
           FROM atomic_facts
           WHERE client_id = ?
           ORDER BY confidence DESC, created_at""",
        (client_id,),
    )
    lines = []
    all_numbers: set[str] = set()
    for r in rows:
        d = dict(r)
        status = "active" if d["status"] == "active" else f"⚠ {d['status']}"
        line = (
            f"[fact:{d['id']}] subject={d['subject_text']} "
            f"attribute={d['attribute']} value={d['value_text']} "
            f"source={d['source_type']} conf={d['confidence']:.2f} "
            f"time={d.get('time_anchor','-')} status={status}"
        )
        lines.append(line)
        all_numbers.update(re.findall(r"\d+", d["value_text"] or ""))

    # 加 clarifications + risk_signals + commitments + insights 上下文
    try:
        for r in db.fetchall(
            "SELECT question FROM clarification_records WHERE scope_id=? AND status='pending'",
            (client_id,),
        ):
            lines.append(f"[clarification] {dict(r)['question']}")
    except Exception:
        pass
    try:
        for r in db.fetchall(
            "SELECT title, description FROM risk_signals WHERE client_id=?",
            (client_id,),
        ):
            d = dict(r)
            lines.append(f"[risk] {d['title']}: {d['description']}")
    except Exception:
        pass
    try:
        for r in db.fetchall(
            "SELECT committer, content, deadline FROM commitments WHERE client_id=?",
            (client_id,),
        ):
            d = dict(r)
            lines.append(f"[commitment] {d['committer']} → {d['content']} by {d.get('deadline','?')}")
    except Exception:
        pass

    return "\n".join(lines), all_numbers


def _build_qa_prompt(question: str, evidence: str) -> str:
    return (
        "你是一个严谨的客户事实问答助手. 你只能基于下面提供的 evidence 回答问题.\n\n"
        "规则:\n"
        "1. 答案中每个关键结论必须用 [fact:xxxx] 格式引用 evidence 里的 fact id\n"
        "2. 如果 evidence 里没有相关信息, 直接说 '数据中心暂无信息'\n"
        "3. 不允许编造任何数字、日期、人名、事件\n"
        "4. 不确定的内容必须标注 '待确认'\n"
        "5. 答案要简短 (1-3 句话)\n\n"
        "Evidence:\n"
        f"{evidence}\n\n"
        f"问题: {question}\n\n"
        "答案 (含 [fact:...] 引用):\n"
    )


def evaluate_answer(
    question: dict, answer: str, evidence_numbers: set[str],
) -> dict:
    """评判一道题."""
    if not answer or answer.startswith("__ERROR__"):
        return {
            "correct": False, "has_citation": False,
            "hallucination": False, "error": True,
            "answer": answer or "(empty)",
        }

    # 1. 是否含引用 [fact:...]
    has_citation = bool(re.search(r"\[fact:[a-z0-9_]+", answer.lower()))

    # 2. must_contain 命中
    hits = [kw for kw in question["must_contain"] if kw in answer]
    hit_rate = len(hits) / len(question["must_contain"]) if question["must_contain"] else 1.0

    # 3. must_not_contain
    violations = [kw for kw in question["must_not_contain"] if kw in answer]

    # 4. 幻觉: 答案里的非常规数字 (≥3 位) 不在 evidence_numbers
    #    剔除 [fact:...] / [clarification] 等引用块, 那里的数字是 fact_id 一部分
    answer_clean = re.sub(r"\[(?:fact|clarification|risk|commitment):[^\]]+\]", "", answer)
    answer_numbers = set(re.findall(r"\d{3,}", answer_clean))
    safe_nums = {"2026", "100", "200", "300", "400", "500", "1000"} | evidence_numbers
    halluc_nums = answer_numbers - safe_nums
    has_hallucination = len(halluc_nums) > 0

    # 整体正确判定: hit_rate ≥ 50% AND 无 violations AND 无 hallucination
    correct = hit_rate >= 0.5 and not violations and not has_hallucination

    return {
        "qid": question["qid"],
        "correct": correct,
        "has_citation": has_citation,
        "hit_rate": hit_rate,
        "must_contain_hits": hits,
        "violations": violations,
        "has_hallucination": has_hallucination,
        "hallucination_numbers": list(halluc_nums),
        "answer": answer[:300],
    }


def run_llm_qa_test() -> dict:
    """跑完整 LLM 受限问答测试."""
    import tempfile

    # 建 db + ingest + derive (确保 evidence 完整)
    tmp = Path(tempfile.mkdtemp(prefix="qinghe_p16_"))
    db = setup_db(tmp / "app.db")
    ingest_all_12_data(db)
    run_cross_source_scan(db)
    derive_all(db, CLIENT_ID)
    detect_conflicts_all(db, CLIENT_ID)

    evidence, evidence_numbers = build_evidence_pack(db, CLIENT_ID)
    print(f"  evidence_pack: {len(evidence)} chars, {len(evidence_numbers)} 数字 token")

    results = []
    for i, q in enumerate(QINGHE_50_QUESTIONS, 1):
        prompt = _build_qa_prompt(q.prompt, evidence)
        t0 = time.time()
        raw = _call_ollama(prompt)
        elapsed = time.time() - t0
        q_dict = {
            "qid": q.qid, "prompt": q.prompt,
            "must_contain": list(q.must_contain),
            "must_not_contain": list(q.must_not_contain),
        }
        ev = evaluate_answer(q_dict, raw or "", evidence_numbers)
        ev["elapsed_seconds"] = round(elapsed, 1)
        results.append(ev)
        mark = "✓" if ev["correct"] else "✗"
        cite = "📎" if ev["has_citation"] else "  "
        halluc = "⚠️" if ev["has_hallucination"] else "  "
        print(f"  {i:2d}/50 {mark} {cite} {halluc} {q.qid} ({elapsed:.1f}s) hit={ev['hit_rate']:.0%}")

    correct_count = sum(1 for r in results if r["correct"])
    citation_count = sum(1 for r in results if r["has_citation"])
    halluc_count = sum(1 for r in results if r["has_hallucination"])
    error_count = sum(1 for r in results if r.get("error"))

    return {
        "model": MODEL,
        "total": 50,
        "correct": correct_count,
        "correct_rate": correct_count / 50,
        "citation_count": citation_count,
        "citation_rate": citation_count / 50,
        "hallucination_count": halluc_count,
        "error_count": error_count,
        "pass_correct": correct_count >= 42,
        "pass_no_hallucination": halluc_count == 0,
        "pass_citation": citation_count / 50 >= 0.9,
        "per_question": results,
    }


if __name__ == "__main__":
    print(f"🚀 V2.4 P1-6 · LLM 受限问答测试 ({MODEL})")
    result = run_llm_qa_test()
    print()
    print(f"📊 正确率:       {result['correct']}/50 = {result['correct_rate']:.0%} "
          f"[{'PASS' if result['pass_correct'] else 'FAIL'} ≥42/50]")
    print(f"📊 引用覆盖率:   {result['citation_count']}/50 = {result['citation_rate']:.0%} "
          f"[{'PASS' if result['pass_citation'] else 'FAIL'} ≥90%]")
    print(f"📊 严重幻觉:     {result['hallucination_count']}/50 "
          f"[{'PASS' if result['pass_no_hallucination'] else 'FAIL'} =0]")
    overall = (result['pass_correct'] and result['pass_no_hallucination']
               and result['pass_citation'])
    print(f"\n{'✅ PASS' if overall else '⚠️ 部分未达标'}")
    out = ROOT.parent / "docs" / "V2.4_P1_LLM_QA_REPORT.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"📝 {out}")
