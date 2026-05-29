"""益语智库 inline 文档编辑器 AI 服务。

Step 4 重构后,inline AI 不再有独立的召回 / prompt 组装链路 —
所有 RAG + grounded 验证 + 防幻觉约束都走 chat 主链路
(resolve_chat_answer_data_center_primary 的 assistant_id=None 旁路调用)。

editor_ai 模块现在只保留:
- operations.py:每种 AI 动词的配置(label / system / user_prefix / faithful 等)
  和 creativity 模式映射

老的 contexts.py(5 个 P13a 空 stub retrievers)和 composer.py(prompt 组装)
已删除 — 它们的功能被 chat 主链路完整接管。
"""
from .operations import (
    CREATIVITY_HINTS,
    FAITHFUL_TEMPERATURE,
    OPERATIONS,
    TEMPERATURE_BY_CREATIVITY,
    OperationConfig,
    OperationKey,
)

__all__ = [
    "CREATIVITY_HINTS",
    "FAITHFUL_TEMPERATURE",
    "OPERATIONS",
    "TEMPERATURE_BY_CREATIVITY",
    "OperationConfig",
    "OperationKey",
]
