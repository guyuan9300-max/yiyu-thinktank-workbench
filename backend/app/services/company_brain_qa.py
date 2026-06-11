"""[A] V2.6 R3-M3 · CompanyBrainQA · 证据约束自然语言回答层

顾源源 5/23 R3 场景 3:
> 用户在工作台问: '上次我们和 测试论坛A 约定新疆试点资质审批是谁负责?
>                 有没有相关合同或会议纪要支持?'
> 系统不能只查关键词. 要联合查询多张语义表.

升级 V2.4 P1-6 LLM 受限问答:
  · evidence 扩展到 file_identities + contract_structures + historical_reference_links
  · prompt 要让 LLM 区分'合同约定' vs '会议承诺'
  · 没合同证据时不强行说有
  · 主动生成'待正式文件确认'澄清
  · 不确定必须标'待确认'
  · 关键结论必带 [fact:xxx] / [contract:xxx] / [meeting:xxx] 引用

验收:
  · 问答调用 ≥ 3 类数据 (facts/timeline/commitments/risks/contracts/meetings)
  · 能区分合同约定 vs 会议承诺 (100%)
  · 没合同证据时不强行说有 (100%)
  · 能主动生成'待正式文件确认' 澄清 (≥1 条)
  · 回答证据覆盖率 ≥ 90%
  · 严重幻觉 0
"""
from __future__ import annotations

import json
import logging
import re
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class _DbLike(Protocol):
    def execute(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchone(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchall(self, sql: str, params: tuple = ...) -> Any: ...


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:14b"


@dataclass(frozen=True)
class EvidencePack:
    """证据包 — 给 LLM 喂的全部 context."""
    facts: list[dict] = field(default_factory=list)
    contracts: list[dict] = field(default_factory=list)
    files: list[dict] = field(default_factory=list)
    commitments: list[dict] = field(default_factory=list)
    risks: list[dict] = field(default_factory=list)
    clarifications: list[dict] = field(default_factory=list)
    timeline: list[dict] = field(default_factory=list)
    historical_links: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class QAResult:
    answer: str
    evidence_pack_size: int = 0
    citation_count: int = 0
    citation_types: list[str] = field(default_factory=list)  # ['fact', 'contract', 'meeting'...]
    has_hallucination: bool = False
    has_uncertainty_marker: bool = False
    elapsed_seconds: float = 0
    proposed_clarifications: list[str] = field(default_factory=list)


# ─── Evidence Pack 构建 ────────────────────────────


def build_evidence_pack(
    db: _DbLike, client_id: str,
    query_keywords: list[str] | None = None,
    limit_per_table: int = 30,
) -> EvidencePack:
    """构建全方位 evidence pack — 联合查询多张语义表."""
    pack = EvidencePack()

    # 1. atomic_facts (核心事实)
    where = "client_id = ? AND status = 'active'"
    params: list[Any] = [client_id]
    if query_keywords:
        kw_clauses = " OR ".join([
            "(subject_text LIKE ? OR attribute LIKE ? OR value_text LIKE ?)"
            for _ in query_keywords
        ])
        where += f" AND ({kw_clauses})"
        for kw in query_keywords:
            params.extend([f"%{kw}%"] * 3)
    rows = db.fetchall(
        f"""SELECT id, subject_text, attribute, value_text, source_type,
                   confidence, time_anchor, verification_status, status
            FROM atomic_facts WHERE {where}
            ORDER BY confidence DESC LIMIT ?""",
        tuple(params + [limit_per_table]),
    )
    pack.facts.extend(dict(r) for r in rows)

    # 2. contract_structures
    try:
        cs_rows = db.fetchall(
            """SELECT id, party_a, party_b, project_name, signed_at, effective_period,
                      amount, deliverables_json, responsibilities_json, version
               FROM contract_structures WHERE client_id = ?""",
            (client_id,),
        )
        pack.contracts.extend(dict(r) for r in cs_rows)
    except Exception:
        pass

    # 3. file_identities
    try:
        f_rows = db.fetchall(
            """SELECT id, file_name, file_type, file_role, project_name,
                      version, file_time, main_subject, is_authoritative
               FROM file_identities WHERE client_id = ?
               ORDER BY file_time DESC LIMIT 30""",
            (client_id,),
        )
        pack.files.extend(dict(r) for r in f_rows)
    except Exception:
        pass

    # 4. commitments
    try:
        com_rows = db.fetchall(
            """SELECT id, committer, recipient, content, deadline, status
               FROM commitments WHERE client_id = ? AND status != 'cancelled'
               ORDER BY created_at DESC LIMIT 20""",
            (client_id,),
        )
        pack.commitments.extend(dict(r) for r in com_rows)
    except Exception:
        pass

    # 5. risks
    try:
        r_rows = db.fetchall(
            """SELECT id, title, description, severity, status
               FROM risk_signals WHERE client_id = ? AND status = 'active'
               ORDER BY severity DESC LIMIT 20""",
            (client_id,),
        )
        pack.risks.extend(dict(r) for r in r_rows)
    except Exception:
        pass

    # 6. clarifications (pending)
    try:
        clar_rows = db.fetchall(
            """SELECT id, question, slot_key FROM clarification_records
               WHERE scope_type='client' AND scope_id=? AND status='pending'
               ORDER BY created_at DESC LIMIT 20""",
            (client_id,),
        )
        pack.clarifications.extend(dict(r) for r in clar_rows)
    except Exception:
        pass

    # 7. event_line_activities (timeline)
    try:
        tl_rows = db.fetchall(
            """SELECT a.id, a.happened_at, a.actor_name, a.title, a.summary
               FROM event_line_activities a
               JOIN event_lines el ON el.id = a.event_line_id
               WHERE el.primary_client_id = ?
               ORDER BY a.happened_at DESC LIMIT 30""",
            (client_id,),
        )
        pack.timeline.extend(dict(r) for r in tl_rows)
    except Exception:
        pass

    # 8. historical_reference_links (复盘历史关联)
    try:
        hrl_rows = db.fetchall(
            """SELECT ref_text, ref_type, target_table, target_id, match_score
               FROM historical_reference_links WHERE client_id = ?
               ORDER BY resolved_at DESC LIMIT 20""",
            (client_id,),
        )
        pack.historical_links.extend(dict(r) for r in hrl_rows)
    except Exception:
        pass

    return pack


def render_evidence_for_prompt(pack: EvidencePack) -> str:
    """把 EvidencePack 拼成 LLM prompt 可读的 markdown."""
    lines = []
    if pack.contracts:
        lines.append("## 合同(contract_structures)")
        for c in pack.contracts[:10]:
            lines.append(
                f"[contract:{c['id']}] {c['party_a']}↔{c['party_b']} · "
                f"{c['project_name']} · {c['amount']} · 签于 {c['signed_at']} · v={c.get('version','-')}"
            )
            if c.get('responsibilities_json'):
                try:
                    resp = json.loads(c['responsibilities_json'])
                    if resp:
                        lines.append(f"  · 责任: {resp}")
                except Exception:
                    pass
    if pack.files:
        lines.append("\n## 文件清单(file_identities)")
        for f in pack.files[:15]:
            lines.append(
                f"[file:{f['id']}] {f['file_name']} · 类型={f['file_type']} · "
                f"角色={f['file_role']} · 项目={f.get('project_name','-')} · "
                f"权威={'是' if f.get('is_authoritative') else '否'}"
            )
    if pack.facts:
        lines.append("\n## 客户事实(atomic_facts)")
        for fact in pack.facts[:20]:
            lines.append(
                f"[fact:{fact['id']}] {fact['subject_text']} · {fact['attribute']} = "
                f"{fact['value_text']} (源={fact.get('source_type','?')}, "
                f"conf={fact.get('confidence',0):.2f}, status={fact.get('status','?')})"
            )
    if pack.commitments:
        lines.append("\n## 承诺(commitments)")
        for cm in pack.commitments[:15]:
            lines.append(
                f"[commitment:{cm['id']}] {cm['committer']} → {cm.get('recipient','?')}: "
                f"{cm.get('content','')[:120]} (deadline={cm.get('deadline','?')}, "
                f"status={cm.get('status','?')})"
            )
    if pack.risks:
        lines.append("\n## 风险(risk_signals)")
        for r in pack.risks[:10]:
            lines.append(
                f"[risk:{r['id']}] {r['title']} · 严重度={r.get('severity','?')}: "
                f"{r.get('description','')[:100]}"
            )
    if pack.timeline:
        lines.append("\n## 时间线(event_line_activities)")
        for t in pack.timeline[:20]:
            lines.append(
                f"[timeline:{t['id']}] {t.get('happened_at','?')[:10]} · "
                f"{t.get('actor_name','sys')}: {t.get('title','')[:80]}"
            )
    if pack.clarifications:
        lines.append("\n## 待澄清(clarification_records)")
        for cl in pack.clarifications[:10]:
            lines.append(f"[clarification:{cl['id']}] {cl['question'][:150]}")
    return "\n".join(lines)


# ─── Prompt ──────────────────────────────────────────


def _build_qa_prompt(question: str, evidence_text: str) -> str:
    return (
        "你是益语智库的公司大脑助手. 你只能基于下面提供的 evidence 回答问题.\n\n"
        "规则 (顾源源 5/23 R3 钦定):\n"
        "1. 每个关键结论必须用 [fact:xxx] / [contract:xxx] / [file:xxx] / [commitment:xxx] "
        "/ [meeting:xxx] / [risk:xxx] / [timeline:xxx] 引用\n"
        "2. **必须区分'合同约定' vs '会议承诺'**:\n"
        "   - 合同约定: 来自 contract_structures 或 file_type=contract\n"
        "   - 会议承诺: 来自 commitments 或会议纪要 (file_type=meeting_minute)\n"
        "3. **没有合同证据时不能强行说有合同**, 应说'目前只有会议承诺, 缺正式文件支持'\n"
        "4. 不确定内容必须标'待确认' 或 '尚未正式文件确认'\n"
        "5. 不允许编造原文没有的数字/日期/人名\n"
        "6. 如果 evidence 不足, 主动建议'此事需进一步澄清' 并指出具体缺什么\n"
        "7. 答案要简短 (2-4 句), 但必须含证据引用\n\n"
        "Evidence:\n"
        f"{evidence_text}\n\n"
        f"问题: {question}\n\n"
        "答案 (含证据引用 + 待确认标注):\n"
    )


def _call_ollama(prompt: str, timeout: float = 90) -> str:
    data = json.dumps({
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.1, "num_predict": 1200},
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


# ─── 主入口 ──────────────────────────────────────────


def answer_question(
    db: _DbLike, *, client_id: str, question: str,
    query_keywords: list[str] | None = None,
) -> QAResult:
    """证据约束 LLM 回答."""
    t0 = time.time()

    # auto-extract keywords from question (中文 2-gram)
    if query_keywords is None:
        kws = re.findall(r"[一-龥]{2,6}", question)
        query_keywords = [k for k in kws if len(k) >= 2][:8]

    pack = build_evidence_pack(db, client_id, query_keywords)
    evidence_text = render_evidence_for_prompt(pack)
    evidence_size = len(evidence_text)

    if not evidence_text.strip():
        return QAResult(
            answer="_(数据中心暂无相关 evidence)_",
            evidence_pack_size=0,
            elapsed_seconds=time.time() - t0,
            has_uncertainty_marker=True,
        )

    prompt = _build_qa_prompt(question, evidence_text)
    raw = _call_ollama(prompt)
    elapsed = time.time() - t0

    if raw.startswith("__ERROR__"):
        return QAResult(
            answer=f"LLM 错误: {raw[:100]}",
            evidence_pack_size=evidence_size,
            elapsed_seconds=elapsed,
        )

    # 统计 citation
    citation_types: set[str] = set()
    citation_count = 0
    for kind in ["fact", "contract", "file", "commitment", "meeting",
                 "risk", "timeline", "clarification"]:
        matches = re.findall(rf"\[{kind}:[^\]]+\]", raw)
        if matches:
            citation_types.add(kind)
            citation_count += len(matches)

    # 不确定标注检测
    uncertainty_phrases = ["待确认", "尚未正式", "缺正式文件", "需要确认",
                          "暂无信息", "无法确定", "建议澄清", "需进一步澄清"]
    has_uncertainty = any(p in raw for p in uncertainty_phrases)

    # 幻觉粗判: 答案的 3+位数字 不在 evidence 里
    # 剔除引用块再查
    answer_clean = re.sub(r"\[(?:fact|contract|file|commitment|meeting|risk|timeline|clarification):[^\]]+\]", "", raw)
    answer_numbers = set(re.findall(r"\d{3,}", answer_clean))
    evidence_numbers = set(re.findall(r"\d{3,}", evidence_text))
    safe = {"2025", "2026", "100", "200", "300", "400", "500", "800", "1000"} | evidence_numbers
    halluc_nums = answer_numbers - safe
    has_hallucination = bool(halluc_nums)

    # 主动澄清建议
    proposed_clarifications = []
    for line in raw.split("\n"):
        if any(p in line for p in ["建议澄清", "需进一步澄清", "需要问客户", "建议确认"]):
            proposed_clarifications.append(line.strip()[:200])

    return QAResult(
        answer=raw,
        evidence_pack_size=evidence_size,
        citation_count=citation_count,
        citation_types=list(citation_types),
        has_hallucination=has_hallucination,
        has_uncertainty_marker=has_uncertainty,
        elapsed_seconds=elapsed,
        proposed_clarifications=proposed_clarifications[:5],
    )
