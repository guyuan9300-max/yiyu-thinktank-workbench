"""时效情报卡片 LLM 增强（P8）。

定位：取代旧的「关键词分类 + mock fallback」泥潭。
  - 每条 hit 用 LLM 做语义判断而不是字符串匹配
  - 输出客户视角的"为什么和你有关"实质分析
  - 失败时**丢弃这条 hit，不再用 mock 模板伪造**

性能：每条 LLM 调用 ~5-10s。所以**只对高优先级 hit 跑**（hit 排序后取 top N）。
其他 hit 走快速降级：保留 snippet 原文 + 标记 needs_enrichment=true，前端可显示"待 AI 复核"。
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# 数据结构
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class EnrichedCard:
    """LLM 加工后的时效情报卡片。"""
    intelligence_type: str       # 语义类别（funding/industry/policy/cooperation/...）
    relevance_reason: str        # 为什么和这个客户有关（必须引用客户具体信号）
    impact: str                  # 对客户的潜在影响（正/负/中性）
    suggested_action: str        # 动作动词 + 具体对象
    timeliness_label: str        # 'urgent' / 'window' / 'reference'
    confidence: float            # 0-1
    discard: bool = False        # LLM 判断这条与客户无关 → 上层丢弃
    discard_reason: str = ""

    def to_db_fields(self) -> dict[str, Any]:
        return {
            "intelligence_type": self.intelligence_type,
            "relevance_reason": self.relevance_reason,
            "impact": self.impact,
            "suggested_action": self.suggested_action,
            "timeliness_label": self.timeliness_label,
        }


# ──────────────────────────────────────────────────────────────────────────
# 优先级打分（决定哪些 hit 值得跑 LLM）
# ──────────────────────────────────────────────────────────────────────────


_AUTHORITATIVE_SOURCES = {
    # 政府公告/招标
    "gov.cn": 30, "ccgp.gov.cn": 30, "ccgp-": 30, "caigou.gov.cn": 30,
    "mca.gov.cn": 30,            # 民政部
    "cfa-foundation.org.cn": 25,   # 中国基金会
    "foundationcenter.org.cn": 25,
    # 主流媒体
    "people.com.cn": 20, "xinhuanet.com": 20, "cctv.com": 20,
    "thepaper.cn": 18, "caixin.com": 18,
    # 行业媒体
    "ngocn.net": 22, "gongyi.qq.com": 22, "gongyi.sohu.com": 20,
    "ngo.cn": 22,
    # 公众号/自媒体
    "mp.weixin.qq.com": 15,
    "zhihu.com": 12,
    # 招聘/职友
    "lagou.com": 5, "jobui.com": 5, "kanzhun.com": 5,
}


def prioritize_hits(
    hits: list[dict[str, Any]],
    *,
    target_name: str,
    aliases: list[str],
    project_modules: list[str],
    persons: list[str],
    domain: str,
) -> list[dict[str, Any]]:
    """给 hit 列表打优先级分，便于挑 top N 跑 LLM。

    优先级因素：
      1. title/snippet 含 target_name → +50
      2. 含 alias 或 person → +20
      3. 含 project_modules 项目名 → +25
      4. 来源域名权威性（gov/news > 招聘）
      5. 标题长度合理（10-80 字符）+10
    """
    name_tokens = [target_name] + (aliases or [])
    persons_set = set(persons or [])
    projects_set = set(project_modules or [])

    scored: list[tuple[int, dict[str, Any]]] = []
    for hit in hits:
        title = (hit.get("title") or "").strip()
        snippet = (hit.get("snippet") or "").strip()
        url = (hit.get("url") or hit.get("source_url") or "").strip().lower()
        text = f"{title} {snippet}"
        score = 0

        # 1. 主名/别名出现
        if any(tok and tok in text for tok in name_tokens):
            score += 50

        # 2. 关键人物
        if any(p in text for p in persons_set):
            score += 20

        # 3. 项目名
        if any(p in text for p in projects_set):
            score += 25

        # 4. 业务域
        if domain and domain in text:
            score += 10

        # 5. 权威性
        for k, v in _AUTHORITATIVE_SOURCES.items():
            if k in url:
                score += v
                break

        # 6. 标题长度合理
        if 10 <= len(title) <= 80:
            score += 10

        scored.append((score, hit))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [hit for _, hit in scored]


# ──────────────────────────────────────────────────────────────────────────
# LLM Prompt
# ──────────────────────────────────────────────────────────────────────────


ENRICH_SYSTEM_INSTRUCTION = (
    "你是企业情报分析师。给你一条搜索引擎抓到的内容（title + snippet）和目标客户的「数据中心档案」，"
    "你的任务是判断这条内容对客户是否真的有价值，并产出**客户能直接拿去看**的卡片字段。\n\n"
    "硬要求（违反任何一条都算失败）：\n"
    "1. 【先判与否】如果这条内容和客户的业务/项目/人物**完全无关**（比如标题里只是凑巧带了『基金会』三个字），"
    "   直接返回 discard=true 并写明 discard_reason。\n"
    "2. 【relevance_reason 必须具体】不能写『和客户业务有关』这种废话。必须指出："
    "   - 引用客户的具体字段（哪个项目/哪个人/哪个业务域）"
    "   - 说出这条内容里的什么具体点与之关联（具体词、具体段落）"
    "   例如：好 → \"南山区民政局招标的『困境儿童心理关爱』项目，与A组织的『心智魔法学院』在服务对象上完全重合\"\n"
    "   差 → \"涉及客户推进\"\n"
    "3. 【intelligence_type 用语义分类】值必须是：funding（资助/招标/采购机会）/ policy（政策变化）/ "
    "   industry（行业动态/同行）/ cooperation（合作机会）/ governance（治理/合规相关）/ "
    "   media_coverage（关于客户的报道，正面/中性）/ media_risk（关于客户的报道，可能负面）/ "
    "   profile_reference（客户自身基础信息，介绍/简介类，价值最低）。"
    "   不要写『资助机会』等中文名——要写英文 key。\n"
    "4. 【impact 必须给方向】正面/负面/中性，并给出 1 句『如果不行动会怎样』或『如果跟进能拿到什么』。\n"
    "5. 【suggested_action 必须是「动作动词 + 具体对象」】例如：\n"
    "   好 → \"3 天内对接南山区民政局，递交『心智魔法学院』案例材料\"\n"
    "   差 → \"先确认负责人\"\n"
    "6. 【timeliness_label】urgent（< 7 天截止）/ window（窗口期 1-3 月）/ reference（长期参考）。\n"
    "7. 【confidence】0-1，对你判断本条与客户相关性的把握度。\n\n"
    "严格只返回 JSON，禁止 Markdown 围栏。"
)


ENRICH_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["discard", "confidence"],
    "properties": {
        "discard": {"type": "boolean"},
        "discard_reason": {"type": "string"},
        "intelligence_type": {
            "type": "string",
            "enum": [
                "funding", "policy", "industry", "cooperation",
                "governance", "media_coverage", "media_risk", "profile_reference",
            ],
        },
        "relevance_reason": {"type": "string", "minLength": 30, "maxLength": 400},
        "impact": {"type": "string", "minLength": 20, "maxLength": 300},
        "suggested_action": {"type": "string", "minLength": 10, "maxLength": 200},
        "timeliness_label": {
            "type": "string",
            "enum": ["urgent", "window", "reference"],
        },
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
}


def _build_enrich_prompt(
    hit: dict[str, Any],
    *,
    target_name: str,
    aliases: list[str],
    domain: str,
    brand_proposition: str,
    project_modules: list[str],
    glossary_projects: list[str],
    glossary_persons: list[str],
    glossary_methods: list[str],
) -> str:
    title = (hit.get("title") or "").strip()
    snippet = (hit.get("snippet") or "").strip()
    url = (hit.get("url") or hit.get("source_url") or "").strip()
    source = (hit.get("source") or "").strip()

    lines = [
        "============ 客户档案 ============",
        f"主名：{target_name}",
        f"别名：{aliases or '（无）'}",
        f"业务域：{domain or '（未填）'}",
        f"自我定位：{brand_proposition or '（未填）'}",
        f"业务线：{project_modules or '（无）'}",
        f"已知项目：{glossary_projects or '（无）'}",
        f"关键人物：{glossary_persons or '（无）'}",
        f"业务术语：{glossary_methods[:8] if glossary_methods else '（无）'}",
        "",
        "============ 待判定的搜索结果 ============",
        f"标题：{title}",
        f"摘要：{snippet}",
        f"来源：{source} ({url})",
        "",
        "请输出 JSON 卡片字段。",
        "再次强调：discard 优先；relevance_reason 必须引用客户档案里的具体字段；",
        "suggested_action 必须含动词+对象。",
    ]
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────────────────────────────────


def enrich_hit(
    ai_service: object,
    hit: dict[str, Any],
    *,
    target_name: str,
    aliases: list[str],
    domain: str,
    brand_proposition: str,
    project_modules: list[str],
    glossary_projects: list[str],
    glossary_persons: list[str],
    glossary_methods: list[str],
    timeout_seconds: float = 30.0,
) -> EnrichedCard | None:
    """对单 hit 跑一次 LLM enrichment。失败返回 None（上层丢弃这条 hit）。"""
    if ai_service is None:
        return None
    try:
        health = ai_service.get_health()  # type: ignore[attr-defined]
        if not getattr(health, "ready", False):
            return None
    except Exception:  # noqa: BLE001
        return None

    prompt = _build_enrich_prompt(
        hit,
        target_name=target_name,
        aliases=aliases,
        domain=domain,
        brand_proposition=brand_proposition,
        project_modules=project_modules,
        glossary_projects=glossary_projects,
        glossary_persons=glossary_persons,
        glossary_methods=glossary_methods,
    )

    try:
        raw = ai_service._qwen_generate(  # type: ignore[attr-defined]  # noqa: SLF001
            prompt,
            ENRICH_SYSTEM_INSTRUCTION,
            ENRICH_RESPONSE_SCHEMA,
            timeout_seconds=timeout_seconds,
            max_tokens=1200,
            temperature=0.15,
            task_kind="default",
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("[card-enrich] LLM failed for %s: %s", hit.get("url"), exc)
        return None

    if not isinstance(raw, dict):
        try:
            raw = json.loads(str(raw))
        except Exception:  # noqa: BLE001
            return None
    if not isinstance(raw, dict):
        return None

    discard = bool(raw.get("discard"))
    try:
        confidence = float(raw.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    if discard:
        return EnrichedCard(
            intelligence_type="",
            relevance_reason="",
            impact="",
            suggested_action="",
            timeliness_label="",
            confidence=confidence,
            discard=True,
            discard_reason=str(raw.get("discard_reason") or "LLM 判定与客户无关")[:200],
        )

    intelligence_type = str(raw.get("intelligence_type") or "").strip()
    relevance_reason = str(raw.get("relevance_reason") or "").strip()
    impact = str(raw.get("impact") or "").strip()
    suggested_action = str(raw.get("suggested_action") or "").strip()
    timeliness_label = str(raw.get("timeliness_label") or "reference").strip()

    # 反套话校验：如果 LLM 又输出"先确认负责人"等模板，强制 discard
    bad_phrases = (
        "先确认负责人", "整合成可落地动作", "整理出一版", "内部判断",
        "证据沉淀与任务闭环", "推进客户", "补关键材料",
    )
    if any(b in suggested_action or b in relevance_reason or b in impact for b in bad_phrases):
        return EnrichedCard(
            intelligence_type="",
            relevance_reason="",
            impact="",
            suggested_action="",
            timeliness_label="",
            confidence=0.0,
            discard=True,
            discard_reason="LLM 输出包含模板套话，已丢弃避免污染卡片",
        )

    # 长度兜底校验：太短的内容也不要
    if len(relevance_reason) < 20 or len(impact) < 15 or len(suggested_action) < 8:
        return EnrichedCard(
            intelligence_type="",
            relevance_reason="",
            impact="",
            suggested_action="",
            timeliness_label="",
            confidence=0.0,
            discard=True,
            discard_reason="LLM 输出字段过短，无业务价值",
        )

    return EnrichedCard(
        intelligence_type=intelligence_type or "industry",
        relevance_reason=relevance_reason[:400],
        impact=impact[:300],
        suggested_action=suggested_action[:200],
        timeliness_label=timeliness_label if timeliness_label in ("urgent", "window", "reference") else "reference",
        confidence=confidence,
        discard=False,
    )


def enrich_hits_batch(
    ai_service: object,
    hits: list[dict[str, Any]],
    *,
    target_name: str,
    aliases: list[str],
    domain: str,
    brand_proposition: str,
    project_modules: list[str],
    glossary_projects: list[str],
    glossary_persons: list[str],
    glossary_methods: list[str],
    max_invocations: int = 12,
    min_confidence: float = 0.45,
    timeout_seconds: float = 30.0,
) -> tuple[list[tuple[dict[str, Any], EnrichedCard]], dict[str, int]]:
    """批量增强 — 按优先级排序后跑前 N 个。

    Returns:
      (enriched_results, stats)
      enriched_results: 每条 = (原 hit, EnrichedCard)，仅含 confidence>=阈值 且 discard=False 的
      stats: {invoked, discarded, low_confidence, accepted}
    """
    stats = {"invoked": 0, "discarded": 0, "low_confidence": 0, "accepted": 0}

    ordered = prioritize_hits(
        hits,
        target_name=target_name,
        aliases=aliases,
        project_modules=project_modules,
        persons=glossary_persons,
        domain=domain,
    )

    results: list[tuple[dict[str, Any], EnrichedCard]] = []
    for hit in ordered[:max_invocations]:
        card = enrich_hit(
            ai_service, hit,
            target_name=target_name, aliases=aliases, domain=domain,
            brand_proposition=brand_proposition,
            project_modules=project_modules,
            glossary_projects=glossary_projects,
            glossary_persons=glossary_persons,
            glossary_methods=glossary_methods,
            timeout_seconds=timeout_seconds,
        )
        stats["invoked"] += 1
        if card is None:
            continue
        if card.discard:
            stats["discarded"] += 1
            continue
        if card.confidence < min_confidence:
            stats["low_confidence"] += 1
            continue
        stats["accepted"] += 1
        results.append((hit, card))

    return results, stats
