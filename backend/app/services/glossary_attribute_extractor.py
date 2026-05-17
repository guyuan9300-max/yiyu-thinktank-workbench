"""AI 抽取 glossary_attributes 候选 - 让任何客户都能自动用上字典权威档案.

机制 (跟 P0 三表保持一致):
1. 从该客户的 atomic_facts + client_glossary 出发, 让 LLM 抽 N 条候选 attribute
2. 写入 glossary_attributes 表, verification_status='pending'
3. 用户在审核 UI 看到候选, 选 verify / reject / edit
4. 只有 verified 的 attribute 会被 chat / narrative 引用

不硬编码任何客户特定信息, 适配任意公司。
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


GENERIC_TERMS_BLACKLIST: set[str] = {
    # 通用业务术语 — 任何机构都用, 没客户专属价值
    "SOP", "sop", "工作坊", "工作流程", "标准操作规程", "标准化流程",
    "心理咨询", "心理辅导", "心理服务", "心理评估", "心理支持",
    "培训", "课程", "教学", "教程", "学习", "课件",
    "项目管理", "项目执行", "项目实施", "项目运营", "项目运维",
    "流程", "制度", "标准", "评估", "方案", "体系", "计划", "报告", "系统",
    "目标", "策略", "战略", "规划", "决策", "管理",
    "财务管理", "人力资源", "团队管理", "组织管理",
    "服务", "活动", "工作", "运营", "执行",
    # 通用心理学/教育学概念 (百科级)
    "心理健康", "心理压力", "心理疏导", "心理干预",
    "青少年心理", "成长", "教育", "学校教育",
}


def is_generic_term(term: str) -> bool:
    """判断 term 是否通用术语 (不该进客户专属字典)."""
    t = (term or "").strip()
    if not t:
        return True
    # 完全匹配
    if t in GENERIC_TERMS_BLACKLIST or t.lower() in GENERIC_TERMS_BLACKLIST:
        return True
    # 太短的通用名词 (2-3 字, 没有上下文修饰)
    if len(t) <= 3 and not any(c.isascii() for c in t):
        # 例外: 长度 ≤3 但含机构名特征 (例 "日慈" 不抽)
        # 实际机构名一般 ≥ 4 字 (XX 基金会), 简称 2-3 字也少见
        # 留给字典 term 本身的过滤, 这里不强拒
        pass
    return False


CANDIDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "term": {"type": "string", "description": "字典中已存在的 term, 必须精确匹配 (字典外的不要抽)"},
                    "attribute_name": {"type": "string", "description": "属性名, 例: '2023年度支出', '项目启动时间', '理事会成员-第3位理事'"},
                    "value_category": {"type": "string", "enum": ["amount", "date", "count", "location", "person", "rating", "text"]},
                    "value_text": {"type": "string", "description": "原文表述, 例: '200.49 万元'"},
                    "value_normalized": {"type": ["number", "null"], "description": "数值归一化, 元/年/数量等 (无法归一时为 null)"},
                    "value_unit": {"type": "string", "description": "单位, 例: '元', '人', '省'"},
                    "scope": {"type": "string", "description": "口径, 例: 'annual', '项目累计', '机构当前', '现任'"},
                    "as_of_date": {"type": ["string", "null"], "description": "数据有效截止日期 YYYY-MM-DD"},
                    "source_evidence": {"type": "string", "description": "证据来源简述, 最长 80 字"},
                    "confidence": {"type": "number", "description": "0-1 置信度"},
                },
                "required": ["term", "attribute_name", "value_text", "confidence"],
            },
        }
    },
    "required": ["candidates"],
}


PROMPT_TEMPLATE = """\
你是数据中心质量保障员。任务: 从下面客户档案中, 抽取「字典已有 term 的关键属性」, 等待人工审核进入字典权威档案。

# 抽取目标
请尽可能抽出 **30-50 条 candidate**, 覆盖各类业务关键事实。规则:

1. **只抽字典中已存在 term 的属性** — 字典里没有的 term, 即使资料里有也不抽。
2. 优先抽 (按价值递减):
   a. 金额 (年度支出/累计募捐/项目预算/合作金额) → amount
   b. 日期 (项目启动/重大事件/成立时间) → date
   c. 数量 (惠及人数/覆盖省份/期数/培训人数) → count
   d. 地点 (总部/覆盖范围) → location
   e. 人物 (理事会成员/创始人/负责人/秘书长) → person
   f. 评级 (社会组织评估等级/认证) → rating
   g. 业务定义 (项目核心目标/方法论核心) → text
3. **同一字段不同 scope 必须分别抽多条** (例: 覆盖-机构当前 vs 覆盖-项目累计)。
4. **同一字段多源冲突时, 全部抽出**, 让人选哪个为权威 (不要预选)。
5. **attribute_name 简短可读** (15 字内), 但必须明确字段含义。
6. **value_text 必须完整、明确** — 不是句子残尾, 不是问句, 不是带"等"省略。
7. as_of_date 从原文提取 (YYYY-MM-DD), 没有就 null。
8. source_evidence 简短引用证据 (含文档名)。
9. confidence: 资料明确=0.9-1.0, 推断=0.5-0.7, 不确定不要抽 (< 0.5)。
10. **❌ 严禁抽通用术语**: SOP / 工作坊 / 心理咨询 / 培训 / 项目管理 / 流程 / 制度 /
    标准 / 评估 / 方案 / 体系 / 课程 / 计划 / 报告 / 系统 等行业通用概念, 不该作为 term 抽。
    只抽**客户独有**的: 机构名 (日慈基金会) / 项目名 (心盛计划) / 客户专属方法
    (朋辈关怀员/学校成长画像) / 客户专属人员 (张真老师/笑雨老师) 的属性。
11. **❌ 严禁抽通用定义**: "心理咨询=专业人员提供心理疏导" 这种百度百科级定义不抽,
    只抽该客户**在该术语上的独特实践**, 例如"心理咨询" 在日慈的服务对象/培训课时/收费标准。

# 字典已有 term (只能抽这些)
{glossary_terms}

# 客户原始事实 (atomic_facts, 注: regex 抽取质量参差, 仅供参考, 优先看原文)
{atomic_facts}

# 已有的 verified 属性 (避免重复抽)
{existing_verified}

请抽 30-50 条 candidates, 严格 JSON 格式输出 (不要解释):
{{"candidates": [...]}}
"""


@dataclass(frozen=True)
class ExtractedCandidate:
    term: str
    attribute_name: str
    value_category: str
    value_text: str
    value_normalized: float | None
    value_unit: str
    scope: str
    as_of_date: str | None
    source_evidence: str
    confidence: float


def _format_glossary_terms(db: Any, client_id: str) -> str:
    rows = db.fetchall(
        "SELECT term, category, definition FROM client_glossary WHERE client_id=? ORDER BY term LIMIT 100",
        (client_id,),
    )
    if not rows:
        return "(字典为空)"
    return "\n".join(
        f"- {r['term']} [{r['category'] or 'misc'}] {r['definition'][:60] if r['definition'] else ''}"
        for r in rows
    )


def _format_atomic_facts(db: Any, client_id: str, limit: int = 300) -> str:
    rows = db.fetchall(
        """SELECT subject_text, attribute, value_text, evidence_text
           FROM atomic_facts
           WHERE client_id=? AND status='active'
           ORDER BY confidence DESC, updated_at DESC LIMIT ?""",
        (client_id, limit),
    )
    if not rows:
        return "(无 atomic_facts)"
    lines = []
    for r in rows:
        ev = (r["evidence_text"] or "")[:50]
        lines.append(f"- {r['subject_text']} · {r['attribute']} = {r['value_text']}  (证据: {ev})")
    return "\n".join(lines)


def _format_existing_verified(db: Any, client_id: str) -> str:
    rows = db.fetchall(
        """SELECT cg.term, ga.attribute_name, ga.value_text, ga.scope
           FROM glossary_attributes ga JOIN client_glossary cg ON cg.id=ga.term_id
           WHERE ga.client_id=? AND ga.verification_status='verified'""",
        (client_id,),
    )
    if not rows:
        return "(无)"
    return "\n".join(
        f"- {r['term']}.{r['attribute_name']} = {r['value_text']} [{r['scope']}]"
        for r in rows
    )


def extract_candidates(db: Any, ai: Any, client_id: str) -> dict[str, Any]:
    """一次性给某客户抽 candidate attributes (status=pending), 等待审核."""
    glossary_block = _format_glossary_terms(db, client_id)
    if glossary_block == "(字典为空)":
        return {"ok": False, "reason": "字典为空, 请先抽 glossary terms", "inserted": 0}

    facts_block = _format_atomic_facts(db, client_id)
    existing_block = _format_existing_verified(db, client_id)

    prompt = PROMPT_TEMPLATE.format(
        glossary_terms=glossary_block,
        atomic_facts=facts_block,
        existing_verified=existing_block,
    )

    health = ai.get_health()
    if not health.ready:
        return {"ok": False, "reason": f"ai_not_ready: {health.detail}", "inserted": 0}

    try:
        result = ai._qwen_generate(  # noqa: SLF001
            prompt,
            "你是数据中心质量保障员, 只返回 JSON, 尽量抽 30-50 条 candidate。",
            CANDIDATE_SCHEMA,
            timeout_seconds=600.0,
            max_tokens=16000,
            temperature=0.2,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[glossary-attr-extract] LLM call failed: %s", exc)
        return {"ok": False, "reason": f"LLM failed: {type(exc).__name__}: {str(exc)[:200]}", "inserted": 0}

    candidates_raw = result.get("candidates") or []
    if not isinstance(candidates_raw, list):
        return {"ok": False, "reason": "bad LLM response", "inserted": 0}

    # 建 term → term_id 索引
    term_rows = db.fetchall(
        "SELECT id, term FROM client_glossary WHERE client_id=?", (client_id,)
    )
    term_id_by_name = {r["term"]: r["id"] for r in term_rows}

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    skipped = 0
    for c in candidates_raw:
        if not isinstance(c, dict):
            continue
        term_name = str(c.get("term") or "").strip()
        attr_name = str(c.get("attribute_name") or "").strip()
        value_text = str(c.get("value_text") or "").strip()
        if not (term_name and attr_name and value_text):
            skipped += 1
            continue
        term_id = term_id_by_name.get(term_name)
        if not term_id:
            skipped += 1
            continue
        # 通识术语过滤 — SOP/工作坊/心理咨询 等不进字典
        if is_generic_term(term_name):
            skipped += 1
            continue

        try:
            confidence = float(c.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence < 0.3:
            skipped += 1
            continue

        value_norm_raw = c.get("value_normalized")
        try:
            value_norm = float(value_norm_raw) if value_norm_raw is not None else None
        except (TypeError, ValueError):
            value_norm = None

        attr_id = f"attr_{uuid.uuid4().hex[:10]}"
        try:
            db.execute(
                """INSERT INTO glossary_attributes
                   (id, client_id, term_id, attribute_name, value_category,
                    value_text, value_normalized, value_unit, scope, as_of_date,
                    source_type, source_evidence, confidence,
                    verification_status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ai_inferred', ?, ?, 'pending', ?, ?)""",
                (
                    attr_id, client_id, term_id, attr_name,
                    str(c.get("value_category") or "text"),
                    value_text, value_norm,
                    str(c.get("value_unit") or ""),
                    str(c.get("scope") or ""),
                    str(c.get("as_of_date") or "") or None,
                    str(c.get("source_evidence") or "")[:300],
                    confidence,
                    now, now,
                ),
            )
            inserted += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("[glossary-attr-extract] insert failed: %s", exc)
            skipped += 1

    return {
        "ok": True,
        "inserted": inserted,
        "skipped": skipped,
        "total_candidates": len(candidates_raw),
    }
