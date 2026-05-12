"""R2 · 调豆包 Seed 2.0 Pro（角色 B：章节起草员）写单节正文。

LLM B 拿到：
  - SectionPlan（title/goal/level/data_sources/chart_hints/estimated_words/citation_budget）
  - 报告全局基调（title/audience/tone）
  - 完整 context（同 LLM A，重用 render_for_prompt）

输出（结构化 JSON）：
  - markdown 正文（含 [CHART:idx] 占位）
  - citations[]（引用条目）
  - charts[]（每个 chart_hint 对应的具体数据）
  - data_source_annotation（章末"数据源"自然语句）
  - confidence / warnings

drafter 在拿到 LLM 输出后，对每个 chart_hint 立即调 materialize_chart 生 PNG。
chart 生成失败不让整节失败，记入 warnings，对应位置留空 base64。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.models import (
    CitationRef,
    GeneratedChart,
    SectionContent,
    SectionPlan,
)
from app.services.ai import AiService
from app.services.report_chart_materializer import (
    ChartMaterializeError,
    materialize_chart,
)
from app.services.report_context_builder import ReportPromptContext


logger = logging.getLogger(__name__)


_VALID_CITATION_TYPES = {
    "judgment",
    "event",
    "task",
    "document",
    "metric",
    "commit",
}


class SectionDraftError(RuntimeError):
    """章节起草失败（LLM 多次重试都没拿到有效内容）。"""


SYSTEM_INSTRUCTION = """你是益语智库"章节起草员"——为已经定好骨架的报告，按章节填写正文。

你只填写**一节**。这一节的 plan 已经给好（title / goal / level / data_sources / chart_hints / estimated_words / citation_budget）。

任务要求：
1. 严格围绕 plan.goal 写正文（markdown，不要写章节标题——由渲染器加）
2. 字数控制在 estimated_words ± 30%
3. 引用：在正文里**自然带过**事实出处；章末用一段简短的"数据源"自然语句概括；
   需要交代具体事实时，请同时在 citations 数组里列出引用条目（不超过 citation_budget × 2 条）
4. 图：对 plan.chart_hints 里的每个 hint，**必须**在 charts 数组里给出对应数据，
   并在 markdown 里用 [CHART:idx] 占位符表示该图位置（idx 是 chart_hints 数组下标）
5. 不要编造事实——只用上下文里给到的事件、判断、文档、指标
6. 如果上下文不足以支撑某节，请在 warnings 里说明

可用 chart 类型与数据形状：
- pie: {"labels": ["类别1","类别2"], "counts": [10, 5]}
- progress_bar_h: {"items": ["模块1","模块2"], "before": [40, 30], "after": [80, 60], "target": 70}
   （target 可选）
- timeline: {"events": [["2026-01-10","启动会","done"], ["2026-02-15","中期检视","in_progress"], ...]}
   status ∈ {done, in_progress, planned}
- grouped_bar: {"categories":["Q1","Q2"], "series_a_name":"实际", "series_a_values":[12,18],
                "series_b_name":"目标", "series_b_values":[10,20], "y_label":"数量"}
- risk_bubble: {"risks": [["人员流失",4,3,2.0], ["资金不足",3,4,3.0]]}
   每条是 [name, impact 0-5, prob 0-5, weight]
- table_only / callout_only: 不需要 data 字段（直接在 markdown 里写表格或强调段落）

输出严格 JSON：
{
  "markdown": "正文 markdown，含 [CHART:0] 等占位符",
  "citations": [
    {"type": "event|task|document|judgment|metric|commit",
     "id": "源 ID（来自上下文，如 act-uuid / task-uuid / 文档名）",
     "label": "短标签（如 '1月10日启动会'）",
     "excerpt": "可选原文片段"}
  ],
  "charts": [
    {"chart_hint_idx": 0, "data": {...如上...}}
  ],
  "data_source_annotation": "本节数据源：事件线 ...; 任务列表 ...",
  "confidence": 0.0-1.0,
  "warnings": ["如有不确定项"]
}

要求：
- 不要用 Markdown 代码块包裹 JSON
- 不要解释
- charts 数组里 chart_hint_idx 必须对得上 plan.chart_hints 下标
"""


def draft_section(
    ai: AiService,
    *,
    plan: SectionPlan,
    context: ReportPromptContext,
    blueprint_title: str,
    blueprint_audience: str,
    blueprint_tone: str,
    section_idx: int,
    max_retries: int = 3,
    timeout_seconds: float = 90.0,
    max_tokens: int = 3500,
) -> SectionContent:
    """调豆包写一节 markdown + materialize 每个 chart_hint。

    成功返回 SectionContent（含已渲染为 base64 的 charts）；
    失败 N 次后抛 SectionDraftError。
    """
    user_prompt = _build_user_prompt(
        plan,
        context,
        blueprint_title=blueprint_title,
        blueprint_audience=blueprint_audience,
        blueprint_tone=blueprint_tone,
    )

    errors: list[str] = []
    last_payload: Any = None

    for attempt in range(1, max_retries + 1):
        prompt_for_attempt = user_prompt
        if attempt > 1 and last_payload is not None:
            prompt_for_attempt = (
                f"{user_prompt}\n\n"
                "上一次输出未通过校验，请重出。\n"
                "上次返回（已截断）：\n"
                f"{json.dumps(last_payload, ensure_ascii=False)[:1200]}"
            )

        try:
            raw = ai._qwen_generate(
                prompt=prompt_for_attempt,
                system_instruction=SYSTEM_INSTRUCTION,
                response_schema=_SECTION_RESPONSE_SCHEMA,
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
                temperature=0.55,
                top_p=0.9,
            )
        except Exception as exc:
            errors.append(f"第 {attempt} 次调 LLM 失败：{exc}")
            logger.warning(
                "section %d attempt %d LLM call failed: %s",
                section_idx,
                attempt,
                exc,
            )
            continue

        if not isinstance(raw, dict):
            errors.append(
                f"第 {attempt} 次返回非 JSON: {type(raw).__name__}"
            )
            last_payload = raw
            continue
        last_payload = raw

        try:
            return _build_section_content(plan, raw)
        except SectionDraftError as exc:
            errors.append(f"第 {attempt} 次构造 SectionContent 失败：{exc}")
            continue

    raise SectionDraftError(
        f"章节 #{section_idx}「{plan.title}」连续 {max_retries} 次失败："
        + "; ".join(errors[-3:])
    )


def _build_user_prompt(
    plan: SectionPlan,
    context: ReportPromptContext,
    *,
    blueprint_title: str,
    blueprint_audience: str,
    blueprint_tone: str,
) -> str:
    chart_block = ""
    if plan.chart_hints:
        chart_block = "\n# 本节 chart_hints（按下标输出对应 charts[i]）\n"
        for i, ch in enumerate(plan.chart_hints):
            caption = ch.caption or "—"
            chart_block += (
                f"- [chart_hint_idx={i}] kind={ch.kind} title={ch.title} "
                f"caption={caption} data_source_hint={ch.data_source_hint}\n"
            )

    return (
        "# 报告全局\n"
        f"- 报告标题：{blueprint_title}\n"
        f"- 目标读者：{blueprint_audience}\n"
        f"- 整体基调：{blueprint_tone}\n\n"
        "# 本节 plan\n"
        f"- 章节标题：{plan.title}\n"
        f"- 章节目标：{plan.goal}\n"
        f"- 字数预算：{plan.estimated_words} 字（±30%）\n"
        f"- 引用预算：{plan.citation_budget} 条以内\n"
        f"- 推荐数据来源：{', '.join(plan.data_sources) or '自由判断'}\n"
        f"{chart_block}\n"
        "# 完整上下文\n\n"
        f"{context.render_for_prompt()}\n\n"
        "请只输出 JSON。"
    )


def _build_section_content(
    plan: SectionPlan, raw: dict[str, Any]
) -> SectionContent:
    markdown = str(raw.get("markdown") or "").strip()
    if not markdown:
        raise SectionDraftError("LLM 没返回 markdown 正文")

    citations = _parse_citations(raw.get("citations"), plan.citation_budget)

    warnings: list[str] = [
        str(w).strip()
        for w in (raw.get("warnings") or [])
        if str(w or "").strip()
    ]

    materialized = _materialize_charts(plan, raw.get("charts"), warnings)

    data_source_annotation = str(
        raw.get("data_source_annotation") or ""
    ).strip()

    try:
        confidence = max(0.0, min(1.0, float(raw.get("confidence", 0.7))))
    except (TypeError, ValueError):
        confidence = 0.7

    return SectionContent(
        plan=plan,
        markdown=markdown,
        citations=citations,
        charts=materialized,
        data_source_annotation=data_source_annotation,
        confidence=confidence,
        warnings=warnings,
    )


def _parse_citations(
    raw_citations: Any, citation_budget: int
) -> list[CitationRef]:
    if not isinstance(raw_citations, list):
        return []
    citations: list[CitationRef] = []
    for c in raw_citations:
        if not isinstance(c, dict):
            continue
        c_type = str(c.get("type") or "").strip()
        if c_type not in _VALID_CITATION_TYPES:
            continue
        c_id = str(c.get("id") or "").strip()
        c_label = str(c.get("label") or "").strip()
        if not c_id or not c_label:
            continue
        excerpt = c.get("excerpt")
        if excerpt is not None:
            excerpt_text = str(excerpt).strip()
            excerpt = excerpt_text or None
        citations.append(
            CitationRef(
                type=c_type,  # type: ignore[arg-type]
                id=c_id,
                label=c_label,
                excerpt=excerpt,
            )
        )
    cap = max(citation_budget * 2, 0)
    if cap and len(citations) > cap:
        citations = citations[:cap]
    return citations


def _materialize_charts(
    plan: SectionPlan, raw_charts: Any, warnings: list[str]
) -> list[GeneratedChart]:
    if not isinstance(raw_charts, list):
        raw_charts = []

    chart_by_idx: dict[int, dict[str, Any]] = {}
    for c in raw_charts:
        if not isinstance(c, dict):
            continue
        idx_raw = c.get("chart_hint_idx")
        try:
            idx = int(idx_raw)
        except (TypeError, ValueError):
            continue
        if idx < 0 or idx >= len(plan.chart_hints):
            continue
        chart_by_idx[idx] = c

    materialized: list[GeneratedChart] = []
    for idx, hint in enumerate(plan.chart_hints):
        c = chart_by_idx.get(idx)
        if c is None:
            warnings.append(
                f"chart_hint #{idx} ({hint.kind}/{hint.title}) "
                "缺少 LLM 数据"
            )
            materialized.append(
                GeneratedChart(hint=hint, png_bytes_base64="", width_cm=14.5)
            )
            continue
        data = c.get("data") or {}
        if not isinstance(data, dict):
            data = {}
        try:
            materialized.append(materialize_chart(hint, data))
        except ChartMaterializeError as exc:
            warnings.append(
                f"chart_hint #{idx} ({hint.kind}) 生成失败：{exc}"
            )
            materialized.append(
                GeneratedChart(hint=hint, png_bytes_base64="", width_cm=14.5)
            )
    return materialized


_SECTION_RESPONSE_SCHEMA: dict[str, object] = {
    "type": "OBJECT",
    "properties": {
        "markdown": {"type": "STRING"},
        "citations": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "type": {"type": "STRING"},
                    "id": {"type": "STRING"},
                    "label": {"type": "STRING"},
                    "excerpt": {"type": "STRING"},
                },
            },
        },
        "charts": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "chart_hint_idx": {"type": "INTEGER"},
                    "data": {"type": "OBJECT"},
                },
            },
        },
        "data_source_annotation": {"type": "STRING"},
        "confidence": {"type": "NUMBER"},
        "warnings": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
}
