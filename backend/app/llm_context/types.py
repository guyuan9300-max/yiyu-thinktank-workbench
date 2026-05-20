"""llm_context 类型 · frozen dataclass

LLMContext 是 ContextComposer 返回的 prompt 装配产物。
PromptLogEntry 是 prompt_log 表的 row 对应类型。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# 当前支持的 intent(Week 2 雏形只先支持 narrative,其他逐周加)
PromptIntent = Literal[
    "narrative",            # 客户叙事生成
    "qa",                   # 对话问答
    "intelligence_query",   # 情报检索/分析
    "task_brief",           # 任务简报
    "test_intent",          # 测试用
]


@dataclass(frozen=True)
class LLMContext:
    """ContextComposer 装配出来的完整 LLM 上下文"""

    intent: str
    client_id: str | None
    user_id: str | None

    # 装配出来的 prompt 三段
    system_text: str
    prompt_text: str

    # 元数据(用于 PromptLogger 自动记录 + 调试)
    sections_included: tuple[str, ...]   # 哪些 section 被装进 prompt(如 'persons','events','tasks')
    token_estimate: int                   # 粗略 token 估算(text 长度 / 3)
    truncated: bool                       # 是否触发了 max_tokens 裁剪
    composed_at: str                      # ISO timestamp


@dataclass(frozen=True)
class PromptLogEntry:
    """对应 prompt_log 一行"""

    id: str
    intent: str
    client_id: str | None
    user_id: str | None
    system_text: str
    prompt_text: str
    output_text: str
    duration_ms: float
    tokens_used: int
    model_id: str
    error: str
    score: float | None
    score_note: str
    metadata: dict
    created_at: str
