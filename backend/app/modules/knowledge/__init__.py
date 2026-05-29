"""knowledge 模块 · 知识库/实体/事实(骨架占位)

W2:模块结构 + 占位接口
W4 完整实施 — v1/v2 双模型并存,迁移风险高

对外接口(占位):
"""
from .repository import KnowledgeRepository, get_knowledge_repository

__all__ = ["KnowledgeRepository", "get_knowledge_repository"]
