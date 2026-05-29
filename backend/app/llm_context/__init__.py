"""llm_context 模块 · v2.1 Karpathy 一等公民

铁律:
- 所有给 LLM 的 prompt 都走 ContextComposer
- 所有 LLM 调用结果都走 PromptLogger 持久化
- ContextInspector 用于 debug + 数据驱动改进

不需要全局立即切换:Week 2 雏形,Week 3-4 逐步接入。

对外接口:
- compose_context(db, client_id, intent) → LLMContext
- log_prompt(db, ...) → 写入 prompt_log
- inspect_recent_prompts(db, n=10) → 最近 n 条
"""

from .schema import SCHEMA_SQL, LLM_CONTEXT_SCHEMA_VERSION
from .types import LLMContext, PromptIntent, PromptLogEntry
from .composer import ContextComposer, compose_context
from .prompt_logger import PromptLogger, log_prompt
from .inspector import ContextInspector, inspect_recent_prompts

__all__ = [
    "SCHEMA_SQL",
    "LLM_CONTEXT_SCHEMA_VERSION",
    "LLMContext",
    "PromptIntent",
    "PromptLogEntry",
    "ContextComposer",
    "compose_context",
    "PromptLogger",
    "log_prompt",
    "ContextInspector",
    "inspect_recent_prompts",
]
