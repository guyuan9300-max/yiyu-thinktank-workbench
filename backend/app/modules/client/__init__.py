"""client 模块 · 客户/项目数据(骨架占位)

W2:模块结构 + 接口骨架
W3 完整实施 — 已有大量 SQL(~118 处)在 main.py 待迁移

对外接口(占位):
"""
from .repository import ClientRepository, get_client_repository

__all__ = ["ClientRepository", "get_client_repository"]
