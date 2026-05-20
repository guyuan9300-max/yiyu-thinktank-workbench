"""Editor AI Prompt Composer.

把 OperationConfig + 召回的 RetrievedContext + 用户输入拼成最终 (system, prompt)。
所有"创意模式注入"、"风格档案注入"、"内容截断"、"温度选择"集中在这里，
endpoint 不再处理这些细节。
"""
from __future__ import annotations

from dataclasses import dataclass

from .contexts import RetrievedContext, SourceRef
from .operations import (
    CREATIVITY_HINTS,
    FAITHFUL_TEMPERATURE,
    TEMPERATURE_BY_CREATIVITY,
    OperationConfig,
)

CONTENT_SOFT_LIMIT = 12000  # 与旧实现保持一致


@dataclass(frozen=True)
class PromptComposition:
    """compose_prompt 的产物。"""
    system: str
    prompt: str
    temperature: float
    effective_creativity: str
    sources: list[SourceRef]
    # P14a：实际作用范围。"selection" = 模型只看选区；"full_doc" = 模型看整篇。
    # 前端根据这个值决定结果应用方式（替换选区 vs 替换整篇）。
    target_scope: str = "full_doc"


def compose_prompt(
    op: OperationConfig,
    *,
    content: str,
    selection_text: str = "",
    user_request: str = "",
    skill_md: str = "",
    creativity: str = "balanced",
    contexts: list[RetrievedContext] | None = None,
) -> PromptComposition:
    """组装 (system, prompt)，并决定 temperature / effective_creativity / target_scope。

    P14a：当 selection_text 非空且 op 提供了 user_prefix_selection 时，模型只看选区；
          否则退回老行为——模型看 content（整篇文档）。

    参数：
        op: 当前要执行的 operation 配置。
        content: 整篇文档 markdown。selection_text 为空时作为模型输入；
                 非空时它是"全文上下文"，但本期不注入。
        selection_text: 用户选区内容（来自 window.getSelection().toString()）。
                        非空 + op 支持选区 → 模型只看这段。
        user_request: 用户在 AI 输入框写的具体要求（可为空）。
        skill_md: 写作风格 skill 的 distilled_md（可为空）。
        creativity: 用户选择的 creativityMode。op.faithful=True 时此值被忽略。
        contexts: 召回到的资料块；compose 把它们拼到 prompt 前部。

    返回 PromptComposition：含 system / prompt / temperature / effective_creativity /
    sources / target_scope。
    """
    # 1) 解析 effective creativity & temperature
    effective_creativity = "strict" if op.faithful else creativity
    if op.faithful:
        temperature = FAITHFUL_TEMPERATURE
    else:
        temperature = TEMPERATURE_BY_CREATIVITY.get(effective_creativity, 0.4)

    # 2) system = op.system + creativity hint
    hint = CREATIVITY_HINTS.get(effective_creativity, "")
    full_system = op.system + (("\n\n" + hint) if hint else "")

    # 3) 决定作用范围 + prefix + 主体内容
    selection_clean = (selection_text or "").strip()
    if selection_clean and op.user_prefix_selection:
        target_scope = "selection"
        effective_body = selection_clean
        effective_prefix = op.user_prefix_selection
    else:
        target_scope = "full_doc"
        effective_body = content
        effective_prefix = op.user_prefix

    # 4) 拼 prefix（用户要求 + 风格档案 + 召回资料块）
    prefix_parts: list[str] = []
    sources: list[SourceRef] = []

    if user_request:
        prefix_parts.append(f"【用户具体要求】\n{user_request}\n")
    if skill_md:
        prefix_parts.append(f"【写作风格档案（请按此风格调整措辞与节奏）】\n{skill_md}\n")

    for ctx in contexts or []:
        if not ctx.chunks:
            continue
        body_parts: list[str] = []
        for idx, chunk in enumerate(ctx.chunks, 1):
            body_parts.append(f"[{idx}] {chunk.text}")
            sources.append(chunk.source_ref)
        prefix_parts.append(f"【{ctx.label}】\n" + "\n\n".join(body_parts) + "\n")

    custom_prefix = ("\n".join(prefix_parts) + "\n") if prefix_parts else ""

    # 5) 内容软上限截断（选区/整篇统一处理）
    truncated = effective_body
    if len(truncated) > CONTENT_SOFT_LIMIT:
        truncated = truncated[:CONTENT_SOFT_LIMIT] + "\n\n（内容过长已截断，仅处理前 12000 字）"

    # 6) 拼最终 prompt
    prompt = custom_prefix + effective_prefix + truncated

    return PromptComposition(
        system=full_system,
        prompt=prompt,
        temperature=temperature,
        effective_creativity=effective_creativity,
        sources=sources,
        target_scope=target_scope,
    )
