"""R1 · 调豆包 Seed 2.0 Pro（角色 A：报告主理人）推导报告骨架。

输入：ReportPromptContext（由 report_context_builder 构造）
输出：ReportBlueprint（已经通过 Pydantic 校验）

策略：
- 用 AiService._qwen_generate(response_schema=...) 走 JSON 模式
- 最多 retry max_retries 次；第 2 / 3 次在 prompt 里附上"上次失败原因"做矫正
- LLM 输出有缺字段时走 _normalize_blueprint_payload 兜底，不轻易认输
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.models import ReportBlueprint
from app.services.ai import AiService
from app.services.report_context_builder import ReportPromptContext


logger = logging.getLogger(__name__)


_VALID_CHART_KINDS = {
    "pie",
    "progress_bar_h",
    "timeline",
    "grouped_bar",
    "risk_bubble",
    "table_only",
    "callout_only",
}


SYSTEM_INSTRUCTION = """你是益语智库"报告主理人"——一位资深的研究与陪伴顾问，
帮助决策者把一段事件线、一组客户协作素材，凝练成一份对外可呈交的报告骨架。

你的产出**不是报告内容**，而是"这份报告该长什么样"的骨架（blueprint）。骨架要：
1. 紧扣事件线的真实主题与阶段——不要套模板
2. 反映客户当前最关心的问题——不要事无巨细
3. 结构清晰，章节之间逻辑递进
4. 每个章节带 goal（这一节回答什么问题）、data_sources（建议从哪几类数据取证）、chart_hints（建议哪些图）
5. 信任你自己的判断——如果事件线适合长篇分析就长一点，适合简报就短一点

可用图表类型：
- pie：成分占比（如评估维度分布）
- progress_bar_h：横向进度条（一组指标的完成度对比）
- timeline：时间线/里程碑
- grouped_bar：分组柱状图（两组指标对比）
- risk_bubble：风险气泡图（影响 × 概率）
- table_only：只用表格
- callout_only：只用强调框，不画图

可用 data_sources 关键词（你只需写出关键词，不需写 SQL）：
- events：事件线活动条目
- tasks：与事件线相关的任务
- documents：客户的文件/资料/资产
- judgments：主理人判断与决策记录
- metrics：客户档案中的量化指标
- snapshot：事件线最新状态快照
- org_profile：客户组织档案

要求：
- sections 3-7 个（不少于 3，不多于 7）
- 不要编造没有的数据来源
- 不要在 blueprint 里写正文
- 严格返回 JSON 对象，不要用 Markdown 代码块包裹，不要解释
"""


class BlueprintDraftError(RuntimeError):
    """Blueprint 草拟连续多次失败（重试也救不回来）。"""


def draft_report_blueprint(
    ai: AiService,
    *,
    context: ReportPromptContext,
    max_retries: int = 3,
    timeout_seconds: float = 60.0,
    max_tokens: int = 3200,
) -> ReportBlueprint:
    user_prompt = _build_user_prompt(context)
    errors: list[str] = []
    last_payload: Any = None

    for attempt in range(1, max_retries + 1):
        prompt_for_attempt = user_prompt
        if attempt > 1 and last_payload is not None:
            prompt_for_attempt = (
                f"{user_prompt}\n\n"
                "上一次输出未通过校验，请仔细对照 schema 重出。\n"
                "上次返回（已截断）：\n"
                f"{json.dumps(last_payload, ensure_ascii=False)[:1200]}"
            )

        try:
            raw = ai._qwen_generate(
                prompt=prompt_for_attempt,
                system_instruction=SYSTEM_INSTRUCTION,
                response_schema=_BLUEPRINT_RESPONSE_SCHEMA,
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
                temperature=0.45,
                top_p=0.9,
            )
        except Exception as exc:
            errors.append(f"第 {attempt} 次调用 LLM 失败：{exc}")
            logger.warning(
                "blueprint_drafter attempt %d call failed: %s", attempt, exc
            )
            continue

        if not isinstance(raw, dict):
            errors.append(
                f"第 {attempt} 次返回非 JSON 对象：{type(raw).__name__}"
            )
            last_payload = raw
            continue

        last_payload = raw
        normalized = _normalize_blueprint_payload(raw, context)
        try:
            return ReportBlueprint.model_validate(normalized)
        except Exception as exc:
            errors.append(f"第 {attempt} 次 Pydantic 校验失败：{exc}")
            logger.warning(
                "blueprint_drafter attempt %d validation failed: %s",
                attempt,
                exc,
            )

    raise BlueprintDraftError(
        f"豆包 blueprint 草拟连续 {max_retries} 次失败：" + "；".join(errors[-3:])
    )


def _build_user_prompt(context: ReportPromptContext) -> str:
    return (
        "请根据下面的事件线与客户素材，推导一份合适的报告骨架。\n\n"
        + context.render_for_prompt()
        + "\n\n请记住：你输出的是骨架（结构），不要写正文。"
    )


def _normalize_blueprint_payload(
    payload: dict[str, Any], context: ReportPromptContext
) -> dict[str, Any]:
    """补齐缺失字段、修正显式异常，让 Pydantic 校验更容易通过。"""
    out = dict(payload)

    default_title = (
        f"{context.event_line_name}报告"
        if context.event_line_name
        else (
            f"{context.client_name}事件线报告"
            if context.client_name
            else "事件线报告"
        )
    )
    out.setdefault("title", default_title)
    if not out.get("title"):
        out["title"] = default_title
    out.setdefault("subtitle", None)
    out.setdefault("report_kind", "事件线综合报告")
    out.setdefault("audience", context.audience_hint or "客户与主理人")
    out.setdefault("tone", context.tone_hint or "客观、克制、可执行")
    out.setdefault("period_start", context.period_start)
    out.setdefault("period_end", context.period_end)
    out.setdefault("inferred_theme", out.get("title") or default_title)
    out.setdefault("open_questions_for_human", [])

    if not isinstance(out["open_questions_for_human"], list):
        out["open_questions_for_human"] = []
    out["open_questions_for_human"] = [
        str(q).strip()
        for q in out["open_questions_for_human"]
        if str(q or "").strip()
    ]

    try:
        out["confidence"] = max(
            0.0, min(1.0, float(out.get("confidence", 0.7)))
        )
    except (TypeError, ValueError):
        out["confidence"] = 0.7

    raw_sections = out.get("sections") or []
    if not isinstance(raw_sections, list):
        raw_sections = []
    normalized_sections: list[dict[str, Any]] = []
    for sec_raw in raw_sections:
        if not isinstance(sec_raw, dict):
            continue
        sec = _normalize_section(sec_raw)
        if sec:
            normalized_sections.append(sec)

    if not normalized_sections:
        normalized_sections = _fallback_sections()

    if len(normalized_sections) > 7:
        normalized_sections = normalized_sections[:7]

    out["sections"] = normalized_sections
    out["event_line_id"] = context.event_line_id or None
    out["client_id"] = context.client_id
    out["generated_at"] = datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )

    return out


def _normalize_section(sec_raw: dict[str, Any]) -> dict[str, Any] | None:
    sec = dict(sec_raw)
    title = str(sec.get("title") or "").strip()
    if not title:
        return None
    sec["title"] = title
    sec["goal"] = str(sec.get("goal") or "").strip()

    try:
        sec["level"] = max(1, min(2, int(sec.get("level", 1))))
    except (TypeError, ValueError):
        sec["level"] = 1
    try:
        sec["citation_budget"] = max(0, int(sec.get("citation_budget", 5)))
    except (TypeError, ValueError):
        sec["citation_budget"] = 5
    try:
        sec["estimated_words"] = max(
            50, min(2000, int(sec.get("estimated_words", 300)))
        )
    except (TypeError, ValueError):
        sec["estimated_words"] = 300

    data_sources = sec.get("data_sources")
    if not isinstance(data_sources, list):
        data_sources = []
    sec["data_sources"] = [
        str(item).strip() for item in data_sources if str(item or "").strip()
    ]

    chart_hints_raw = sec.get("chart_hints")
    if not isinstance(chart_hints_raw, list):
        chart_hints_raw = []
    valid_chart_hints: list[dict[str, Any]] = []
    for ch_raw in chart_hints_raw:
        if not isinstance(ch_raw, dict):
            continue
        kind = str(ch_raw.get("kind") or "").strip()
        if kind not in _VALID_CHART_KINDS:
            continue
        title_ch = str(ch_raw.get("title") or "").strip() or "信息图"
        caption = ch_raw.get("caption")
        if caption is not None:
            caption = str(caption).strip() or None
        valid_chart_hints.append(
            {
                "kind": kind,
                "title": title_ch,
                "caption": caption,
                "data_source_hint": str(
                    ch_raw.get("data_source_hint") or ""
                ).strip(),
            }
        )
    sec["chart_hints"] = valid_chart_hints
    return sec


def _fallback_sections() -> list[dict[str, Any]]:
    return [
        {
            "level": 1,
            "title": "事件线概览",
            "goal": "梳理本期事件线的整体进展与关键节点",
            "data_sources": ["events", "snapshot"],
            "chart_hints": [
                {
                    "kind": "timeline",
                    "title": "事件时间线",
                    "caption": None,
                    "data_source_hint": "event_line_activities",
                }
            ],
            "citation_budget": 5,
            "estimated_words": 400,
        },
        {
            "level": 1,
            "title": "主理人判断",
            "goal": "提炼当前最重要的洞察、风险与机会",
            "data_sources": ["judgments", "snapshot"],
            "chart_hints": [],
            "citation_budget": 5,
            "estimated_words": 350,
        },
        {
            "level": 1,
            "title": "下一步行动建议",
            "goal": "给出可落地的下一阶段行动",
            "data_sources": ["tasks", "snapshot"],
            "chart_hints": [],
            "citation_budget": 3,
            "estimated_words": 250,
        },
    ]


_BLUEPRINT_RESPONSE_SCHEMA: dict[str, object] = {
    "type": "OBJECT",
    "properties": {
        "title": {"type": "STRING"},
        "subtitle": {"type": "STRING"},
        "report_kind": {"type": "STRING"},
        "audience": {"type": "STRING"},
        "tone": {"type": "STRING"},
        "period_start": {"type": "STRING"},
        "period_end": {"type": "STRING"},
        "inferred_theme": {"type": "STRING"},
        "confidence": {"type": "NUMBER"},
        "open_questions_for_human": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
        "sections": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "level": {"type": "INTEGER"},
                    "title": {"type": "STRING"},
                    "goal": {"type": "STRING"},
                    "data_sources": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                    },
                    "chart_hints": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "kind": {"type": "STRING"},
                                "title": {"type": "STRING"},
                                "caption": {"type": "STRING"},
                                "data_source_hint": {"type": "STRING"},
                            },
                        },
                    },
                    "citation_budget": {"type": "INTEGER"},
                    "estimated_words": {"type": "INTEGER"},
                },
            },
        },
    },
}
