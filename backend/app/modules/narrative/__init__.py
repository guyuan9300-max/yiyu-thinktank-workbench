"""narrative 模块 · 叙事生成/事件线(骨架占位)

W2:模块结构 + 占位
W5 完整实施 — 91 处 SQL,event_line 6 张表,历史 bug 高发(冷冻孤儿/orphan 等)

对外接口(占位):
"""
from .repository import NarrativeRepository, get_narrative_repository

__all__ = ["NarrativeRepository", "get_narrative_repository"]
