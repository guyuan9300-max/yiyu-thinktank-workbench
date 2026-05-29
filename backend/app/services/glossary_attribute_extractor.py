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
        # 例外: 长度 ≤3 但含机构名特征 (例 "A组织" 不抽)
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

# 🎯 抽取目标
请尽可能抽出 **30-50 条 candidate**, 覆盖各类业务关键事实。规则:

# ⭐ 字段命名: 严格按基金会标准 schema (覆盖率 70%+ 的字段必须用 schema 名)
下面是一份"基金会摸底表标准 schema" — 摸底表/民政部门/年报/审计报告里都用这套字段名。

如果你抽出的属性能对应到 schema 里某个字段, **attribute_name 必须严格用 schema 标准名**, 不允许变体:
  · ❌ 错: "注册成立时间" → ✅ 对: "成立时间"
  · ❌ 错: "机构性质" / "公募非公募" → ✅ 对: "基金会类型"
  · ❌ 错: "组织机构代码" / "信用代码" → ✅ 对: "统一社会信用代码"
  · ❌ 错: "法人" / "法人代表" / "理事长" (作为基金会法人时) → ✅ 对: "法定代表人"
  · ❌ 错: "注册资金" / "注册资本" → ✅ 对: "原始基金数额"
  · ❌ 错: "注册地址" → ✅ 对: "登记住所"
  · ❌ 错: "总部位置" / "办公地址" → ✅ 对: "实际办公地址"
  · ❌ 错: "项目预算" → ✅ 对: "年度投入（万元）"
  · ❌ 错: "服务对象" (作为项目对象时) → ✅ 对: "服务对象与规模"
  · ❌ 错: "年度筹款" / "募捐总额" → ✅ 对: "年度募捐总额"
  · ❌ 错: "AAA 级" / "5A 级" (作为字段名时) → ✅ 对: "评估等级", value="AAA 级"等
  · ❌ 错: "核心业务" / "核心服务" → ✅ 对: "主要业务范围" 或 "核心服务领域1/2/3"

## 标准字段清单 (节选, 必须按这套命名)
{schema_summary}

## 命名规则
1. 如果你抽到的事实能放进上面任何一个标准字段, **attribute_name 必须用左侧标准名 (不是 aliases 里的同义词)**.
2. 如果是客户专属信息 (项目内部时间线/项目角色/客户独有方法) 不在 schema 里, attribute_name 可以自由命名 — 但要简短可读 (15 字内).
3. **一个 term 同一个 schema 字段只抽一次** (不要"成立时间"和"注册成立时间"都抽两条).

# 其他规则

1. **只抽字典中已存在 term 的属性** — 字典里没有的 term, 即使资料里有也不抽。
2. value_category 取值: amount/date/count/location/person/rating/text.
3. **同一字段不同 scope 必须分别抽多条** (例: 覆盖-机构当前 vs 覆盖-项目累计)。
4. **同一字段多源冲突时, 全部抽出**, 让人选哪个为权威 (不要预选)。
5. **value_text 必须完整、明确** — 不是句子残尾, 不是问句, 不是带"等"省略。
6. as_of_date 从原文提取 (YYYY-MM-DD), 没有就 null。
7. source_evidence 简短引用证据 (含文档名)。
8. confidence: 资料明确=0.9-1.0, 推断=0.5-0.7, 不确定不要抽 (< 0.5)。
9. **❌ 严禁抽通用术语**: SOP / 工作坊 / 心理咨询 / 培训 / 项目管理 / 流程 / 制度 /
   标准 / 评估 / 方案 / 体系 / 课程 / 计划 / 报告 / 系统 等行业通用概念, 不该作为 term 抽。
   只抽**客户独有**的: 机构名 / 项目名 / 客户专属方法 / 客户专属人员 的属性。
10. **❌ 严禁抽通用定义**: 百度百科级定义不抽, 只抽该客户的独特实践。

# 字典已有 term (只能抽这些)
{glossary_terms}

# 互联网抓回的网页正文 (最高优先级 — 来自百度百科/官网/信息公开/民政公示)
{internet_chunks}

# 客户原始事实 (atomic_facts, 注: regex 抽取质量参差, 仅供参考)
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


def _format_internet_chunks(db: Any, client_id: str, *, max_chunks: int = 25, max_chars_per_chunk: int = 800) -> str:
    """从爬虫抓回的 v2_chunks (互联网网页 markdown) 抽 chunks 喂 LLM.

    这是 Stage 3 从"atomic_facts 中间层"升级到"直接读网页正文"的关键:
      - atomic_facts 是 regex 抽出, 大量"成立时间/法定代表人/注册资金"自然语言陈述抽不出
      - v2_chunks 是网页 markdown 原文 (例: 百度百科 / 官网信息公开页), LLM 可以直接读
      - 优先 internet_enrichment 来源的 chunks (新数据, 优先级最高)
    """
    rows = db.fetchall(
        """SELECT d.file_name, substr(c.content, 1, ?) AS snippet
           FROM v2_chunks c JOIN v2_documents d ON d.id = c.v2_document_id
           WHERE d.client_id = ? AND d.content_domain = 'internet_enrichment'
             AND length(c.content) >= 100
           ORDER BY length(c.content) DESC
           LIMIT ?""",
        (max_chars_per_chunk, client_id, max_chunks),
    )
    if not rows:
        return "(无互联网抓回的 chunks)"
    parts = []
    for r in rows:
        title = (r["file_name"] or "")[:40]
        snippet = (r["snippet"] or "").strip()
        if snippet:
            parts.append(f"### {title}\n{snippet}")
    return "\n\n".join(parts) if parts else "(无)"


_STANDARD_SCHEMA_CACHE: list[dict] | None = None


def _load_standard_schema() -> list[dict]:
    """读 foundation_standard_schema.json (摸底表 226 字段). 单进程内 cache."""
    global _STANDARD_SCHEMA_CACHE
    if _STANDARD_SCHEMA_CACHE is not None:
        return _STANDARD_SCHEMA_CACHE
    import json as _json
    from pathlib import Path
    p = Path(__file__).parent / "foundation_standard_schema.json"
    if not p.exists():
        _STANDARD_SCHEMA_CACHE = []
        return []
    try:
        data = _json.loads(p.read_text(encoding="utf-8"))
        _STANDARD_SCHEMA_CACHE = data.get("fields", [])
    except Exception:
        _STANDARD_SCHEMA_CACHE = []
    return _STANDARD_SCHEMA_CACHE


def _build_schema_summary(*, compact: bool) -> str:
    """构造 prompt 里嵌入的 schema 字段清单. compact 模式只列公开可查字段."""
    fields = _load_standard_schema()
    if not fields:
        return "(schema 未加载)"
    # compact: 只列 public_searchable + non-subjective 字段 (大约 60-80 个)
    selected = []
    for f in fields:
        if f.get("is_subjective"):
            continue
        if compact and not f.get("is_public_searchable"):
            continue
        selected.append(f)
    # 按 section 分组渲染
    by_sec: dict[str, list[dict]] = {}
    for f in selected:
        by_sec.setdefault(f.get("section", "其他"), []).append(f)
    lines: list[str] = []
    for sec, group in by_sec.items():
        if sec:
            lines.append(f"  【{sec}】")
        for f in group:
            aliases = "/".join(f.get("aliases", [])[:4]) if f.get("aliases") else ""
            lines.append(f"    · {f['field_name']:<24} [{f.get('value_type','text'):<16}]"
                         + (f"  别名: {aliases}" if aliases and aliases != f["field_name"] else ""))
    return "\n".join(lines)


def extract_candidates(
    db: Any,
    ai: Any,
    client_id: str,
    *,
    compact: bool = False,
    timeout_seconds: float = 600.0,
    max_tokens: int = 16000,
) -> dict[str, Any]:
    """一次性给某客户抽 candidate attributes (status=pending), 等待审核.

    compact=True: 减小 prompt + 加快超时, 用于内嵌在爬虫异步链路里 (Stage 3 紧凑模式).
    """
    glossary_block = _format_glossary_terms(db, client_id)
    if glossary_block == "(字典为空)":
        return {"ok": False, "reason": "字典为空, 请先抽 glossary terms", "inserted": 0}

    facts_limit = 80 if compact else 300
    facts_block = _format_atomic_facts(db, client_id, limit=facts_limit)
    existing_block = _format_existing_verified(db, client_id)
    # 互联网网页 chunks 是基础登记字段的金矿 — compact 模式取少而精, 完整模式取更多
    if compact:
        chunks_block = _format_internet_chunks(db, client_id, max_chunks=12, max_chars_per_chunk=600)
    else:
        chunks_block = _format_internet_chunks(db, client_id, max_chunks=25, max_chars_per_chunk=800)
    # K 任务: 基金会标准 schema 注入 prompt, 让 LLM 用标准 attribute_name
    schema_summary = _build_schema_summary(compact=compact)

    prompt = PROMPT_TEMPLATE.format(
        schema_summary=schema_summary,
        glossary_terms=glossary_block,
        internet_chunks=chunks_block,
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
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
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

    # Task L · 抽完立即跑自动 verify 规则, 让确定性 pending 不进人审队列
    auto_verify_stats: dict[str, Any] = {}
    try:
        from .auto_verify_rules import auto_verify_qualifying_attributes
        auto_verify_stats = auto_verify_qualifying_attributes(db, client_id)
        try:
            db.conn.commit()
        except Exception:  # noqa: BLE001
            pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("[glossary-attr-extract] auto-verify failed: %s", exc)

    return {
        "ok": True,
        "inserted": inserted,
        "skipped": skipped,
        "total_candidates": len(candidates_raw),
        "auto_verified": auto_verify_stats.get("auto_verified", 0),
        "auto_verify_stats": auto_verify_stats,
    }
