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

import ast
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
    strategic_pack: str = "",
    max_sections: int = 4,
    timeout_seconds: float = 45.0,
) -> AnswerOutline:
    """Pass 1：让快速模型出大纲。返回 ``AnswerOutline``。

    失败抛 ``MultipassPlanError``，调用方应降级到单次调用链路。

    ``strategic_pack`` 是「战略层素材包」（组织 DNA / 已采纳判断的推导链 /
    项目演进时间线 / 历史已沉淀的关键观点），用于让大纲能跳出"项目进展"
    层面、形成战略层的判断角度。不传则退化为旧行为。
    """
    system_instruction = (
        "你是为咨询顾问做提纲的助手。任务：基于客户背景包 + 战略素材 + 已命中证据摘要，"
        "为客户工作台的一个深度问答出大纲。"
        "严格输出一个 JSON 对象，禁止任何 markdown、解释、代码块包裹。"
        "headline：一句话核心判断，15-40 字，把回答的总论断点明，不要写「以下是分析...」这种话。"
        "judgmentLine：整体判断锚点，约 30-80 字，每段写作时要 align 这条判断，避免漂题。"
        f"sections：3-{max_sections} 个深度段落规划。每段一个独立的角度，不要把不同角度合并到一段。"
        "每段的 title 必须是具体角度（如「差异化定位」「第二曲线布局」「落地节奏」），"
        "不要是「概述」「总结」「展望」这类空标题。"
        "每段 hints 给 2-5 个具体要点，写关键词或短语（如「锚定预防前置」「不走问题干预路径」），"
        '不要写完整句子。hints 是给后续写作的「小抄」，越具体越好。'
        "\n如果战略素材里已经写出了组织级的差异化定位、赛道边界、项目演进时间线、"
        "已被采纳的核心判断、或顾问视角的关键观点，优先把这些作为 section title 候选，"
        "不要停留在项目进展、落地节奏这种表层切片。每个 section 都应该是一个独立成立的判断角度，"
        "而不是同一现象的另一种说法。"
    )
    strategic_block = ""
    if (strategic_pack or "").strip():
        strategic_block = (
            "战略素材（组织级的定位/判断/演进/历史观点，是出角度的主要依据）：\n"
            "<<<STRATEGIC>>>\n"
            f"{(strategic_pack or '').strip()[:13000]}\n"
            "<<<END STRATEGIC>>>\n\n"
        )
    user_prompt = (
        "用户问题：\n"
        f"{question.strip()}\n\n"
        + strategic_block +
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
    raw_response = None
    last_exc: Exception | None = None
    # Pass 1 同样可能遇到 SSL EOF / 网络抖动，最多 3 次尝试。
    for attempt in range(3):
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
            break
        except Exception as exc:
            last_exc = exc
            logger.warning("[multipass] pass1 attempt %d/3 failed: %s", attempt + 1, exc)
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    if raw_response is None:
        raise MultipassPlanError(f"Pass1 调用 3 次都失败：{last_exc}") from last_exc

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
    """尝试把 LLM 输出解析成 dict。

    实测豆包等模型有时会输出 **Python repr 风格**（单引号字典字面量），不是合法 JSON。
    本函数 4 级兜底：
    1. ``json.loads(cleaned)`` —— 标准 JSON
    2. ``ast.literal_eval(cleaned)`` —— Python 单引号字典字面量
    3. 用正则抽出 ``{...}`` 块后再走 (1)+(2)
    4. 实在不行 → return None
    """
    if not raw:
        return None
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json|python)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()

    def _try(text: str) -> Any:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        try:
            return ast.literal_eval(text)
        except (SyntaxError, ValueError):
            pass
        return None

    result = _try(cleaned)
    if result is None:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            return None
        result = _try(match.group(0))
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
    writing_skill_md: str = "",
    creativity_mode: str = "strict",
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

    # R6：写作风格 skill 优先级最高，放在 system_instruction 最顶部
    style_prefix = ""
    if (writing_skill_md or "").strip():
        style_prefix = (
            "【写作风格约束 —— 必须遵守，优先级最高】\n"
            f"{writing_skill_md.strip()}\n"
            "【写作风格约束结束】\n\n"
            "下面是常规的角色和段落写作规范，与上面的风格约束冲突时以风格约束为准（除事实准确性外）。\n\n"
        )
    # R7：创意度三档 prompt
    creativity_block = ""
    if creativity_mode == "creative":
        creativity_block = (
            "【创意优先 · 自由创作模式】\n"
            "本段写作等同于通用 LLM 对话窗口：仅基于用户原问题 + 当前对话框提供的内容写作。\n"
            "**不引用**任何客户资料、文档库、组织内部信息。完全释放想象力。\n\n"
        )
    elif creativity_mode == "balanced":
        creativity_block = (
            "【兼顾资料 · 默认创作模式】\n"
            "客户资料是**事实底色和背景**，不是直接复述对象。\n"
            "硬事实（数字、人名、产品名、机构名、时间节点）**绝对不能编造**。\n"
            "**但**：叙事结构、句式、修辞、表达质感、措辞、隐喻、整体气质——**完全自由发挥**。\n"
            "目标是写出**有作者意识**的文章：事实是骨头，语言是血肉。\n"
            "**不要**写「[资料1]」「(见 XX.pdf)」溯源标记，不要被资料的逐条罗列引诱去复述。\n\n"
        )
    else:  # strict
        creativity_block = (
            "【完全客观 · 严格模式】\n"
            "所有数据、人名、产品名、机构名、时间节点必须能在资料中找到出处，零编造容忍。\n"
            "关键判断后面带溯源标记（如「[资料 1]」「(见 XX.pdf)」）。\n"
            "**不允许**文学修辞、隐喻、戏谑、夸张句式——句式严谨保守。\n"
            "如选了写作风格 skill，**风格让位于事实约束**：句式可参考但内容必须严格基于资料。\n\n"
        )

    section_instruction = (
        creativity_block +
        style_prefix +
        # R8 全局：禁止元描述
        "【全局规则 · 必须遵守】**直接给出用户要求的内容**。"
        "不要描述「你打算如何完成」、不要写「以下是我的方法论」「按以下步骤」「数据源说明 / 字段提取规则 / 待补全场景」式的元文档。"
        "用户要分析就给分析；要表格/列表/草稿就给产物；数据不足时直接说缺什么，不要写「应该建立 X 规则」式规划。\n"
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
        # ---- 排版习惯（不是框架，只是让段落能呼吸）-------------------------
        "\n排版要求 ——"
        "\n1) 本段必须自然分成 3-5 个子段落，每个子段落 150-400 字，子段落之间空一行（用两个换行 \\n\\n 分隔）。"
        "整段写成一大块文字墙是不允许的。"
        "\n2) 关键判断或对比型结论（如\"它做的是 A，不是 B\"、\"这意味着 X\"、\"这背后的逻辑是 Y\"）单独成段，"
        "让读者一眼能看到核心论点。"
        "\n3) 列举性内容（如多个项目、多类资产、多种合作方）尽量用 markdown 列表（- 开头），"
        "每条短一些，不要塞长句。"
        "\n4) 项目名（如「心灵魔法学院」「心盛计划」「繁星计划」）、关键数字（如「覆盖 30 个省」「提升 28.7%」）、"
        "关键时间节点（如「2016 年启动」「2026 年正式独立运营」）可适度用 **粗体** 标出，但不要每段都堆，"
        "整段加粗不超过 8 处。"
        "\n5) 不要使用 ## 或 ### 等 markdown 子标题；段落自然换行即可。"
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

    # R4：流式调用 + throttle partial 推送
    # - 每收到 token 就累计；每 PARTIAL_THROTTLE_MS 毫秒或每 PARTIAL_THROTTLE_CHARS
    #   字符 push 一次 on_partial，让后端把增量写到 db 让前端打字机追字
    # - 流式失败时让外层（generate_multipass_answer）的段级 retry 兜住
    PARTIAL_THROTTLE_MS = 200.0
    PARTIAL_THROTTLE_CHARS = 40
    # 深度思考心跳节流：reasoning chunks 来得很密，10s 推一次心跳足以让 watchdog 不误判
    REASONING_HEARTBEAT_MIN_INTERVAL_MS = 10000.0

    accumulated: list[str] = []
    last_push_at = time.perf_counter()
    last_push_len = 0
    last_heartbeat_at = time.perf_counter()

    def _on_stream_token(token: str) -> None:
        nonlocal last_push_at, last_push_len
        accumulated.append(token)
        if on_partial is None:
            return
        now = time.perf_counter()
        current_len = sum(len(t) for t in accumulated)
        delta_chars = current_len - last_push_len
        delta_ms = (now - last_push_at) * 1000.0
        if delta_chars < PARTIAL_THROTTLE_CHARS and delta_ms < PARTIAL_THROTTLE_MS:
            return
        last_push_at = now
        last_push_len = current_len
        current_text = "".join(accumulated)
        try:
            on_partial({
                "stageLabel": f"正在生成第 {section_index + 1}/{total_sections} 段：{section_plan.title}",
                "progress": 62.0 + (section_index / max(1, total_sections)) * 30,
                "content": current_text,
                "structured": None,
                "sectionIndex": section_index,
                "streaming": True,
            })
        except Exception:
            # partial 回调失败不能阻塞流式接收
            pass

    def _on_reasoning_heartbeat() -> None:
        """豆包 / Qwen3-thinking 等深度思考模型在 reasoning 阶段返回 reasoning_content，
        没有 content。直接忽略会让上层 watchdog（按 analysis_run.updated_at 老旧度判定）
        在思考超过阈值时误判 LLM "卡住"。这里节流推一个 heartbeat partial，让 push_partial_analysis
        刷新 analysis_run.updated_at，但不覆盖 db.content。"""
        nonlocal last_heartbeat_at
        if on_partial is None:
            return
        now = time.perf_counter()
        if (now - last_heartbeat_at) * 1000.0 < REASONING_HEARTBEAT_MIN_INTERVAL_MS:
            return
        last_heartbeat_at = now
        try:
            on_partial({
                "stageLabel": f"模型正在深度思考第 {section_index + 1}/{total_sections} 段：{section_plan.title}",
                "progress": 60.0 + (section_index / max(1, total_sections)) * 30,
                "content": "",  # heartbeat 不带新内容
                "structured": None,
                "sectionIndex": section_index,
                "streaming": True,
                "heartbeat": True,
            })
        except Exception:
            pass

    try:
        text = ai_service._qwen_generate_streaming(  # noqa: SLF001
            prompt=user_prompt,
            system_instruction=section_instruction,
            on_token=_on_stream_token,
            on_reasoning_heartbeat=_on_reasoning_heartbeat,
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

    # 流结束后再推一次最终内容，确保前端拿到完整段
    if on_partial is not None and accumulated:
        try:
            on_partial({
                "stageLabel": f"完成第 {section_index + 1}/{total_sections} 段：{section_plan.title}",
                "progress": 62.0 + ((section_index + 1) / max(1, total_sections)) * 30,
                "content": "".join(accumulated),
                "structured": None,
                "sectionIndex": section_index,
                "streaming": False,
            })
        except Exception:
            pass

    result_text = str(text or "").strip()
    if not result_text:
        raise RuntimeError(f"Pass2 第 {section_index + 1} 段返回为空")
    logger.info(
        "[multipass] section %d/%d generated (streaming) in %.2fs (%d chars)",
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
    strategic_pack: str = "",
    writing_skill_md: str = "",
    creativity_mode: str = "strict",
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

    # R7.10: creative 档完全清空所有客户资料喂入 —— Pass 1 也不能看到 strategic_pack /
    # background_pack / evidence_summary，否则大纲会包含客户专有名词（如"繁星计划"），
    # 然后 Pass 2 即使不再喂客户资料也会基于 hints 编造客户专属内容。
    if creativity_mode == "creative":
        background_pack = ""
        evidence_summary = ""
        strategic_pack = ""
        full_context = ""

    # Pass 1
    llm_attempt_count += 1
    outline = plan_workspace_answer_outline(
        question=question,
        background_pack=background_pack,
        evidence_summary=evidence_summary,
        ai_service=ai_service,
        strategic_pack=strategic_pack,
        max_sections=max_sections,
    )
    if on_outline_ready is not None:
        on_outline_ready(outline)

    sections_to_generate = outline.sections
    section_texts: list[str] = []
    failure_stage: str | None = None

    # 段级 retry：豆包等 API 偶发 SSL EOF / 网络抖动会让 _qwen_generate 抛错。
    # 每段最多重试 2 次（共调用 3 次）避免单次抖动让整个 multipass 失败 fallback 到老链路。
    section_max_retries = 2

    # Pass 2 也需要看到战略素材作为"前置高亮"，不让它淹没在 full_context 大段原始资料里。
    # 拼到 full_context 头部，明确包一层 STRATEGIC tag 方便模型聚焦。
    # R7：creative 档完全不喂客户资料
    if creativity_mode == "creative":
        effective_full_context = ""
    else:
        effective_full_context = full_context or ""
        if (strategic_pack or "").strip():
            effective_full_context = (
                "【战略素材摘要（已在 Pass 1 用于规划角度，本段写作时也要扎进这些判断）】\n"
                f"{strategic_pack.strip()}\n\n"
                "【原始背景与证据原文】\n"
                f"{full_context or ''}"
            )

    for index, plan in enumerate(sections_to_generate):
        if on_section_started is not None:
            on_section_started(index, plan)
        section_text: str | None = None
        last_exc: Exception | None = None
        for attempt in range(section_max_retries + 1):
            try:
                llm_attempt_count += 1
                section_text = generate_workspace_answer_section(
                    question=question,
                    section_plan=plan,
                    section_index=index,
                    total_sections=len(sections_to_generate),
                    headline=outline.headline,
                    judgment_line=outline.judgment_line,
                    full_context=effective_full_context,
                    previous_section_recaps=section_texts,
                    ai_service=ai_service,
                    on_partial=(lambda partial, _idx=index: on_section_partial(_idx, partial))
                    if on_section_partial is not None else None,
                    max_tokens=section_max_tokens,
                    writing_skill_md=writing_skill_md,
                    creativity_mode=creativity_mode,
                )
                break  # 成功
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "[multipass] section %d attempt %d/%d failed: %s",
                    index + 1, attempt + 1, section_max_retries + 1, exc,
                )
                if attempt < section_max_retries:
                    # 简单退避（1.5s, 3s）让对端 SSL 恢复
                    time.sleep(1.5 * (attempt + 1))
        if section_text is None:
            logger.warning(
                "[multipass] section %d exhausted retries: %s",
                index + 1, last_exc, exc_info=last_exc,
            )
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
