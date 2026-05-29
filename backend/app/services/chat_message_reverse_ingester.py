"""[A] V2.5 P0-3 · ChatMessageReverseIngester · 工作台对话反向入库

用户甲 5/23 钦定:
> chat_messages 不能只保留原文.
> 用户贴会议纪要、写判断、提出纠错时, 系统应识别为
>   candidate_fact / judgment / risk / commitment / correction.
> 普通提问不强行入事实库.

B 报告 38 分 §维度二: 工作台对话 1125 条不进 atomic_facts.
本服务把 user role 消息按意图分类:

  factual_assertion → 走 IngestPipeline (user_verbal_fact)
  judgment          → 走 IngestPipeline (user_observation)
  correction        → 走 user_correction_handler
  commitment        → 写 commitments (直写,不走 ingest)
  risk              → 写 risk_signals
  question          → 跳过 (普通提问不入事实库)
  chitchat          → 跳过

规则优先, LLM 可选 (规则 cover 80%, LLM 处理边界).
"""
from __future__ import annotations

import json
import logging
import re
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


MessageIntent = Literal[
    "factual_assertion", "judgment", "correction",
    "commitment", "risk", "question", "chitchat",
]


@dataclass(frozen=True)
class ClassifyResult:
    intent: MessageIntent
    confidence: float
    extracted_subjects: list[str] = field(default_factory=list)
    extracted_numbers: list[str] = field(default_factory=list)
    matched_pattern: str = ""
    # V3 收尾 M5 升级 (用户甲 §M5 §4 必做):
    extracted_persons: list[str] = field(default_factory=list)
    history_refs: list[dict] = field(default_factory=list)     # [{ref_text, ref_type}, ...]
    triggers_clarification: bool = False
    clarification_reason: str = ""


# ─── 分类规则 ─────────────────────────────────────────


_QUESTION_TAILS = ("吗?", "吗？", "?", "？", "什么", "为什么", "如何", "怎么", "怎样")
_QUESTION_HEADS = (
    "请", "帮我", "给我", "麻烦", "能不能", "可不可以",
    "请问", "你能", "AI", "请你",
)

_CORRECTION_PATTERNS = [
    "不对", "错了", "不是", "应该是", "实际是", "纠正一下",
    "你引用的是旧版本", "之前的", "是旧版", "已经更新",
    "实际上",
]

_COMMITMENT_PATTERNS = [
    "我会", "我承诺", "我答应", "我负责", "我来",
    "X月X日前", "之前完成", "下周完成",
    "约定",
]

_RISK_PATTERNS = [
    "担心", "万一", "风险", "可能出问题", "小心",
    "怕的是", "怕他们", "如果出现",
    "隐性风险", "服务质量",
]

_JUDGMENT_PATTERNS = [
    "我觉得", "我判断", "我认为", "我感觉", "可能",
    "也许", "估计", "应该不", "或许",
    "我的看法", "依我看",
]

_FACTUAL_PATTERNS = [
    # 数字 + 单位
    r"\d+\s*(?:万|千|百|所|个|条|份|位)",
    # 日期
    r"\d+\s*月\s*\d+\s*日",
    r"\d{4}-\d{2}-\d{2}",
    # 角色描述
    r"(?:是|为)\s*(?:理事长|秘书长|总经理|项目经理|执行人|负责人)",
]


def _extract_persons(text: str) -> list[str]:
    """V3 收尾 M5 · 抽人物 (中文姓名 + 角色)."""
    persons: list[str] = []
    seen: set[str] = set()
    # 角色 (含姓): 王主任 / 张总 / 李秘书长 / 强哥 / 高老师
    for m in re.finditer(r"([一-龥]{1,2})(主任|总|秘书长|理事长|总经理|项目经理|执行人|负责人|老师|哥|姐|教练|经理)", text):
        p = m.group(0)
        if p not in seen:
            seen.add(p); persons.append(p)
    # 全名: 2-3 字中文 + 后接动词(说/承诺/确认/...)
    for m in re.finditer(r"([一-龥]{2,3})(?=\s*[说承诺确认表示提出反馈])", text):
        p = m.group(1)
        if 2 <= len(p) <= 3 and p not in seen and p not in {"我们", "他们", "你们", "客户", "用户"}:
            seen.add(p); persons.append(p)
    return persons[:8]


def _extract_history_refs(text: str) -> list[dict]:
    """V3 收尾 M5 · 抽历史指代 (复用 historical_material_resolver 的 rule 抽取)."""
    refs: list[dict] = []
    seen: set[str] = set()
    # 月份+合同/协议
    for m in re.finditer(r"([0-9一二三四五六七八九十]{1,2})\s*月(?:份)?(?:签|订)?(?:的)?(补充协议|合同|协议|备忘录|方案)", text):
        rt = m.group(0).strip()
        if rt not in seen:
            seen.add(rt); refs.append({"ref_text": rt[:80], "ref_type": "contract_reference"})
    # 历史指代+名词
    for m in re.finditer(r"(上次|上一[版次份回]|上回|前次|之前的|曾经的?|原来的?|沿用)([一-龥]{0,12}(?:合同|协议|方案|计划|会议|纪要|材料|文件|说明))?", text):
        rt = m.group(0)[:60]
        if rt not in seen:
            seen.add(rt); refs.append({"ref_text": rt, "ref_type": "contract_reference" if "合同" in rt or "协议" in rt else "fact_reference"})
    # 续签/延续
    for m in re.finditer(r"(续签|延续|沿用)([一-龥]{0,12})", text):
        rt = m.group(0)[:50]
        if rt not in seen:
            seen.add(rt); refs.append({"ref_text": rt, "ref_type": "contract_reference"})
    return refs[:5]


_UNCERTAINTY_PATTERNS = [
    "不太清楚", "不知道", "不确定", "可能要确认", "需要核实",
    "好像", "印象中", "记不清", "稍后确认", "回头查一下",
    "暂时不能确定", "得问问", "还要核对",
]


def classify_message(content: str) -> ClassifyResult:
    """规则分类 user 消息意图.

    V3 收尾 M5 升级: 加 _extract_persons / _extract_history_refs / triggers_clarification.
    """
    text = (content or "").strip()
    if not text:
        return ClassifyResult(intent="chitchat", confidence=1.0)
    if len(text) < 10:
        return ClassifyResult(intent="chitchat", confidence=0.8)

    # 提取关键词
    numbers = re.findall(r"\d+\s*(?:万|千|百|所|个|条|份|位|月|日|年)", text)
    has_factual_pattern = any(re.search(p, text) for p in _FACTUAL_PATTERNS)

    # V3 收尾 M5: 人物 / 历史指代 / 待澄清触发 (所有 intent 都抽)
    persons = _extract_persons(text)
    history_refs = _extract_history_refs(text)
    triggers_clarification = any(p in text for p in _UNCERTAINTY_PATTERNS)
    clarification_reason = ""
    if triggers_clarification:
        for p in _UNCERTAINTY_PATTERNS:
            if p in text:
                clarification_reason = f"用户表达不确定: '{p}'"
                break

    # 1. 纠错(优先级最高,因为"实际是"很明确)
    for kw in _CORRECTION_PATTERNS:
        if kw in text:
            return ClassifyResult(
                intent="correction", confidence=0.9,
                extracted_numbers=numbers, matched_pattern=kw,
                extracted_persons=persons, history_refs=history_refs,
                triggers_clarification=triggers_clarification,
                clarification_reason=clarification_reason,
            )

    # 2. 问题 (问号、请求语)
    is_question = (
        any(text.endswith(q) for q in _QUESTION_TAILS)
        or any(text.startswith(h) for h in _QUESTION_HEADS)
    )
    if is_question:
        return ClassifyResult(
            intent="question", confidence=0.85,
            extracted_persons=persons, history_refs=history_refs,
            triggers_clarification=triggers_clarification,
            clarification_reason=clarification_reason,
        )

    # 3. 承诺
    for kw in _COMMITMENT_PATTERNS:
        if kw in text:
            return ClassifyResult(
                intent="commitment", confidence=0.85,
                extracted_numbers=numbers, matched_pattern=kw,
                extracted_persons=persons, history_refs=history_refs,
                triggers_clarification=triggers_clarification,
                clarification_reason=clarification_reason,
            )

    # 4. 风险
    for kw in _RISK_PATTERNS:
        if kw in text:
            return ClassifyResult(
                intent="risk", confidence=0.85,
                extracted_numbers=numbers, matched_pattern=kw,
                extracted_persons=persons, history_refs=history_refs,
                triggers_clarification=triggers_clarification,
                clarification_reason=clarification_reason,
            )

    # 5. 用户判断
    for kw in _JUDGMENT_PATTERNS:
        if kw in text:
            return ClassifyResult(
                intent="judgment", confidence=0.8,
                extracted_numbers=numbers, matched_pattern=kw,
                extracted_persons=persons, history_refs=history_refs,
                triggers_clarification=triggers_clarification,
                clarification_reason=clarification_reason,
            )

    # 6. 事实陈述 (含数字/角色/人物/历史)
    if has_factual_pattern or numbers or persons or history_refs:
        return ClassifyResult(
            intent="factual_assertion", confidence=0.7,
            extracted_numbers=numbers, matched_pattern="numeric/role/person/history",
            extracted_persons=persons, history_refs=history_refs,
            triggers_clarification=triggers_clarification,
            clarification_reason=clarification_reason,
        )

    # 7. 其它视为 chitchat (默认跳过)
    return ClassifyResult(
        intent="chitchat", confidence=0.6,
        extracted_persons=persons, history_refs=history_refs,
        triggers_clarification=triggers_clarification,
        clarification_reason=clarification_reason,
    )


# ─── 入库 ─────────────────────────────────────────────


@dataclass(frozen=True)
class IngestStats:
    total_messages: int = 0
    by_intent: dict[str, int] = field(default_factory=dict)
    facts_written: int = 0
    judgments_written: int = 0
    commitments_written: int = 0
    risks_written: int = 0
    corrections_processed: int = 0
    skipped_questions: int = 0
    skipped_chitchat: int = 0
    errors: list[str] = field(default_factory=list)


def _write_simple_atomic_fact(
    db: _DbLike, *, client_id: str, subject: str, attribute: str,
    value: str, source_type: str, content_role: str, confidence: float,
    evidence_text: str, source_message_id: str,
) -> str | None:
    """简化版 atomic_fact 写入 (不走 IngestPipeline 重逻辑, 仅 demo P0-3 反向入库).

    生产链路应该走 IngestPipeline, 但 demo 这里用直写避免重型调用.
    """
    fact_id = f"af_chat_{uuid.uuid4().hex[:24]}"
    now = _now_iso()
    try:
        db.execute(
            """INSERT INTO atomic_facts (
                id, client_id, subject_text, attribute, value_text,
                value_normalized, confidence, source_v2_chunk_id, source_v2_document_id,
                evidence_text, created_at, updated_at,
                source_type, content_role, actor_type, actor_id,
                speaker_person_id, time_anchor, verification_status,
                confidence_source, update_relation, reasoning_trace_id,
                derived_from_ids_json, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, 'human', 'user',
                      NULL, ?, 'unverified', 'user', 'none', NULL, '[]', 'active')""",
            (
                fact_id, client_id, subject, attribute, value,
                value.lower().strip(), confidence,
                f"[chat:{source_message_id}] {evidence_text[:300]}",
                now, now, source_type, content_role,
                _now_iso(),
            ),
        )
        return fact_id
    except Exception as exc:
        logger.warning("write atomic_fact failed: %s", exc)
        return None


def ingest_chat_message(
    db: _DbLike, *, client_id: str,
    message_id: str, content: str,
    user_id: str = "workbench_user",
) -> tuple[ClassifyResult, dict]:
    """处理 1 条 user chat_message, 返回 (分类结果, action 摘要).

    V3 收尾 M5 升级: 任何 intent 都尝试抽历史指代 / 写人物到 entities /
    触发 clarification 当 triggers_clarification=true.
    """
    cls = classify_message(content)
    action = {
        "intent": cls.intent, "written_fact_ids": [],
        "persons_extracted": cls.extracted_persons,
        "history_refs_extracted": cls.history_refs,
        "triggers_clarification": cls.triggers_clarification,
    }

    # V3 收尾 M5: 即使 intent=question/chitchat 也抽历史指代到 historical_reference_links
    if cls.history_refs:
        try:
            from app.services.historical_material_resolver import resolve_review_references
            text_for_resolve = " ".join(h["ref_text"] for h in cls.history_refs)
            r = resolve_review_references(
                db, client_id=client_id, review_text=content[:2000],
                source_doc_type="chat", source_doc_id=message_id, use_llm=False,
            )
            action["historical_links_written"] = r.get("historical_links_written", 0)
            action["clarifications_from_history"] = r.get("references_clarification", 0)
        except Exception as exc:
            action["history_resolve_error"] = str(exc)

    # V3 收尾 M5: 触发 clarification 当 triggers_clarification 且 intent in (factual/judgment/commitment)
    if cls.triggers_clarification and cls.intent in ("factual_assertion", "judgment", "commitment"):
        try:
            now = _now_iso()
            clar_id = f"clar_chat_{uuid.uuid4().hex[:20]}"
            db.execute(
                """INSERT INTO clarification_records (
                    id, scope_type, scope_id, slot_key, question, status,
                    write_scope_json, resolved_fact_ids_json, reusable,
                    created_at, updated_at
                ) VALUES (?, 'client', ?, ?, ?, 'pending', '{}', '[]', 0, ?, ?)""",
                (
                    clar_id, client_id,
                    f"chat_uncertainty/{message_id[:8]}",
                    f"{cls.clarification_reason}: {content[:120]}",
                    now, now,
                ),
            )
            action["clarification_id"] = clar_id
        except Exception as exc:
            action["clarification_error"] = str(exc)

    if cls.intent in ("question", "chitchat"):
        return cls, action

    # 用 subject = 第一个 number/角色, 或 fallback 到"用户陈述"
    subject = cls.extracted_subjects[0] if cls.extracted_subjects else "用户陈述"
    if cls.extracted_numbers:
        subject = f"用户:{cls.extracted_numbers[0]}"

    if cls.intent == "factual_assertion":
        fid = _write_simple_atomic_fact(
            db, client_id=client_id,
            subject=subject, attribute="用户陈述事实",
            value=content[:300], source_type="user_verbal_fact",
            content_role="fact", confidence=0.7,
            evidence_text=content, source_message_id=message_id,
        )
        if fid:
            action["written_fact_ids"].append(fid)
    elif cls.intent == "judgment":
        fid = _write_simple_atomic_fact(
            db, client_id=client_id,
            subject=subject, attribute="用户判断",
            value=content[:300], source_type="user_observation",
            content_role="observation", confidence=0.6,
            evidence_text=content, source_message_id=message_id,
        )
        if fid:
            action["written_fact_ids"].append(fid)
    elif cls.intent == "commitment":
        try:
            now = _now_iso()
            cid_row = f"com_chat_{uuid.uuid4().hex[:24]}"
            db.execute(
                """INSERT INTO commitments (
                    id, client_id, committer, recipient, commitment_type,
                    content, deadline, status, related_term_ids_json,
                    source_type, source_id, fulfilled_at, created_at, updated_at
                ) VALUES (?, ?, '用户', '客户/项目方', 'verbal', ?, NULL,
                          'pending', '[]', 'chat_message', ?, NULL, ?, ?)""",
                (cid_row, client_id, content[:500], message_id, now, now),
            )
            action["commitment_id"] = cid_row
        except Exception as exc:
            action["error"] = str(exc)
    elif cls.intent == "risk":
        try:
            now = _now_iso()
            rid = f"risk_chat_{uuid.uuid4().hex[:24]}"
            db.execute(
                """INSERT INTO risk_signals (
                    id, client_id, signal_kind, title, description,
                    severity, related_term_ids_json, source_type, source_id,
                    captured_at, status, resolution_note, created_at, updated_at
                ) VALUES (?, ?, 'user_voiced_risk', ?, ?, 'medium', '[]',
                          'chat_message', ?, ?, 'active', '', ?, ?)""",
                (rid, client_id, content[:120], content[:500], message_id, now, now, now),
            )
            action["risk_id"] = rid
        except Exception as exc:
            action["error"] = str(exc)
    elif cls.intent == "correction":
        # 写一个 user_verbal_fact + 标记 correction
        # 生产链路应该接 user_correction_handler 跑完整 supersede
        fid = _write_simple_atomic_fact(
            db, client_id=client_id,
            subject="用户纠错", attribute="纠错原文",
            value=content[:300], source_type="user_verbal_fact",
            content_role="fact", confidence=1.0,
            evidence_text=content, source_message_id=message_id,
        )
        if fid:
            action["written_fact_ids"].append(fid)
            action["correction_marked"] = True
    return cls, action


def batch_ingest_chat_messages(
    db: _DbLike, *, client_id: str, limit: int = 200, dry_run: bool = False,
) -> IngestStats:
    """批量处理一个客户所有 user chat_messages."""
    rows = db.fetchall(
        """SELECT m.id, m.content FROM chat_messages m
           JOIN chat_threads t ON m.thread_id = t.id
           WHERE t.client_id = ? AND m.role = 'user'
             AND length(m.content) > 10
           ORDER BY m.created_at DESC LIMIT ?""",
        (client_id, limit),
    )
    msgs = [dict(r) for r in rows]

    by_intent: dict[str, int] = {}
    facts = judgments = commitments = risks = corrections = skipped_q = skipped_c = 0
    errors: list[str] = []

    for m in msgs:
        cls = classify_message(m["content"])
        by_intent[cls.intent] = by_intent.get(cls.intent, 0) + 1
        if dry_run:
            continue
        try:
            _, action = ingest_chat_message(
                db, client_id=client_id,
                message_id=m["id"], content=m["content"],
            )
            if cls.intent == "factual_assertion":
                facts += 1
            elif cls.intent == "judgment":
                judgments += 1
            elif cls.intent == "commitment":
                commitments += 1 if "commitment_id" in action else 0
            elif cls.intent == "risk":
                risks += 1 if "risk_id" in action else 0
            elif cls.intent == "correction":
                corrections += 1
            elif cls.intent == "question":
                skipped_q += 1
            elif cls.intent == "chitchat":
                skipped_c += 1
            if action.get("error"):
                errors.append(action["error"])
        except Exception as exc:
            errors.append(f"{m['id']}: {exc}")

    return IngestStats(
        total_messages=len(msgs),
        by_intent=by_intent,
        facts_written=facts,
        judgments_written=judgments,
        commitments_written=commitments,
        risks_written=risks,
        corrections_processed=corrections,
        skipped_questions=skipped_q,
        skipped_chitchat=skipped_c,
        errors=errors[:10],
    )
