"""client 模块 · 客户数据唯一读写入口 (Phase 1 F1.1 完整实现)

服务: V2.2_NORTH_STAR.md 目标 A (现有功能不掉链) + 目标 B (机器人能拿全数据)

对外接口:
- ClientRepository / get_client_repository: CRUD + 状态唯一真相
- ClientRecord / ClientCreatePayload / ClientUpdatePayload: 不可变数据类型
- ClientStage: 状态枚举

下游消费者 (待 F1.2/F1.3/F1.4 接入):
- ClientFactView (F1.2): 一个客户全部事实的聚合视图
- ClientScopeFilter (F1.3): 所有 client_id 查询的统一过滤
- main.py top 50 处 client_id 查询切迁 (F1.4)
"""
from .repository import ClientRepository, get_client_repository
from .types import (
    ClientCreatePayload,
    ClientRecord,
    ClientStage,
    ClientUpdatePayload,
)

__all__ = [
    "ClientRepository",
    "get_client_repository",
    "ClientRecord",
    "ClientCreatePayload",
    "ClientUpdatePayload",
    "ClientStage",
]
