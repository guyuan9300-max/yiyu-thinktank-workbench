"""task 模块 · 任务数据(骨架占位)

W2:模块结构 + 占位接口
W3-4 完整实施 — 最重(~152 处 SQL),需深度重构

对外接口(占位):
"""
from .repository import TaskRepository, get_task_repository

__all__ = ["TaskRepository", "get_task_repository"]
