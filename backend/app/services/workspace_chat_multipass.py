"""客户工作台问答的 Outline-First 多段生成（Pass 1 + Pass 2-N）。

设计：
- Pass 1：让快速模型基于"背景包 + 证据摘要"出大纲（headline + sections + judgment_line），1-2 秒
- Pass 2-N：基于完整 context 分段生成长文，每段独立调用、独立流式
- 每段输出后取末尾 200 字作为下一段的"接续提示"，避免重复 + 保持连贯
- 任何一段失败 → 保留已完成段，标记"答案不完整"

为什么不直接单次：
- 单次 max_tokens 5200，4-5 段累计能写 16000+ 字
- Pass 1 强制先想结构，避免"写到哪算哪"
- 每段开始就推前端 → 体感等待时间从 70 秒 → ~5 秒

调用方：``resolve_chat_answer_data_center_primary``（main.py）。
失败回退：调用方拿到 ``MultipassAnswerFailure`` 时应降级到 ``generate_raw_evidence_response`` 单次调用。
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SectionPlan:
    """一段的规划：标题 + 要点提示。"""
    title: str
    hints: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnswerOutline:
    """Pass 1 输出：一句话核心判断 + 分段规划。"""
    headline: str
    judgment_line: str
    sections: tuple[SectionPlan, ...]
    raw_response: str = ""


@dataclass
class MultipassAnswer:
    """多段生成的完整结果。

    - ``markdown``：拼接好的完整答案（含 headline / 各段）
    - ``sections_generated``：实际成功生成的段数（< len(outline.sections) 说明中途失败）
    - ``outline``：Pass 1 的规划（拿来回填 retrieval_summary）
    - ``elapsed_ms``：总耗时
    - ``llm_attempt_count``：包括 Pass 1 + 各段在内的总调用次数
    - ``failure_stage``：成功时为 None；失败时写明失败在哪一段（如 "section_3"）
    """
    markdown: str
    sections_generated: int
    outline: AnswerOutline
    elapsed_ms: float
    llm_attempt_count: int
    failure_stage: str | None = None
    section_texts: list[str] = field(default_factory=list)


class MultipassPlanError(RuntimeError):
    """Pass 1 失败（outline 没出来）。调用方应降级到单次调用。"""


# === Pass 1：大纲规划 =====================================================


_OUTLINE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["headline", "judgmentLine", "sections"],
    "properties": {
        "headline": {
            "type": "string",
            "description": "一句话核心判断，15-40 字，直接点明回答的总论断",
        },
        "judgmentLine": {
            "type": "string",
            "description": "整体回答必须 align 的判断锚点，给每段写作时引用",
        },
        "sections": {
            "type": "array",
            "minItems": 3,
            "maxItems": 6,
            "items": {
                "type": "object",
                "required": ["title", "hints"],
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "本段主题，如「差异化定位」「第二曲线布局」",
                    },
                    "hints": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "本段要展开的 2-5 个具体要点（不写句子，写关键词或短语）",
                    },
                },
            },
        },
    },
}


def plan_workspace_answer_outline(
    *,
    question: str,
    background_pack: str,
    evidence_summary: str,
    ai_service: Any,
    max_sections: int = 4,
    timeout_seconds: float = 45.0,
) -> AnswerOutline:
    """Pass 1：让快速模型出大纲。返回 ``AnswerOutline``。

    失败抛 ``MultipassPlanError``，调用方应降级到单次调用链路。
    """
    system_instruction = (
        "你是为咨询顾问做提纲的助手。任务：基于客户背景包 + 已命中证据摘要，"
        "为客户工作台的一个深度问答出大纲。"
        "严格输出一个 JSON 对象，禁止任何 markdown、解释、代码块包裹。"
        "headline：一句话核心判断，15-40 字，把回答的总论断点明，不要写「以下是分析...」这种话。"
        "judgmentLine：整体判断锚点，约 30-80 字，每段写作时要 align 这条判断，避免漂题。"
        f"sections：3-{max_sections} 个深度段落规划。每段一个独立的角度，不要把不同角度合并到一段。"
        "每段的 title 必须是具体角度（如「差异化定位」「第二曲线布局」「落地节奏」），"
        "不要是「概述」「总结」「展望」这类空标题。"
        "每段 hints 给 2-5 个具体要点，写关键词或短语（如「锚定预防前置」「不走问题干预路径」），"
        '不要写完整句子。hints 是给后续写作的「小抄」，越具体越好。'
    )
    user_prompt = (
        "用户问题：\n"
        f"{question.strip()}\n\n"
        "客户背景包（已知事实，不需要再确认）：\n"
        "<<<BACKGROUND>>>\n"
        f"{(background_pack or '').strip()[:8000]}\n"
        "<<<END BACKGROUND>>>\n\n"
        "已命中证据摘要（仅用于判断需要哪些角度，正文生成时会有完整证据）：\n"
        "<<<EVIDENCE>>>\n"
        f"{(evidence_summary or '').strip()[:6000]}\n"
        "<<<END EVIDENCE>>>\n\n"
        "请输出 JSON：{headline, judgmentLine, sections:[{title, hints:[]}]}"
    )

    started = time.perf_counter()
    try:
        raw_response = ai_service._qwen_generate(  # noqa: SLF001 — 内部约定
            prompt=user_prompt,
            system_instruction=system_instruction,
            response_schema=_OUTLINE_SCHEMA,
            timeout_seconds=timeout_seconds,
            max_tokens=1200,
            temperature=0.3,
            top_p=0.85,
            enable_thinking=False,
            task_kind="fast_structured",
        )
    except Exception as exc:
        raise MultipassPlanError(f"Pass1 调用失败：{exc}") from exc

    raw_text = str(raw_response or "").strip()
    parsed = _parse_outline_json(raw_text)
    if parsed is None:
        raise MultipassPlanError(f"Pass1 返回无法解析为 JSON：{raw_text[:200]}")

    headline = str(parsed.get("headline") or "").strip()
    judgment_line = str(parsed.get("judgmentLine") or "").strip()
    sections_raw = parsed.get("sections")
    if not isinstance(sections_raw, list) or not sections_raw:
        raise MultipassPlanError("Pass1 缺少 sections 字段或为空")

    sections: list[SectionPlan] = []
    for item in sections_raw[:max_sections]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        hints_raw = item.get("hints")
        hints: list[str] = []
        if isinstance(hints_raw, list):
            for h in hints_raw:
                txt = str(h or "").strip()
                if txt and txt not in hints:
                    hints.append(txt)
        sections.append(SectionPlan(title=title, hints=tuple(hints[:5])))

    if not sections:
        raise MultipassPlanError("Pass1 sections 全部解析失败")
    if not headline:
        headline = sections[0].title
    if not judgment_line:
        judgment_line = headline

    logger.info(
        "[multipass] outline planned in %.2fs: headline=%s sections=%d",
        time.perf_counter() - started, headline[:40], len(sections),
    )
    return AnswerOutline(
        headline=headline,
        judgment_line=judgment_line,
        sections=tuple(sections),
        raw_response=raw_text,
    )


def _parse_outline_json(raw: str) -> dict[str, Any] | None:
    """尝试把 LLM 输出解析成 dict。带 markdown ```json 包裹、首尾解释都能兜住。"""
    if not raw:
        return None
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            return None
        try:
            result = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return result if isinstance(result, dict) else None


# === Pass 2-N：分段生成 ===================================================


def generate_workspace_answer_section(
    *,
    question: str,
    section_plan: SectionPlan,
    section_index: int,
    total_sections: int,
    headline: str,
    judgment_line: str,
    full_context: str,
    previous_section_recaps: list[str],
    ai_service: Any,
    on_partial: Callable[[dict[str, Any]], None] | None = None,
    timeout_seconds: float = 180.0,
    max_tokens: int = 4500,
) -> str:
    """生成单段长文。

    输入：
    - section_plan: 本段标题 + hints
    - previous_section_recaps: 已生成段的末尾摘要（最近 1-2 段，避免重复）
    - full_context: 完整背景包 + 证据包

    返回纯文本（markdown 格式），失败抛异常。
    """
    hints_block = ""
    if section_plan.hints:
        hints_block = "本段要点（不一定全用，作为'小抄'）：\n" + "\n".join(
            f"- {h}" for h in section_plan.hints
        )

    recap_block = ""
    if previous_section_recaps:
        recap_block = (
            "前面已经写过的段落末尾（参考接续，不要重述前面说过的内容）：\n"
            + "\n\n".join(
                f"【前文段 {idx + 1} 末尾】\n{recap.strip()[-260:]}"
                for idx, recap in enumerate(previous_section_recaps[-2:])
                if recap.strip()
            )
        )

    section_instruction = (
        "你是这家组织的资深陪伴顾问，正在写一份深度问答的其中一段。"
        f"整体回答有 {total_sections} 段，本段是第 {section_index + 1} 段，主题：「{section_plan.title}」。"
        f"整体核心判断：{headline}"
        f"\n判断锚点：{judgment_line}"
        "\n本段必须 align 上面的判断锚点，不要漂到无关角度。"
        '\n只写这一段，不要写整体引言或总结，不要重述前面段落已经说过的内容；做「接续」，不做「重复」。'
        "\n必须落到具体的项目名、合作方、活动名、数字、时间节点、人物角色——这些细节都在原始资料里，要去挖。"
        "\n不要满足于在画像层面做抽象总结。一段的长度 600-1500 字，写得充分一些。"
        "\n不要输出本段的小标题（如「第三段：xxx」），直接写正文段落。"
        "\n不要列资料名、不要暴露系统过程。"
    )

    user_prompt_parts = [
        f"用户原问题：{question.strip()}",
        "",
        f"本段主题：「{section_plan.title}」",
    ]
    if hints_block:
        user_prompt_parts.append(hints_block)
    if recap_block:
        user_prompt_parts.append(recap_block)
    user_prompt_parts.extend([
        "",
        "完整背景包 + 原始资料：",
        full_context,
        "",
        f"请按系统指令写本段（「{section_plan.title}」）的正文，长度 600-1500 字。",
    ])
    user_prompt = "\n".join(user_prompt_parts)

    if on_partial is not None:
        on_partial({
            "stageLabel": f"正在生成第 {section_index + 1}/{total_sections} 段：{section_plan.title}",
            "progress": 62.0 + (section_index / max(1, total_sections)) * 30,
            "content": "",
            "structured": None,
            "sectionIndex": section_index,
        })

    started = time.perf_counter()
    try:
        text = ai_service._qwen_generate(  # noqa: SLF001
            prompt=user_prompt,
            system_instruction=section_instruction,
            response_schema=None,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
            temperature=0.55,
            top_p=0.95,
            enable_thinking=True,
            task_kind="deep_analysis",
        )
    except Exception as exc:
        elapsed = time.perf_counter() - started
        raise RuntimeError(
            f"Pass2 第 {section_index + 1} 段调用失败（用时 {elapsed:.1f}s）：{exc}"
        ) from exc

    result_text = str(text or "").strip()
    if not result_text:
        raise RuntimeError(f"Pass2 第 {section_index + 1} 段返回为空")
    logger.info(
        "[multipass] section %d/%d generated in %.2fs (%d chars)",
        section_index + 1, total_sections,
        time.perf_counter() - started, len(result_text),
    )
    return result_text


# === 编排器 ===============================================================


def generate_multipass_answer(
    *,
    question: str,
    background_pack: str,
    evidence_summary: str,
    full_context: str,
    ai_service: Any,
    on_section_started: Callable[[int, SectionPlan], None] | None = None,
    on_section_partial: Callable[[int, dict[str, Any]], None] | None = None,
    on_section_completed: Callable[[int, str, str], None] | None = None,
    on_outline_ready: Callable[[AnswerOutline], None] | None = None,
    max_sections: int = 4,
    section_max_tokens: int = 4500,
) -> MultipassAnswer:
    """主编排：Pass 1 出大纲 → Pass 2-N 分段生成 → 拼接答案。

    回调：
    - ``on_outline_ready(outline)``：Pass 1 完成立刻调，让 UI 显示 headline
    - ``on_section_started(index, plan)``：每段开始前
    - ``on_section_partial(index, partial)``：每段流式 partial（如果 LLM 支持）
    - ``on_section_completed(index, plan_title, section_text)``：每段完成后
      调用方应在这里把累计 markdown 推给前端 chat_message
    """
    started = time.perf_counter()
    llm_attempt_count = 0

    # Pass 1
    llm_attempt_count += 1
    outline = plan_workspace_answer_outline(
        question=question,
        background_pack=background_pack,
        evidence_summary=evidence_summary,
        ai_service=ai_service,
        max_sections=max_sections,
    )
    if on_outline_ready is not None:
        on_outline_ready(outline)

    sections_to_generate = outline.sections
    section_texts: list[str] = []
    failure_stage: str | None = None

    for index, plan in enumerate(sections_to_generate):
        if on_section_started is not None:
            on_section_started(index, plan)
        try:
            llm_attempt_count += 1
            section_text = generate_workspace_answer_section(
                question=question,
                section_plan=plan,
                section_index=index,
                total_sections=len(sections_to_generate),
                headline=outline.headline,
                judgment_line=outline.judgment_line,
                full_context=full_context,
                previous_section_recaps=section_texts,
                ai_service=ai_service,
                on_partial=(lambda partial, _idx=index: on_section_partial(_idx, partial))
                if on_section_partial is not None else None,
                max_tokens=section_max_tokens,
            )
        except Exception as exc:
            logger.warning("[multipass] section %d failed: %s", index + 1, exc, exc_info=True)
            failure_stage = f"section_{index + 1}"
            break
        section_texts.append(section_text)
        if on_section_completed is not None:
            on_section_completed(index, plan.title, section_text)

    markdown = _compose_markdown(outline.headline, sections_to_generate[: len(section_texts)], section_texts)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return MultipassAnswer(
        markdown=markdown,
        sections_generated=len(section_texts),
        outline=outline,
        elapsed_ms=elapsed_ms,
        llm_attempt_count=llm_attempt_count,
        failure_stage=failure_stage,
        section_texts=section_texts,
    )


def _compose_markdown(headline: str, plans: tuple[SectionPlan, ...] | list[SectionPlan], texts: list[str]) -> str:
    """把 headline + 各段拼成最终 markdown。

    格式：
        # {headline}

        {第一段正文}

        ## {第二段标题}

        {第二段正文}
        ...
    第一段直接接在 headline 后，后面段落用 `##` 标题分隔。
    """
    if not texts:
        return ""
    lines: list[str] = []
    if headline:
        lines.append(f"# {headline.strip()}")
        lines.append("")
    for index, (plan, text) in enumerate(zip(plans, texts)):
        if index > 0:
            lines.append("")
            lines.append(f"## {plan.title.strip()}")
            lines.append("")
        lines.append(text.strip())
    return "\n".join(lines).strip()
