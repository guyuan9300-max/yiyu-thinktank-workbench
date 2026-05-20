"""益语智库 inline 文档编辑器 AI 服务。

把"操作 = 动词"（operations）和"资料 = 名词"（contexts）解耦：
- operations.py：每种 AI 动词的 system / user prefix / 温度 / 是否 faithful 等配置
- contexts.py：每种资料源（客户资料库 / 战略锚点 / 事件线）的召回逻辑
- composer.py：把 op + contexts + 用户输入拼成最终 prompt

公开 API 通过 run_document_ai_action 调用。
"""
from .composer import PromptComposition, compose_prompt
from .contexts import (
    ContextChunk,
    ContextSourceSpec,
    SourceRef,
    retrieve_contexts,
)
from .operations import OPERATIONS, OperationConfig, OperationKey

__all__ = [
    "PromptComposition",
    "compose_prompt",
    "ContextChunk",
    "ContextSourceSpec",
    "SourceRef",
    "retrieve_contexts",
    "OPERATIONS",
    "OperationConfig",
    "OperationKey",
]
