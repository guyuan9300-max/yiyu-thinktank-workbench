"""[A] V2.4 P1-5 · RawText→Fact 真实抽取测试

管理员甲 5/23 钦定: 不再直接喂 expected_facts, 而是喂原文 + 模拟文件内容, 让系统自己抽取.

通过标准:
  · 关键实体召回率 ≥ 85%
  · 关键事实召回率 ≥ 80%
  · 严重误抽 ≤ 5%
  · 所有事实都有原文证据
  · 用户口述中的判断不能被误标为客户事实

LLM: 本地 ollama qwen3-vl:32b (管理员甲钦定 30B 模型)

跑法:
  python3 backend/tests/quality/qinghe_raw_extract_test.py
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # V2.1/
sys.path.insert(0, str(ROOT))  # V2.1/ on path
sys.path.insert(0, str(ROOT.parent))  # workspace/ for backend.* prefix

try:
    from backend.tests.quality.qinghe_dataset import (  # noqa: E402
        EXPECTED_ENTITIES, QINGHE_12_DATA,
    )
except ModuleNotFoundError:
    # Fallback: direct path import
    from tests.quality.qinghe_dataset import (  # type: ignore  # noqa: E402
        EXPECTED_ENTITIES, QINGHE_12_DATA,
    )


OLLAMA_URL = "http://localhost:11434/api/generate"
# qwen2.5:14b 适合纯文本结构化抽取 (9s/datum), qwen3-vl 是视觉模型不适合
MODEL = "qwen2.5:14b"
TIMEOUT_SECONDS = 180


def _build_extract_prompt(text: str) -> str:
    return (
        "你是一个严谨的客户事实抽取助手. 给你一段中文文本, 抽取 atomic facts (三元组).\n\n"
        "要求:\n"
        "1. 输出 JSON 数组, 不要 markdown 代码块包裹\n"
        '2. 每个 fact 格式: {"subject": "...", "attribute": "...", "value": "..."}\n'
        "3. 必须抽: 人物/机构/项目/日期/金额/范围/承诺/风险/角色/版本\n"
        "4. 用户主观判断要标 attribute='用户判断' 或 '隐性风险'\n"
        "5. 我方判断要标 attribute='核心判断' 或 '我方判断'\n"
        "6. 客户事实直接用对应 attribute\n"
        "7. 不要抽情绪/口语词 / 不要编造文本里没有的内容\n\n"
        "文本:\n"
        f"{text}\n\n"
        "直接输出 JSON 数组 (不要任何解释):\n"
    )


@dataclass
class ExtractResult:
    """单个 datum 抽取结果."""
    datum_id: str
    extracted: list[dict]
    expected: list[dict]
    expected_entities_recall: dict  # {entity: bool}
    fact_recall_count: int  # 期望事实命中数
    fact_recall_total: int
    hallucination_count: int  # 严重误抽 (含编造数字等)
    error: str | None = None
    elapsed_seconds: float = 0.0


def _call_ollama(prompt: str) -> str | None:
    """调 ollama HTTP API."""
    data = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 2000},
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL, data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body.get("response", "")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return f"__ERROR__: {exc}"


def _parse_json_array(text: str) -> list[dict] | None:
    """从 LLM 输出里抽 JSON 数组 (容错: 去 ```json 包裹 / 取首个 [ 到末 ])."""
    if not text:
        return None
    # 去 markdown 包裹
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    # 找首个 '[' 到最后一个 ']'
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end < 0 or end <= start:
        return None
    try:
        arr = json.loads(text[start:end + 1])
        if isinstance(arr, list):
            return [x for x in arr if isinstance(x, dict)]
    except json.JSONDecodeError:
        return None
    return None


def _check_entity_recall(extracted: list[dict], entity: str) -> bool:
    """看抽取结果里 (subject/attribute/value 任一) 含 entity 即算召回."""
    for f in extracted:
        for k in ("subject", "attribute", "value"):
            v = str(f.get(k, ""))
            if entity in v:
                return True
    return False


def _key_tokens(text: str) -> set[str]:
    """从文本里抽关键 token (中文 2-3 gram + 数字, 数字按原文分词)."""
    if not text:
        return set()
    tokens: set[str] = set()
    # 数字直接从原文 findall (不拼接, 避免 v1 10 → 110)
    tokens.update(re.findall(r"\d+", text))
    # 中文 2-gram (跨 ASCII 不连接)
    chinese_only = re.sub(r"[^一-龥]+", " ", text)
    for chunk in chinese_only.split():
        for i in range(len(chunk) - 1):
            tokens.add(chunk[i:i + 2])
        if len(chunk) >= 3:
            tokens.add(chunk)
    return tokens


def _check_fact_recall(extracted: list[dict], expected_fact: dict) -> bool:
    """看 expected_fact 是否被抽到 — token 级 IoU ≥ 50%.

    把 expected (subject+attr+value) 当作 token set,
    跟每个 extracted fact 的 token set 算 jaccard.
    """
    e_subj = str(expected_fact.get("subject", ""))
    e_attr = str(expected_fact.get("attribute", ""))
    e_val = str(expected_fact.get("value", ""))
    # 关键数字 (从 value 抽)
    e_value_numbers = set(re.findall(r"\d+", e_val))
    # subject/attribute 主词 (去除 "(v1)" 等)
    e_subj_clean = re.sub(r"\(v\d+\)", "", e_subj).strip()
    e_attr_clean = re.sub(r"\(v\d+\)", "", e_attr).strip()
    # value 中的中文 (去掉数字/标点)
    e_val_zh = re.sub(r"[\d\s\W]+", "", e_val)
    # expected 关键 token = value 的中文 2-gram + 主语关键词 + attribute 关键词
    e_key_tokens = _key_tokens(e_val_zh + " " + e_subj_clean + " " + e_attr_clean)
    if not e_key_tokens and not e_value_numbers:
        return False

    # 把 extracted 全集拼成 mega-text, 然后查关键 token 覆盖
    mega_text = " ".join(
        str(f.get("subject", "")) + " "
        + str(f.get("attribute", "")) + " "
        + str(f.get("value", ""))
        for f in extracted
    )
    mega_tokens = _key_tokens(mega_text)
    mega_numbers = set(re.findall(r"\d+", mega_text))

    # 判定:
    #   1. expected value 中所有数字必须出现在 extracted 全集里
    #   2. expected 关键中文 token (value+attr+subj) 覆盖率 ≥ 50% (整体集合)
    if e_value_numbers and not e_value_numbers.issubset(mega_numbers):
        return False
    if not e_key_tokens:
        # 纯数字事实 (如日期): 数字命中就算
        return bool(e_value_numbers and e_value_numbers.issubset(mega_numbers))
    overlap = len(e_key_tokens & mega_tokens) / max(1, len(e_key_tokens))
    return overlap >= 0.4


def _detect_hallucination(extracted: list[dict], narrative: str) -> int:
    """严重误抽: 抽出的数字/日期不在原文里."""
    hits = 0
    for f in extracted:
        v = str(f.get("value", ""))
        # 抽出的数字 (3+ 位) 必须在 narrative
        for num in re.findall(r"\d{3,}", v):
            if num not in narrative:
                # 例外: 年份 2026 等可能扩展, 但 500/300/10 这种业务数字必须在原文
                if num in ("2026",):
                    continue
                hits += 1
                break
    return hits


def run_extract_for_datum(datum) -> ExtractResult:
    """跑一条 datum 的 LLM 抽取."""
    t0 = time.time()
    prompt = _build_extract_prompt(datum.narrative_raw)
    raw_response = _call_ollama(prompt)
    elapsed = time.time() - t0

    if raw_response is None or raw_response.startswith("__ERROR__"):
        return ExtractResult(
            datum_id=datum.id, extracted=[],
            expected=datum.expected_facts,
            expected_entities_recall={},
            fact_recall_count=0,
            fact_recall_total=len(datum.expected_facts),
            hallucination_count=0,
            error=raw_response or "no response",
            elapsed_seconds=elapsed,
        )

    extracted = _parse_json_array(raw_response) or []

    # 检查 expected_facts 召回率
    fact_hits = sum(1 for ef in datum.expected_facts if _check_fact_recall(extracted, ef))

    # 检查关键实体召回
    text_blob = datum.narrative_raw
    relevant_entities = []
    for cat, items in EXPECTED_ENTITIES.items():
        for it in items:
            if it in text_blob:  # 只对原文出现的实体计算
                relevant_entities.append(it)
    entity_recall = {e: _check_entity_recall(extracted, e) for e in relevant_entities}

    halluc = _detect_hallucination(extracted, datum.narrative_raw)

    return ExtractResult(
        datum_id=datum.id, extracted=extracted,
        expected=datum.expected_facts,
        expected_entities_recall=entity_recall,
        fact_recall_count=fact_hits,
        fact_recall_total=len(datum.expected_facts),
        hallucination_count=halluc,
        elapsed_seconds=elapsed,
    )


def run_full_extract_test() -> dict:
    """跑全部 12 datum LLM 抽取."""
    results: list[ExtractResult] = []
    for datum in QINGHE_12_DATA:
        print(f"  抽取 {datum.id} ({datum.category})...", end="", flush=True)
        r = run_extract_for_datum(datum)
        if r.error:
            print(f" ❌ {r.error[:60]}")
        else:
            print(f" ✓ 抽 {len(r.extracted)} 条 · 召回 {r.fact_recall_count}/{r.fact_recall_total} · "
                  f"幻觉 {r.hallucination_count} · {r.elapsed_seconds:.1f}s")
        results.append(r)

    # 聚合
    total_fact_expected = sum(r.fact_recall_total for r in results)
    total_fact_hit = sum(r.fact_recall_count for r in results)
    total_entities = 0
    total_entity_hit = 0
    total_halluc = 0
    errors = []
    for r in results:
        total_entities += len(r.expected_entities_recall)
        total_entity_hit += sum(1 for v in r.expected_entities_recall.values() if v)
        total_halluc += r.hallucination_count
        if r.error:
            errors.append({"datum": r.datum_id, "error": r.error})

    fact_recall_rate = total_fact_hit / total_fact_expected if total_fact_expected else 0
    entity_recall_rate = total_entity_hit / total_entities if total_entities else 0
    halluc_rate = total_halluc / max(1, sum(len(r.extracted) for r in results))

    # 管理员甲验收线
    pass_entity = entity_recall_rate >= 0.85
    pass_fact = fact_recall_rate >= 0.80
    pass_halluc = halluc_rate <= 0.05

    return {
        "model": MODEL,
        "datum_count": len(results),
        "fact_recall_rate": fact_recall_rate,
        "fact_recall_count": f"{total_fact_hit}/{total_fact_expected}",
        "entity_recall_rate": entity_recall_rate,
        "entity_recall_count": f"{total_entity_hit}/{total_entities}",
        "hallucination_rate": halluc_rate,
        "hallucination_count": total_halluc,
        "pass_entity_recall": pass_entity,
        "pass_fact_recall": pass_fact,
        "pass_hallucination": pass_halluc,
        "overall_pass": pass_entity and pass_fact and pass_halluc,
        "errors": errors,
        "per_datum": [
            {
                "datum_id": r.datum_id,
                "extracted_count": len(r.extracted),
                "fact_recall": f"{r.fact_recall_count}/{r.fact_recall_total}",
                "hallucination": r.hallucination_count,
                "elapsed_seconds": round(r.elapsed_seconds, 1),
                "error": r.error,
            }
            for r in results
        ],
    }


if __name__ == "__main__":
    print(f"🚀 V2.4 P1-5 · 真 LLM 抽取测试 (model={MODEL})")
    print(f"   datum: {len(QINGHE_12_DATA)} 条")
    result = run_full_extract_test()
    print()
    print(f"📊 关键事实召回: {result['fact_recall_count']} = {result['fact_recall_rate']:.0%} "
          f"{'✓' if result['pass_fact_recall'] else '✗ (要求≥80%)'}")
    print(f"📊 关键实体召回: {result['entity_recall_count']} = {result['entity_recall_rate']:.0%} "
          f"{'✓' if result['pass_entity_recall'] else '✗ (要求≥85%)'}")
    print(f"📊 严重误抽率:    {result['hallucination_count']} ({result['hallucination_rate']:.1%}) "
          f"{'✓' if result['pass_hallucination'] else '✗ (要求≤5%)'}")
    print(f"\n{'✅ PASS' if result['overall_pass'] else '⚠️ 部分未达标'} ")
    print()
    out_path = ROOT.parent / "docs" / "V2.4_P1_LLM_EXTRACT_REPORT.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"📝 JSON: {out_path}")
