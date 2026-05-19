"""澄清问题预搜索中间层 (clarification pre-search).

== 解决的真问题 ==

narrative_generator LLM 在写 6 维度叙事时, 会把 fact 不足的问题放到 openClarifications,
让用户去回答. 但实测里 LLM 经常把"公共概念问题"也塞进去 — 例如:
  · "什么是 5A 评估?"       — 这是民政部规则, 爬虫查得到, 不该问用户
  · "积极心理学的核心理论?" — 这是学术通识, 百科查得到
  · "互联网募捐备案规则?"   — 这是法规, 政府网站查得到

这些问题让用户回答 = 增加用户负担 + 浪费用户时间.

== 这一层做什么 ==

对每条 openClarifications:
  1. **判定**: 是"公共概念问题" 还是 "客户专属问题"
  2. **公共概念** → 跑 search_public_web 找答案 → 直接从 openClarifications 删除 (不打扰用户)
  3. **客户专属 + 搜得到** → LLM 抽 (term, attribute, value) → 进字典 pending (用户审一次, 不再答)
  4. **客户专属 + 搜不到** → 保留在 openClarifications (真正只有用户能答的)

== 机制化原则 (用户原话) ==
  · 用机制决定, 不靠 LLM 自我判断 (LLM 自检不够可靠)
  · 真的去搜一遍, 用搜索结果判定
  · 公共概念走爬虫→字典 verified, 客户专属走澄清
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from app.services.public_search import search_public_web

logger = logging.getLogger(__name__)


# 公共概念问题的语言学特征 (用作启发式预筛, 避免对每条问题都跑 LLM)
_PUBLIC_QUESTION_PATTERNS = (
    r"什么\s*是\s*",  # "什么是 X"
    r"什么\s*叫\s*",
    r"如何\s*定义",
    r"X\s*的\s*定义",
    r"是\s*什么\s*?",
    r"的\s*核心\s*理论",
    r"的\s*基本\s*概念",
    r"的\s*基本\s*要求",
    r"的\s*基本\s*规则",
    r"的\s*主要\s*内容",
    r"规定\s*什么",
    r"标准\s*是\s*",
    r"法\s*第.{0,3}条",
    r"条例\s*规定",
    r"办法\s*规定",
    r"《[^》]+》\s*的",
    r"行业\s*标准",
    r"通行\s*做法",
)
_PUBLIC_QUESTION_REGEX = re.compile("|".join(_PUBLIC_QUESTION_PATTERNS))

# 公共概念关键词 (问题含这些词高概率是公共概念)
_PUBLIC_CONCEPT_KEYWORDS = (
    "评估等级", "AAA", "5A", "4A",  # 民政部评估
    "公开募捐", "募捐备案", "互联网募捐",
    "慈善法", "基金会管理条例", "慈善组织信息公开",
    "公益事业捐赠法", "税前扣除",
    "积极心理学", "社会情感学习", "SEL",
    "心理学理论", "认知行为", "动力学",
    "项目管理体系", "PMI",
    "审计准则", "会计准则",
    "理事会", "监事会",  # 治理机构标准定义
)


def _looks_like_public_question(question: str, client_name: str) -> bool:
    """启发式: 这个问题像不像"公共概念"问题.

    返回 True 不是最终判定, 只是省搜索成本的预筛 (避免每条都跑 search):
      - 含"什么是 X/规定什么/标准是" 等通识句式
      - 含公共概念关键词
      - 不含客户名 (公共概念问题通常跟具体客户无关)
    """
    q = (question or "").strip()
    if not q:
        return False
    cname = (client_name or "").strip()

    # 1. 客户名在问题里 → 强信号: 是客户专属问题, 不公共
    if cname and cname in q:
        return False

    # 2. 含公共问题句式
    if _PUBLIC_QUESTION_REGEX.search(q):
        return True

    # 3. 含公共概念关键词
    if any(kw in q for kw in _PUBLIC_CONCEPT_KEYWORDS):
        return True

    return False


def _search_has_authoritative_answer(question: str, client_name: str) -> tuple[bool, list[dict]]:
    """对一条问题跑 search_public_web, 判断是否有权威源能答.

    权威源 = baike.sogou.com / baike.baidu.com / *.gov.cn / 主流公益基金会域名等.
    返回 (是否搜到, 前 3 个结果详情).
    """
    # 控制成本: 单条问题只搜 1 次, max_results=5
    try:
        results = search_public_web(question, max_results=5, timeout_seconds=10.0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[clarification-pre-search] search '%s' failed: %s", question[:40], exc)
        return False, []

    if not results:
        return False, []

    # 数权威源命中数
    authoritative = 0
    for r in results:
        u = (r.url or "").lower()
        if any(d in u for d in ("baike.sogou.com", "baike.baidu.com", ".gov.cn", "naradafoundation.org", "bnu1.org")):
            authoritative += 1

    # 至少 2 个权威源 → 判定为可答
    has_answer = authoritative >= 2
    digest = [
        {"title": (r.title or "")[:60], "url": (r.url or "")[:120], "snippet": (r.snippet or "")[:160]}
        for r in results[:3]
    ]
    return has_answer, digest


_CLIENT_FIELDS_LIKELY_IN_DICT = (
    "成立时间", "成立日期", "注册时间", "注册资金", "原始基金",
    "法定代表人", "登记机关", "登记管理机关", "评估等级", "信用代码",
    "理事长", "秘书长", "总部位置", "注册地址", "办公地址",
    "募捐资格", "公募", "非公募", "税前扣除资格", "慈善组织认定",
    "项目数量", "覆盖范围", "服务对象", "受益人数",
    "业务范围", "核心业务",
)


def _fuzzy_match_client_name(question: str, client_name: str) -> bool:
    """模糊匹配客户名: '日慈' 也算 '日慈基金会' 命中."""
    if not client_name or not question:
        return False
    if client_name in question:
        return True
    # 去掉常见后缀 (基金会/中心/学会/公益服务中心/公益)
    short = client_name
    for suffix in ("公益基金会", "基金会", "公益服务中心", "服务中心", "公益", "中心", "学会"):
        if short.endswith(suffix):
            short = short[: -len(suffix)]
            break
    return bool(short and len(short) >= 2 and short in question)


def _check_question_already_answered_in_glossary(
    db: Any,
    client_id: str,
    question: str,
    client_name: str,
) -> tuple[bool, dict | None]:
    """检查澄清问题在字典里是不是已经有 verified/pending 答案了.

    设计: 大部分客户专属问题 (成立时间/法人/评估等级...) 在爬虫+Stage 3 链路跑完后
    已经进了 glossary_attributes (verified 或 pending). LLM 多此一问时, 直接拦截.

    返回 (is_already_answered, glossary_row_or_None)
    """
    if not _fuzzy_match_client_name(question, client_name):
        return False, None
    # 找问题里命中的字段关键词
    hit_fields = [f for f in _CLIENT_FIELDS_LIKELY_IN_DICT if f in question]
    if not hit_fields:
        return False, None
    # 用 hit_fields 在 glossary_attributes 查
    for field in hit_fields:
        for r in db.fetchall(
            """SELECT ga.value_text, ga.attribute_name, ga.verification_status, cg.term
               FROM glossary_attributes ga JOIN client_glossary cg ON cg.id = ga.term_id
               WHERE ga.client_id = ?
                 AND ga.attribute_name LIKE ?
               ORDER BY CASE ga.verification_status WHEN 'verified' THEN 0 ELSE 1 END,
                        ga.confidence DESC LIMIT 1""",
            (client_id, f"%{field}%"),
        ):
            return True, dict(r) if hasattr(r, "keys") else {"value_text": r[0], "attribute_name": r[1], "verification_status": r[2], "term": r[3]}
    return False, None


def _extract_glossary_candidate_from_search(
    ai: Any,
    question: str,
    client_name: str,
    search_results: list[dict],
) -> dict[str, Any] | None:
    """对客户专属问题, 用 LLM 把搜索结果抽成 (term, attribute, value) 三元组.

    返回 None 表示抽不出有效答案.
    """
    if not ai or not hasattr(ai, "_qwen_generate"):
        return None
    if not search_results:
        return None

    # 拼出"问题 + 候选答案上下文"喂 LLM
    context_lines = []
    for i, r in enumerate(search_results, 1):
        context_lines.append(f"[来源 {i}] {r.get('title','')}")
        if r.get("snippet"):
            context_lines.append(f"  内容: {r['snippet']}")
        if r.get("url"):
            context_lines.append(f"  URL: {r['url']}")
    context = "\n".join(context_lines)

    prompt = f"""客户名: {client_name}
澄清问题: {question}

搜索结果:
{context}

任务: 如果搜索结果**直接回答了**这个问题, 提取出 (term, attribute, value) 三元组.
不要编造, 不要推断, 只复述搜索结果里的事实.

严格 JSON 格式:
{{
  "found": true,
  "term": "广东省日慈公益基金会",
  "attribute_name": "成立时间",
  "value_text": "2013年12月31日",
  "source_url": "https://baike.sogou.com/..."
}}

如果搜索结果**没有直接回答**这个问题, 返回:
{{ "found": false, "reason": "搜索结果未直接回答此问题" }}

只输出 JSON, 不要其他文字."""
    try:
        result = ai._qwen_generate(  # noqa: SLF001
            prompt,
            "你是数据中心质量员, 只从搜索结果里提取直接事实, 不推断不编造. 只输出 JSON.",
            None,
            timeout_seconds=60.0,
            max_tokens=600,
            temperature=0.1,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[clarification-pre-search] LLM extract failed: %s", exc)
        return None
    if isinstance(result, dict):
        if result.get("found"):
            return result
        return None
    # 兜底: 字符串 JSON
    if isinstance(result, str):
        try:
            obj = json.loads(result)
            if isinstance(obj, dict) and obj.get("found"):
                return obj
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def _persist_resolved_clarification_to_glossary(
    db: Any,
    client_id: str,
    candidate: dict[str, Any],
    source_question: str,
) -> bool:
    """把搜索抽出的 (term, attribute, value) 落库到 glossary_attributes pending.

    标记 source_type='auto_resolved_clarification', 让用户在字典审核时知道
    这是机器自动从公开搜索答出来的, 审一下即可 verified.
    """
    term = str(candidate.get("term") or "").strip()
    attr = str(candidate.get("attribute_name") or "").strip()
    value = str(candidate.get("value_text") or "").strip()
    source_url = str(candidate.get("source_url") or "").strip()
    if not (term and attr and value):
        return False

    # 找/建 term 行
    term_row = db.fetchone(
        "SELECT id FROM client_glossary WHERE client_id = ? AND term = ?",
        (client_id, term),
    )
    if not term_row:
        # 自动建 term (因为 LLM 选定的 term 不一定在字典里)
        term_id = f"term_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        try:
            db.execute(
                """INSERT INTO client_glossary (id, client_id, term, normalized_term, definition,
                                                aliases_json, category, created_at, updated_at)
                   VALUES (?, ?, ?, ?, '', '[]', '机构', ?, ?)""",
                (term_id, client_id, term, term, now, now),
            )
        except Exception:  # noqa: BLE001
            return False
    else:
        term_id = str(term_row["id"])

    # 落 attribute
    attr_id = f"attr_{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc).isoformat()
    try:
        db.execute(
            """INSERT INTO glossary_attributes
               (id, client_id, term_id, attribute_name, value_category,
                value_text, value_normalized, value_unit, scope, as_of_date,
                source_type, source_evidence, confidence,
                verification_status, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'text', ?, NULL, '', '', NULL,
                       'auto_resolved_clarification', ?, 0.85,
                       'pending', ?, ?)""",
            (
                attr_id, client_id, term_id, attr, value,
                f"自动搜索解决澄清问题: 「{source_question[:80]}」  来源: {source_url}",
                now, now,
            ),
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("[clarification-pre-search] persist failed: %s", exc)
        return False


def pre_search_clarifications(
    ai: Any,
    db: Any,
    client_id: str,
    client_name: str,
    dims: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """对每个维度的 openClarifications 跑预搜索, 拦截公共概念 + 已可答的客户专属问题.

    会修改 dims 里每个 dimension 的 openClarifications 字段 (filter in-place).
    返回统计:
      {"total":N, "public_dropped":X, "auto_resolved":Y, "kept":Z, "stale":Z2}
    """
    stats = {
        "total": 0,
        "public_dropped": 0,         # 公共概念, 搜索能答 → 直接删除
        "public_dropped_heuristic": 0,  # 公共概念, 启发式判定后直接删 (不真搜, 省成本)
        "auto_resolved": 0,          # 客户专属, 搜到答案 → 进字典 pending
        "kept": 0,                   # 客户专属, 搜不到 → 保留在 openClarifications
        "details": [],
    }

    for dim_name, dim_data in dims.items():
        if not isinstance(dim_data, dict):
            continue
        clarifications = dim_data.get("openClarifications") or []
        if not clarifications:
            continue

        filtered: list[str] = []
        for q in clarifications:
            q_text = str(q or "").strip()
            if not q_text:
                continue
            stats["total"] += 1

            # === 路径 1: 启发式判定为公共概念 (省成本, 不搜索) ===
            if _looks_like_public_question(q_text, client_name):
                # 即便启发式判定为公共概念, 也跑一次 search 做二次验证 (省心)
                has_ans, _ = _search_has_authoritative_answer(q_text, client_name)
                if has_ans:
                    stats["public_dropped"] += 1
                    stats["details"].append({
                        "dim": dim_name,
                        "question": q_text,
                        "action": "public_dropped",
                        "reason": "启发式+search 双重确认是公共概念",
                    })
                    continue
                # 启发式说是公共概念但搜不到 → 边界情况, 也删掉 (LLM 想问通识但通识没现成答案 ≈ 八成是问错了)
                stats["public_dropped_heuristic"] += 1
                stats["details"].append({
                    "dim": dim_name,
                    "question": q_text,
                    "action": "public_dropped_heuristic",
                    "reason": "启发式判定公共概念, 搜索无明确答案, 仍判为公共并删除",
                })
                continue

            # === 路径 2: 客户专属 + 字典里已有答案 (LLM 多此一问 → 拦截不打扰用户) ===
            # 实测发现: 爬虫+Stage 3 跑完后, 大部分基础登记字段都在字典 pending/verified 里,
            # LLM 写 narrative 时没看到字典就重复问. 直接查字典拦截这种重复问题.
            already_answered, ga_row = _check_question_already_answered_in_glossary(
                db, client_id, q_text, client_name,
            )
            if already_answered:
                stats["auto_resolved"] += 1
                stats["details"].append({
                    "dim": dim_name,
                    "question": q_text,
                    "action": "auto_resolved",
                    "reason": "字典里已有答案",
                    "candidate": {
                        "term": ga_row.get("term","") if ga_row else "",
                        "attribute_name": ga_row.get("attribute_name","") if ga_row else "",
                        "value_text": str(ga_row.get("value_text","") if ga_row else "")[:60],
                        "verification_status": ga_row.get("verification_status","") if ga_row else "",
                    },
                })
                continue

            # === 路径 3: 真正客户专属 + 字典没有 + 搜索也搜不到 → 保留为澄清 ===
            filtered.append(q_text)
            stats["kept"] += 1

        dim_data["openClarifications"] = filtered

    return stats
