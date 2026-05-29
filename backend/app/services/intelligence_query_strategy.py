"""智能 Query Strategy Engine（P7-1）。

定位：资讯情报站的「搜索大脑」。
  - 从数据中心 8-10 张表收集客户信号（人物 / 项目 / 机构 / 业务术语等）
  - LLM 基于信号生成 50-150 条 query 矩阵，每条带 intent 标签
  - 同一引擎服务**舆情**和**时效**两个下游 — 只是 intent 不同
  - 硬编码模板作为降级兜底（LLM 失败时回退）

设计原则（用户拍板）：
  - 旧硬编码搜索 = 降级兜底，不删
  - 新智能流程 = 主路径
  - 数据中心信号没有 → fallback 到硬编码，并在返回里告知"signals_sparse"
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from app.db import Database

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# 数据中心信号收集
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class DataCenterSignals:
    """从数据中心吸取的客户全景信号，作为 query strategy 的输入。"""
    primary_name: str
    aliases: list[str] = field(default_factory=list)
    domain: str = ""
    brand_proposition: str = ""

    # 业务架构
    project_modules: list[str] = field(default_factory=list)

    # client_glossary 分类抽取
    glossary_persons: list[str] = field(default_factory=list)   # 人物
    glossary_projects: list[str] = field(default_factory=list)  # 项目
    glossary_orgs: list[str] = field(default_factory=list)      # 机构（合作方）
    glossary_methods: list[str] = field(default_factory=list)   # 业务术语/方法论

    # 已经聚出的舆情主题（如果有）
    known_themes: list[str] = field(default_factory=list)

    # 元信息
    has_uploaded_docs: bool = False
    sentiment_item_count: int = 0


# 过滤掉明显内部 / 噪声的 glossary 项
_INTERNAL_PERSON_HINTS = ("益语", "本机用户", "对接人员", "技术相关")
_NOISE_PROJECT_HINTS = ("联调", "已完成", "内部系统")


def collect_signals(db: Database, *, client_id: str) -> DataCenterSignals:
    """从数据中心收集一个客户的全部可用信号。"""
    row = db.fetchone(
        "SELECT name, alias, domain, brand_proposition FROM clients WHERE id = ?",
        (client_id,),
    )
    if not row:
        return DataCenterSignals(primary_name="")

    name = str(row["name"] or "").strip()
    alias = str(row["alias"] or "").strip()
    domain = str(row["domain"] or "").strip()
    brand_proposition = str(row["brand_proposition"] or "").strip()

    signals = DataCenterSignals(
        primary_name=name,
        aliases=[alias] if alias and alias != name and len(alias) >= 2 else [],
        domain=domain,
        brand_proposition=brand_proposition,
    )

    # 业务线
    try:
        pm_rows = db.fetchall(
            "SELECT name FROM project_modules WHERE client_id = ? ORDER BY updated_at DESC LIMIT 10",
            (client_id,),
        )
        signals.project_modules = [
            str(r["name"]).strip() for r in pm_rows
            if r["name"] and len(str(r["name"]).strip()) >= 2
        ]
    except Exception:  # noqa: BLE001
        pass

    # client_glossary 按 category 拆类
    try:
        glo_rows = db.fetchall(
            "SELECT term, category, definition FROM client_glossary WHERE client_id = ? LIMIT 200",
            (client_id,),
        )
        for r in glo_rows:
            term = str(r["term"] or "").strip()
            category = str(r["category"] or "").strip()
            definition = str(r["definition"] or "").strip()
            if not term or len(term) < 2:
                continue

            # 内部人员过滤：term 或 definition 含 "益语" / "本机" / "对接人员" 都跳过
            combined = f"{term} {definition}"
            is_internal = any(h in combined for h in _INTERNAL_PERSON_HINTS)

            if category == "人物":
                if is_internal:
                    continue
                # 排除主公司 + 笼统的"X老师"（无具体姓名）
                if term in (name, "高老师", "王老师", "张老师", "于老师", "顾老师"):
                    continue
                signals.glossary_persons.append(term)
            elif category == "项目":
                if any(h in term for h in _NOISE_PROJECT_HINTS):
                    continue
                if is_internal:
                    continue  # 益语方内部项目（如"战略陪伴项目"）不搜
                if term in signals.project_modules:
                    continue  # 已在 project_modules 里
                signals.glossary_projects.append(term)
            elif category == "机构":
                if term == name:
                    continue
                signals.glossary_orgs.append(term)
            elif category == "业务术语":
                if len(term) < 3:
                    continue  # 太短的术语不适合做搜索词
                signals.glossary_methods.append(term)
    except Exception:  # noqa: BLE001
        pass

    # 已知舆情主题（前几轮聚类的产物，可作为下次搜索的种子）
    try:
        theme_rows = db.fetchall(
            """
            SELECT theme_label FROM intelligence_sentiment_themes
            WHERE scope_type = 'client' AND scope_id = ?
            ORDER BY item_count DESC LIMIT 8
            """,
            (client_id,),
        )
        signals.known_themes = [
            str(r["theme_label"]).strip() for r in theme_rows if r["theme_label"]
        ]
    except Exception:  # noqa: BLE001
        pass

    # 文档存量（影响策略：有文档可加 LLM 二轮抽词）
    try:
        doc_row = db.fetchone(
            "SELECT COUNT(*) AS c FROM documents WHERE client_id = ?", (client_id,),
        )
        signals.has_uploaded_docs = bool(doc_row and int(doc_row["c"] or 0) > 0)
    except Exception:  # noqa: BLE001
        pass

    # 已抓的 sentiment item 数
    try:
        cnt_row = db.fetchone(
            """
            SELECT COUNT(*) AS c FROM intelligence_items
            WHERE client_id = ? AND content_kind = 'public_opinion'
              AND COALESCE(user_status,'active') NOT IN ('dismissed','misclassified')
            """,
            (client_id,),
        )
        signals.sentiment_item_count = int(cnt_row["c"]) if cnt_row else 0
    except Exception:  # noqa: BLE001
        pass

    return signals


def signals_health_report(signals: DataCenterSignals) -> dict[str, Any]:
    """生成"数据中心健康度"报告，用户可见的「我们了解这家客户多少」。"""
    score = 0
    notes: list[str] = []
    suggestions: list[str] = []

    if signals.primary_name:
        score += 10
    if signals.aliases:
        score += 5
    else:
        suggestions.append("补 alias（别名/简称）— 例：A组织 → A组织")
    if signals.domain:
        score += 5
    if signals.brand_proposition:
        score += 15
    else:
        suggestions.append("填自我品牌定位（3-5 个关键词）— 用于定位差异图")

    if signals.project_modules:
        score += 10
    if signals.glossary_projects:
        score += 10
    if not signals.project_modules and not signals.glossary_projects:
        suggestions.append("录入关键项目名 — 公众讨论项目比讨论机构本身更多")

    if signals.glossary_persons:
        score += min(20, len(signals.glossary_persons) * 3)
    else:
        suggestions.append("录入关键人物（创始人/秘书长/首席研究员）— 人物维度搜索量级最高")

    if signals.glossary_orgs:
        score += 5
    if signals.glossary_methods:
        score += min(10, len(signals.glossary_methods) * 2)

    if signals.has_uploaded_docs:
        score += 5
    if signals.sentiment_item_count > 0:
        score += 5

    score = min(100, score)

    # 估算 query 矩阵的潜在量级
    if signals.glossary_persons or signals.glossary_projects:
        potential_queries = (
            5  # base
            + len(signals.glossary_persons) * 3
            + len(signals.glossary_projects) * 3
            + len(signals.glossary_orgs) * 2
            + len(signals.glossary_methods) * 2
            + len(signals.project_modules) * 2
        )
    else:
        potential_queries = 14  # fallback baseline

    notes.append(f"基于现有信号，预计可生成 {potential_queries} 条 query")
    if score < 40:
        notes.append("⚠️ 数据中心信号偏少，搜索效果会受影响。建议先补充关键人物/项目。")

    return {
        "score": score,
        "ready": score >= 40,
        "notes": notes,
        "suggestions": suggestions,
        "potentialQueries": potential_queries,
    }


# ──────────────────────────────────────────────────────────────────────────
# Query 计划 dataclass
# ──────────────────────────────────────────────────────────────────────────


QueryIntent = Literal[
    "evaluation",      # 评价/口碑
    "complaint",       # 投诉/质疑
    "image",           # 品牌印象/标签
    "person",          # 人物相关
    "project",         # 项目相关
    "industry",        # 行业语境
    "internal",        # 内部（招聘/离职/文化）
    "cooperation",     # 利益相关/合作方
    "governance",      # 治理/合规
    "policy",          # 政策窗口（时效）
    "funding",         # 资助申报（时效）
    "regulatory",      # 监管变化（时效）
    "platform_limited" # site: 限定
]


@dataclass
class QueryPlan:
    query_text: str
    intent: str
    source_priority: list[str] = field(default_factory=list)  # 该 query 适合哪些信源
    expected_signal: str = ""  # 期望抓到的信号类型描述
    priority: int = 50         # 0-100，决定执行顺序
    mission_key: str = ""      # P9-Mission：该 query 服务于情报站哪个站岗任务

    def to_dict(self) -> dict[str, Any]:
        return {
            "queryText": self.query_text,
            "intent": self.intent,
            "sourcePriority": self.source_priority,
            "expectedSignal": self.expected_signal,
            "priority": self.priority,
            "missionKey": self.mission_key,
        }


# ──────────────────────────────────────────────────────────────────────────
# LLM 生成 query 矩阵
# ──────────────────────────────────────────────────────────────────────────


STRATEGY_SYSTEM_INSTRUCTION = (
    "你是资讯情报站的「搜索策略师」。\n"
    "情报站是一个有自己任务清单的产品——它**自主**决定要监控什么，"
    "数据中心的客户档案只是它用来理解客户的工具，不是它的命令源。\n\n"
    "你会收到：\n"
    "  1. 当前激活的 missions 清单（情报站的 6 个站岗任务中的部分）\n"
    "  2. 客户档案（数据中心已知的人物/项目/术语/定位）\n\n"
    "你的任务：**按 mission 分组**输出 query 矩阵。\n"
    "每个 mission 用客户档案去定向 — 比如「关键人物追踪」这个 mission，"
    "如果客户档案有「张真」这个人，就生成「张真 演讲」「张真 专访」「张真 公开发言」等 query。\n\n"
    "硬要求：\n"
    "1. 每条 query 必须**所属一个明确的 mission**（mission_key 字段必填）。\n"
    "2. 每条 query 必须**引用客户档案里的具体字段**（人物名/项目名/术语），不要泛泛搜机构名。\n"
    "3. 每条 query 短且具体（不超过 20 字）。\n"
    "4. 每个 mission 的 query 数大致符合它的 target_count（不要全堆到一个 mission）。\n"
    "5. 每条 query 给：mission_key / intent / priority(0-100) / source_priority / expected_signal。\n"
    "6. source_priority 取值：search_engine/wechat/zhihu/bilibili/weibo/xiaohongshu/tianyancha/foundation_registry。\n"
    "7. 总量随 mission 数浮动（通常 30-80 条）。\n"
    "只返回 JSON，禁止 Markdown 围栏。"
)


STRATEGY_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["queries"],
    "properties": {
        "queries": {
            "type": "array",
            "minItems": 10,
            "maxItems": 100,
            "items": {
                "type": "object",
                "required": ["query_text", "mission_key", "intent", "priority"],
                "properties": {
                    "query_text": {"type": "string", "maxLength": 40},
                    "mission_key": {"type": "string"},
                    "intent": {"type": "string"},
                    "priority": {"type": "integer", "minimum": 0, "maximum": 100},
                    "source_priority": {"type": "array", "items": {"type": "string"}},
                    "expected_signal": {"type": "string"},
                },
            },
        },
    },
}


def _build_strategy_prompt(
    signals: DataCenterSignals,
    *,
    task_type: str,
    missions: list[Any] | None = None,
) -> str:
    lines: list[str] = []

    # P9-Mission：先说情报站这次要干什么（站岗任务）
    if missions:
        lines.append("============ 情报站当前激活的 STANDING MISSIONS ============")
        lines.append("（每条 query 必须明确所属哪个 mission，mission_key 字段必填）")
        lines.append("")
        for m in missions:
            lines.append(f"[{m.key}] {m.name}（目标 query 数: {m.target_count}）")
            lines.append(f"  做什么：{m.intent}")
            lines.append(f"  什么算高价值：{m.value_criteria}")
            lines.append(f"  基准 priority：{m.priority_base}")
            lines.append("")
        lines.append("============ 客户档案（用来定向每个 mission 的具体关键词） ============")
        lines.append("")
    else:
        lines.append(f"task_type: {task_type}（sentiment=舆情口碑 / timely=时效资讯）")
        lines.append("")

    lines += [
        f"client_primary_name: {signals.primary_name}",
        f"aliases: {signals.aliases}",
        f"domain: {signals.domain or '（未填写）'}",
        f"brand_proposition: {signals.brand_proposition or '（未填写）'}",
        "",
        f"project_modules: {signals.project_modules or '（无）'}",
        f"glossary_persons: {signals.glossary_persons or '（无）'}",
        f"glossary_projects: {signals.glossary_projects or '（无）'}",
        f"glossary_orgs: {signals.glossary_orgs or '（无）'}",
        f"glossary_methods: {signals.glossary_methods or '（无）'}",
        "",
        f"known_public_themes（已聚出的公众主题，可用于深挖）: {signals.known_themes or '（首次抓取）'}",
        f"sentiment_item_count: {signals.sentiment_item_count}",
        "",
        "请输出 query 矩阵。要求量级 30-80 条，覆盖多 intent，引用人物/项目/术语。",
    ]
    return "\n".join(lines)


def _llm_generate_queries(
    ai_service: object,
    signals: DataCenterSignals,
    *,
    task_type: str,
    timeout_seconds: float,
    missions: list[Any] | None = None,
) -> list[QueryPlan]:
    """调 Qwen 生成 query 矩阵。失败返回 []，上层走 fallback。

    Args:
        missions: 当前激活的 mission 列表（MissionSpec），LLM 按 mission 分组生成 query
    """
    if ai_service is None:
        return []
    try:
        health = ai_service.get_health()  # type: ignore[attr-defined]
        if not getattr(health, "ready", False):
            return []
    except Exception:  # noqa: BLE001
        return []

    prompt = _build_strategy_prompt(signals, task_type=task_type, missions=missions)
    try:
        raw = ai_service._qwen_generate(  # type: ignore[attr-defined]  # noqa: SLF001
            prompt,
            STRATEGY_SYSTEM_INSTRUCTION,
            STRATEGY_RESPONSE_SCHEMA,
            timeout_seconds=timeout_seconds,
            max_tokens=4000,
            temperature=0.25,
            task_kind="default",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[query-strategy] LLM failed: %s", exc)
        return []

    if not isinstance(raw, dict):
        try:
            raw = json.loads(str(raw))
        except Exception:  # noqa: BLE001
            return []
    if not isinstance(raw, dict):
        return []

    items = raw.get("queries") or []
    if not isinstance(items, list):
        return []

    # 合法 mission_key 集合（用来过滤 LLM 乱写的）
    valid_mission_keys = {m.key for m in (missions or [])}

    plans: list[QueryPlan] = []
    seen_queries: set[str] = set()
    for it in items:
        if not isinstance(it, dict):
            continue
        qtext = str(it.get("query_text") or "").strip()
        if not qtext or len(qtext) > 40 or qtext in seen_queries:
            continue
        seen_queries.add(qtext)
        intent = str(it.get("intent") or "evaluation").strip()
        try:
            priority = int(it.get("priority") or 50)
        except (TypeError, ValueError):
            priority = 50
        priority = max(0, min(100, priority))
        sources_raw = it.get("source_priority") or []
        sources = [str(s).strip() for s in sources_raw if str(s).strip()] if isinstance(sources_raw, list) else []
        mission_key = str(it.get("mission_key") or "").strip()
        # 校验：LLM 必须给出有效 mission_key
        if valid_mission_keys and mission_key not in valid_mission_keys:
            # 兜底：根据 intent 启发式分配
            mission_key = _infer_mission_from_intent(intent, valid_mission_keys)
        plans.append(QueryPlan(
            query_text=qtext,
            intent=intent,
            source_priority=sources[:3],
            expected_signal=str(it.get("expected_signal") or "").strip()[:100],
            priority=priority,
            mission_key=mission_key,
        ))
    return plans


def _infer_mission_from_intent(intent: str, valid_keys: set[str]) -> str:
    """LLM 没给 mission_key 时的兜底分配。"""
    intent = (intent or "").lower()
    mapping = [
        ("person", "key_persons_voice"),
        ("project", "core_projects_reception"),
        ("complaint", "negative_signals"),
        ("image", "brand_impression"),
        ("evaluation", "brand_impression"),
        ("funding", "funding_opportunities"),
        ("policy", "funding_opportunities"),
        ("industry", "industry_context"),
        ("cooperation", "funding_opportunities"),
    ]
    for kw, key in mapping:
        if kw in intent and key in valid_keys:
            return key
    # 兜底：返回 valid 集合里 priority 最低的
    return next(iter(valid_keys)) if valid_keys else ""


# ──────────────────────────────────────────────────────────────────────────
# Fallback 硬编码兜底（保留旧的搜索矩阵）
# ──────────────────────────────────────────────────────────────────────────


def _fallback_queries(signals: DataCenterSignals, *, task_type: str) -> list[QueryPlan]:
    """硬编码模板兜底。等同于之前 build_search_queries 的逻辑，但产出 QueryPlan 结构。"""
    target = signals.primary_name
    out: list[QueryPlan] = []
    seen: set[str] = set()

    def _add(q: str, intent: str, sources: list[str], priority: int) -> None:
        q = q.strip()
        if not q or q in seen:
            return
        seen.add(q)
        out.append(QueryPlan(query_text=q, intent=intent, source_priority=sources, priority=priority))

    # 主体基础
    _add(f"{target} 评价", "evaluation", ["search_engine"], 90)
    _add(f"{target} 怎么样", "evaluation", ["search_engine"], 85)
    _add(f"{target} 报道", "image", ["search_engine"], 75)
    _add(f"{target} 投诉 OR 质疑 OR 曝光", "complaint", ["search_engine"], 85)

    # 别名
    for alias in signals.aliases:
        _add(f"{alias} 评价", "evaluation", ["search_engine"], 80)
        _add(f"{alias} 怎么样", "evaluation", ["search_engine"], 75)

    # 业务域 + 项目
    if signals.domain:
        _add(f"{target} {signals.domain}", "industry", ["search_engine"], 65)
    for pm in (signals.project_modules or [])[:3]:
        _add(f"{target} {pm}", "project", ["search_engine"], 70)
        _add(f"{pm} 评价", "project", ["search_engine"], 75)

    # 人物（fallback 也用！哪怕 LLM 失败也搜人物）
    for person in (signals.glossary_persons or [])[:5]:
        _add(f"{person} 公益", "person", ["search_engine"], 70)
        _add(f"{person} {target}", "person", ["search_engine"], 75)

    # site: 限定
    if task_type == "sentiment":
        for site in ("xiaohongshu.com", "weibo.com", "zhihu.com", "douban.com"):
            _add(f"{target} site:{site}", "platform_limited", ["search_engine"], 60)

    return out


# ──────────────────────────────────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────────────────────────────────


def generate_query_plan(
    db: Database,
    ai_service: object | None,
    *,
    client_id: str,
    task_type: str = "sentiment",
    timeout_seconds: float = 90.0,
    force_fallback: bool = False,
) -> dict[str, Any]:
    """主入口：返回完整 query 矩阵 + signals 报告 + 路径来源。

    Returns:
      {
        "signals": {...},
        "health": {...},
        "queries": [QueryPlan.to_dict(), ...],
        "path": "llm" | "fallback" | "hybrid",
        "reason": "..." 可选
      }
    """
    signals = collect_signals(db, client_id=client_id)
    if not signals.primary_name:
        return {
            "signals": {},
            "health": {"score": 0, "ready": False, "notes": ["客户不存在"], "suggestions": [], "potentialQueries": 0},
            "queries": [],
            "path": "fallback",
            "reason": "client_not_found",
            "missions": [],
            "missionReadiness": None,
        }

    health = signals_health_report(signals)
    fallback_queries = _fallback_queries(signals, task_type=task_type)

    # P9-Mission：拉 mission 配置 + 算可用 mission 列表
    from app.services.intelligence_missions import (
        default_mission_config,
        effective_missions,
        mission_readiness_report,
    )
    mission_config = default_mission_config(client_id)
    signals_dict = _signals_to_dict(signals)
    active_missions = effective_missions(mission_config, signals_dict)
    readiness = mission_readiness_report(mission_config, signals_dict)

    if force_fallback:
        return {
            "signals": signals_dict,
            "health": health,
            "queries": [q.to_dict() for q in fallback_queries],
            "path": "fallback",
            "reason": "forced_fallback",
            "missions": [{"key": m.key, "name": m.name} for m in active_missions],
            "missionReadiness": readiness,
        }

    llm_queries = _llm_generate_queries(
        ai_service, signals,
        task_type=task_type,
        timeout_seconds=timeout_seconds,
        missions=active_missions,
    )

    if not llm_queries:
        # LLM 失败，纯 fallback
        return {
            "signals": signals_dict,
            "health": health,
            "queries": [q.to_dict() for q in fallback_queries],
            "path": "fallback",
            "reason": "llm_failed_or_empty",
            "missions": [{"key": m.key, "name": m.name} for m in active_missions],
            "missionReadiness": readiness,
        }

    # LLM 成功 — 用 LLM 的，但把 fallback 里 LLM 没覆盖到的 query 补齐（确保至少有基础覆盖）
    llm_query_texts = {q.query_text for q in llm_queries}
    merged = list(llm_queries)
    for fb in fallback_queries:
        if fb.query_text not in llm_query_texts:
            merged.append(fb)
    # 按 priority 倒序
    merged.sort(key=lambda q: q.priority, reverse=True)

    return {
        "signals": signals_dict,
        "health": health,
        "queries": [q.to_dict() for q in merged],
        "path": "hybrid",
        "reason": None,
        "missions": [{"key": m.key, "name": m.name} for m in active_missions],
        "missionReadiness": readiness,
    }


def _signals_to_dict(s: DataCenterSignals) -> dict[str, Any]:
    return {
        "primaryName": s.primary_name,
        "aliases": s.aliases,
        "domain": s.domain,
        "brandProposition": s.brand_proposition,
        "projectModules": s.project_modules,
        "glossaryPersons": s.glossary_persons,
        "glossaryProjects": s.glossary_projects,
        "glossaryOrgs": s.glossary_orgs,
        "glossaryMethods": s.glossary_methods,
        "knownThemes": s.known_themes,
        "hasUploadedDocs": s.has_uploaded_docs,
        "sentimentItemCount": s.sentiment_item_count,
    }
