"""client 模块 · L2 客户共识层 (Phase 1)

服务: V2.2_NORTH_STAR.md 目标 A (现有功能不掉链) + 目标 B (机器人能拿全数据)

对外接口 (Phase 1 三件套):

F1.1 (commit 010fe20):
- ClientRepository / get_client_repository: CRUD + 状态唯一真相
- ClientRecord / ClientCreatePayload / ClientUpdatePayload: 不可变数据类型
- ClientStage: 状态枚举

F1.2 (commit a1f214c):
- ClientFactView / get_client_fact_view: L2 共识层核心, 聚合 6 表事实
- ClientFactBundle: 完整事实包
- EventLineFact / TaskFact / CommitmentFact / DnaDocumentRef / AtomicFactRef
- FactChangedCallback: 事件通知

F1.3 (新增):
- ClientScopeFilter / get_client_scope_filter: client_id 写入路径统一守门
- ScopeFilterError: 写入被拦截异常
- REASON_NOT_FOUND / REASON_FROZEN / REASON_ARCHIVED / REASON_LOST: 异常 reason 常量

下游待接入 (后续 feature):
- F1.4 main.py top 50 处 client_id 查询切迁 (写入前调 ScopeFilter.assert_writable)
- F1.5 前端 useClientFact hook
- F1.6 5 个 view 接入
- F1.7 client_stage_audit 表 + freeze() reason 持久化
"""
from .facts import (
    AtomicFactRef,
    ClientFactBundle,
    CommitmentFact,
    DnaDocumentRef,
    EventLineFact,
    TaskFact,
)
from .fact_view import (
    ClientFactView,
    FactChangedCallback,
    get_client_fact_view,
)
from .repository import ClientRepository, get_client_repository
from .scope_filter import (
    REASON_ARCHIVED,
    REASON_FROZEN,
    REASON_LOST,
    REASON_NOT_FOUND,
    ClientScopeFilter,
    ScopeFilterError,
    get_client_scope_filter,
)
from .types import (
    ClientCreatePayload,
    ClientRecord,
    ClientStage,
    ClientUpdatePayload,
)

__all__ = [
    # F1.1
    "ClientRepository",
    "get_client_repository",
    "ClientRecord",
    "ClientCreatePayload",
    "ClientUpdatePayload",
    "ClientStage",
    # F1.2
    "ClientFactView",
    "get_client_fact_view",
    "FactChangedCallback",
    "ClientFactBundle",
    "EventLineFact",
    "TaskFact",
    "CommitmentFact",
    "DnaDocumentRef",
    "AtomicFactRef",
    # F1.3
    "ClientScopeFilter",
    "get_client_scope_filter",
    "ScopeFilterError",
    "REASON_NOT_FOUND",
    "REASON_FROZEN",
    "REASON_ARCHIVED",
    "REASON_LOST",
]
