"""[A] V2.6 R3-M2 · HistoricalMaterialResolver · 复盘/任务历史材料回指

顾源源 5/23 R3 优先级 2:
> 用户在复盘里说 '上次合同里说的那个', 系统必须知道是哪份合同.
> 这是公司大脑最重要的能力.

场景: 用户写复盘 -
> "和张真确认了安心妈妈试点学校名单, 按照 5 月签的补充协议执行,
>  但预算需要根据心盛计划调整后的 300 万重新测算."

系统要识别:
  · "5 月签的补充协议" → 哪一份(在 contract_structures 表里)
  · "心盛计划 300 万" → 哪份方案/事实
  · "安心妈妈试点学校名单" → 哪份方案
  · "张真" → entities 表里哪个人

流程:
  1. LLM 抽出 references list
  2. 每个 ref 在 (file_identities / contract_structures / atomic_facts / entities) 找候选
  3. 0 候选 → 创建 clarification (缺历史依据)
  4. 1 候选 → 高置信关联
  5. 多候选 → ambiguous, 创建 clarification (顾源源硬门槛 4 — 不强行判断)
  6. 写 historical_reference_links 表
"""
from __future__ import annotations

import json
import logging
import re
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Protocol

logger = logging.getLogger(__name__)


class _DbLike(Protocol):
    def execute(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchone(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchall(self, sql: str, params: tuple = ...) -> Any: ...


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:14b"


ReferenceType = Literal[
    "contract_reference", "project_reference", "amount_reference",
    "person_reference", "meeting_reference", "fact_reference",
]


@dataclass
class ExtractedReference:
    """从复盘/任务文本里抽出的一个历史引用."""
    ref_text: str  # 原文片段
    ref_type: str  # contract_reference / project_reference / ...
    hint_keywords: list[str] = field(default_factory=list)
    hint_time: str | None = None  # "5 月" / "上次" / "X 月 X 日"
    hint_amount: str | None = None
    hint_party: str | None = None


@dataclass
class ResolveCandidate:
    """匹配候选 (一个 ref 可能匹配 0/1/N 个历史材料)."""
    candidate_id: str  # 在哪张表
    candidate_table: str  # file_identities / contract_structures / atomic_facts / entities
    candidate_summary: str  # 一句话描述
    match_score: float  # 0-1 综合匹配度
    match_reasons: list[str] = field(default_factory=list)


@dataclass
class ResolveResult:
    ref: ExtractedReference
    candidates: list[ResolveCandidate] = field(default_factory=list)
    chosen: ResolveCandidate | None = None  # 唯一高置信选定
    needs_clarification: bool = False
    clarification_question: str = ""


# ─── schema ───────────────────────────────────────────


def ensure_resolver_schema(db: _DbLike) -> None:
    """V2.6 R3-M2 新表."""
    for sql in [
        """CREATE TABLE IF NOT EXISTS historical_reference_links (
            id TEXT PRIMARY KEY,
            client_id TEXT,
            source_doc_type TEXT NOT NULL,  -- review / task / chat / meeting_minute
            source_doc_id TEXT,
            ref_text TEXT NOT NULL,
            ref_type TEXT NOT NULL,
            target_table TEXT,
            target_id TEXT,
            match_score REAL,
            match_reasons_json TEXT NOT NULL DEFAULT '[]',
            needs_clarification INTEGER NOT NULL DEFAULT 0,
            clarification_id TEXT,
            resolved_at TEXT NOT NULL
        )""",
        """CREATE INDEX IF NOT EXISTS idx_hist_ref_links_client
           ON historical_reference_links(client_id, source_doc_type)""",
    ]:
        try:
            db.execute(sql)
        except Exception as exc:
            logger.warning("ensure_resolver_schema failed: %s", exc)


# ─── LLM 抽 references ──────────────────────────────


def _call_ollama(prompt: str, timeout: float = 60, max_tokens: int = 1500) -> str:
    data = json.dumps({
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.1, "num_predict": max_tokens},
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL, data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8")).get("response", "")
    except Exception as exc:
        return f"__ERROR__: {exc}"


def _parse_json_arr(text: str) -> list[dict]:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    s, e = text.find("["), text.rfind("]")
    if s < 0 or e <= s:
        return []
    try:
        arr = json.loads(text[s:e + 1])
        return [x for x in arr if isinstance(x, dict)]
    except json.JSONDecodeError:
        return []


_EXTRACT_REF_PROMPT = """你是公司大脑助手. 给你一段复盘/任务/会议纪要文本, 抽出所有'对历史材料的引用'.

什么是"对历史材料的引用":
  · 提到"上次的合同"/"5 月签的协议"/"之前的方案"
  · 提到"心盛计划的 300 万"/"480 万版本的预算"
  · 提到具体人名("张真"/"强哥")
  · 提到具体项目名("心盛计划"/"安心妈妈试点")
  · 提到旧版口径("原来 20 所学校")

文本:
{text}

请输出 JSON 数组, 每个 item:
[
  {{
    "ref_text": "原文片段 (例:'5 月签的补充协议')",
    "ref_type": "contract_reference | project_reference | amount_reference | person_reference | meeting_reference",
    "hint_keywords": ["补充协议","5 月","心盛"],
    "hint_time": "5 月 或 null",
    "hint_amount": "300 万 或 null",
    "hint_party": "甲方/乙方/张真 或 null"
  }},
  ...
]

直接输出 JSON 数组."""


def extract_references(text: str, *, use_llm: bool = True) -> list[ExtractedReference]:
    if not use_llm or not text:
        return []
    prompt = _EXTRACT_REF_PROMPT.format(text=text[:4000])
    raw = _call_ollama(prompt)
    if raw.startswith("__ERROR__"):
        return []
    arr = _parse_json_arr(raw)
    return [
        ExtractedReference(
            ref_text=str(x.get("ref_text", ""))[:200],
            ref_type=str(x.get("ref_type", "fact_reference")),
            hint_keywords=x.get("hint_keywords") or [],
            hint_time=x.get("hint_time"),
            hint_amount=x.get("hint_amount"),
            hint_party=x.get("hint_party"),
        )
        for x in arr if x.get("ref_text")
    ]


# ─── 候选匹配 ────────────────────────────────────────


def _score_text_overlap(a: str, b: str) -> float:
    """简单字符 overlap 算分."""
    if not a or not b: return 0
    a_set = set(re.findall(r"[一-龥]{2,}|\d+", a))
    b_set = set(re.findall(r"[一-龥]{2,}|\d+", b))
    if not a_set:
        return 0
    return len(a_set & b_set) / len(a_set)


def find_candidates(
    db: _DbLike, ref: ExtractedReference, client_id: str,
) -> list[ResolveCandidate]:
    """在 (file_identities / contract_structures / atomic_facts / entities) 找候选."""
    cands: list[ResolveCandidate] = []
    keywords = ref.hint_keywords + [ref.ref_text[:30]]
    keyword_clause = " OR ".join(["? LIKE concat('%', file_name, '%') OR file_name LIKE ?"
                                  for _ in keywords]) if keywords else "1=1"

    # 1a. contract_reference / project_reference → file_identities
    if ref.ref_type in ("contract_reference", "project_reference"):
        try:
            hint_kw = ref.hint_keywords[0] if ref.hint_keywords else ref.ref_text[:8]
            rows = db.fetchall(
                """SELECT id, file_name, file_type, project_name, version, file_time
                   FROM file_identities WHERE client_id = ?
                     AND (file_name LIKE ? OR project_name LIKE ?)""",
                (client_id, f"%{hint_kw}%", f"%{hint_kw}%"),
            )
            for r in rows:
                d = dict(r)
                score = _score_text_overlap(ref.ref_text, d["file_name"])
                if ref.hint_time and d.get("file_time") and ref.hint_time in (d.get("file_time") or ""):
                    score += 0.3
                if "补充" in ref.ref_text and d["file_type"] == "supplementary_agreement":
                    score += 0.4
                if "合同" in ref.ref_text and d["file_type"] in ("contract", "supplementary_agreement"):
                    score += 0.3
                cands.append(ResolveCandidate(
                    candidate_id=d["id"], candidate_table="file_identities",
                    candidate_summary=f"{d['file_name']} ({d['file_type']}/{d.get('version','?')})",
                    match_score=min(1.0, score),
                    match_reasons=[f"file_name overlap + type/time hint"],
                ))
        except Exception:
            pass

    # 1b. contract_reference → contract_structures (顾源源 R3 核心: 合同结构搜)
    if ref.ref_type in ("contract_reference", "project_reference"):
        try:
            rows = db.fetchall(
                """SELECT id, party_a, party_b, project_name, amount, signed_at, version
                   FROM contract_structures WHERE client_id = ?""",
                (client_id,),
            )
            for r in rows:
                d = dict(r)
                score = 0.0
                # 时间匹配 (5 月 ↔ 2026 年 5 月 XX 日)
                if ref.hint_time and d.get("signed_at"):
                    if re.search(r"5\s*月", ref.hint_time) and "05" in (d["signed_at"] or "") + " " + str(d.get("signed_at","")):
                        score += 0.5
                    elif ref.hint_time and ref.hint_time in (d.get("signed_at") or ""):
                        score += 0.5
                # project_name 关键词
                for kw in ref.hint_keywords:
                    if kw in (d.get("project_name") or ""):
                        score += 0.3
                # "补充" 加成
                if "补充" in ref.ref_text and d.get("version") and "v2" in (d["version"] or ""):
                    score += 0.3
                if score >= 0.3:  # 至少时间或项目匹配
                    cands.append(ResolveCandidate(
                        candidate_id=d["id"], candidate_table="contract_structures",
                        candidate_summary=(
                            f"{d['party_a']}↔{d['party_b']} · {d['project_name']} · "
                            f"{d['amount']} · {d['signed_at']}"
                        ),
                        match_score=min(1.0, score),
                        match_reasons=["合同结构时间+项目+版本匹配"],
                    ))
        except Exception:
            pass

    # 2a. amount_reference → contract_structures (顾源源 R3 钦定 — 金额优先查合同)
    if ref.ref_type == "amount_reference" and ref.hint_amount:
        try:
            # 抽出 hint_amount 的数字 (300 → 找 "300 万"包含)
            amount_num = re.findall(r"\d+", ref.hint_amount or "")
            if amount_num:
                num = amount_num[0]
                rows = db.fetchall(
                    """SELECT id, party_a, party_b, project_name, amount, signed_at
                       FROM contract_structures WHERE client_id = ?
                         AND amount LIKE ?""",
                    (client_id, f"%{num}%"),
                )
                for r in rows:
                    d = dict(r)
                    cands.append(ResolveCandidate(
                        candidate_id=d["id"], candidate_table="contract_structures",
                        candidate_summary=(
                            f"{d['project_name']} {d['amount']} ({d['signed_at']})"
                        ),
                        match_score=0.85,
                        match_reasons=[f"合同金额含 {num}"],
                    ))
        except Exception:
            pass

    # 2b. amount_reference → atomic_facts (value 含金额, 作为补充)
    if ref.ref_type == "amount_reference" and ref.hint_amount:
        try:
            rows = db.fetchall(
                """SELECT id, subject_text, attribute, value_text, source_type
                   FROM atomic_facts WHERE client_id = ? AND status = 'active'
                     AND value_text LIKE ?""",
                (client_id, f"%{ref.hint_amount}%"),
            )
            for r in rows[:5]:
                d = dict(r)
                cands.append(ResolveCandidate(
                    candidate_id=d["id"], candidate_table="atomic_facts",
                    candidate_summary=f"{d['subject_text']}·{d['attribute']}={d['value_text']}",
                    match_score=0.6,
                    match_reasons=[f"value 含 {ref.hint_amount}"],
                ))
        except Exception:
            pass

    # 3. person_reference → entities + atomic_facts (subject=人名)
    if ref.ref_type == "person_reference":
        try:
            rows = db.fetchall(
                """SELECT id, subject_text, attribute, value_text
                   FROM atomic_facts WHERE client_id = ? AND status = 'active'
                     AND subject_text LIKE ?
                   LIMIT 5""",
                (client_id, f"%{ref.ref_text[:8]}%"),
            )
            for r in rows:
                d = dict(r)
                cands.append(ResolveCandidate(
                    candidate_id=d["id"], candidate_table="atomic_facts",
                    candidate_summary=f"{d['subject_text']}·{d['attribute']}={d['value_text']}",
                    match_score=0.7,
                    match_reasons=[f"subject 含 {ref.ref_text[:8]}"],
                ))
        except Exception:
            pass

    # 排序
    cands.sort(key=lambda c: -c.match_score)
    return cands[:5]


def resolve_one(
    db: _DbLike, ref: ExtractedReference, client_id: str,
    *, ambiguous_threshold: float = 0.15,
) -> ResolveResult:
    """匹配一个 reference, 决定: 唯一选 / 多候选进澄清 / 无候选进澄清."""
    cands = find_candidates(db, ref, client_id)
    result = ResolveResult(ref=ref, candidates=cands)

    if not cands:
        result.needs_clarification = True
        result.clarification_question = (
            f"复盘中提到的「{ref.ref_text}」, 系统在客户档案中没找到对应的历史材料. "
            f"请补充资料或确认这是新事项."
        )
        return result

    top = cands[0]
    if len(cands) == 1 and top.match_score >= 0.5:
        result.chosen = top
        return result

    # 多候选: 看第一名 vs 第二名差距
    if len(cands) >= 2 and (top.match_score - cands[1].match_score) >= ambiguous_threshold and top.match_score >= 0.5:
        result.chosen = top
        return result

    # 模糊 - 进澄清 (顾源源硬门槛 4: 不强行判断)
    result.needs_clarification = True
    options_text = "\n".join(
        f"  · 候选 {i+1}: {c.candidate_summary} (match {c.match_score:.2f})"
        for i, c in enumerate(cands[:3])
    )
    result.clarification_question = (
        f"复盘中提到的「{ref.ref_text}」, 系统找到 {len(cands)} 个可能的历史材料:\n"
        f"{options_text}\n请确认指的是哪一个."
    )
    return result


# ─── 主入口 ──────────────────────────────────────────


def resolve_review_references(
    db: _DbLike, *,
    client_id: str, review_text: str,
    source_doc_id: str | None = None,
    source_doc_type: str = "review",
    use_llm: bool = True,
) -> dict:
    """处理一段复盘/任务文本, 抽 reference 并匹配历史材料."""
    ensure_resolver_schema(db)
    refs = extract_references(review_text, use_llm=use_llm)
    results: list[ResolveResult] = []
    written_clarifications = 0
    written_links = 0

    for ref in refs:
        r = resolve_one(db, ref, client_id)
        results.append(r)

        # 写 historical_reference_links
        link_id = f"hrl_{uuid.uuid4().hex[:24]}"
        clar_id = None
        if r.needs_clarification:
            # 写 clarification
            clar_id = f"clar_hrl_{uuid.uuid4().hex[:20]}"
            try:
                now = _now_iso()
                db.execute(
                    """INSERT INTO clarification_records (
                        id, scope_type, scope_id, slot_key, question, status,
                        write_scope_json, resolved_fact_ids_json, reusable,
                        created_at, updated_at
                    ) VALUES (?, 'client', ?, ?, ?, 'pending', ?, '[]', 0, ?, ?)""",
                    (
                        clar_id, client_id,
                        f"hist_ref/{r.ref.ref_type}/{ref.ref_text[:30]}",
                        r.clarification_question,
                        json.dumps({
                            "source_doc_type": source_doc_type,
                            "ref_text": ref.ref_text,
                            "ref_type": ref.ref_type,
                            "candidates": [
                                {"id": c.candidate_id, "table": c.candidate_table,
                                 "summary": c.candidate_summary, "score": c.match_score}
                                for c in r.candidates
                            ],
                        }, ensure_ascii=False),
                        now, now,
                    ),
                )
                written_clarifications += 1
            except Exception as exc:
                logger.warning("write clarification failed: %s", exc)

        try:
            db.execute(
                """INSERT INTO historical_reference_links (
                    id, client_id, source_doc_type, source_doc_id,
                    ref_text, ref_type, target_table, target_id,
                    match_score, match_reasons_json, needs_clarification,
                    clarification_id, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    link_id, client_id, source_doc_type, source_doc_id,
                    ref.ref_text, ref.ref_type,
                    r.chosen.candidate_table if r.chosen else None,
                    r.chosen.candidate_id if r.chosen else None,
                    r.chosen.match_score if r.chosen else None,
                    json.dumps(r.chosen.match_reasons if r.chosen else [], ensure_ascii=False),
                    1 if r.needs_clarification else 0,
                    clar_id, _now_iso(),
                ),
            )
            written_links += 1
        except Exception as exc:
            logger.warning("write hrl failed: %s", exc)

    # 统计
    chosen_n = sum(1 for r in results if r.chosen)
    return {
        "references_extracted": len(refs),
        "references_resolved": chosen_n,
        "references_clarification": written_clarifications,
        "historical_links_written": written_links,
        "details": [
            {
                "ref": r.ref.ref_text,
                "type": r.ref.ref_type,
                "chosen": r.chosen.candidate_summary if r.chosen else None,
                "score": r.chosen.match_score if r.chosen else None,
                "needs_clarification": r.needs_clarification,
                "candidates_count": len(r.candidates),
            }
            for r in results
        ],
    }
