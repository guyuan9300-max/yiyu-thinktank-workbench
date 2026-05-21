"""client 模块 · L2 客户共识层 (Phase 1)

服务: V2.2_NORTH_STAR.md 目标 A (现有功能不掉链) + 目标 B (机器人能拿全数据)

对外接口:

F1.1 (commit 010fe20):
- ClientRepository / get_client_repository: CRUD + 状态唯一真相
- ClientRecord / ClientCreatePayload / ClientUpdatePayload: 不可变数据类型
- ClientStage: 状态枚举

F1.2 (新增):
- ClientFactView / get_client_fact_view: L2 共识层核心, 聚合 6 表事实
- ClientFactBundle: 完整事实包 (client + event_lines + tasks + commitments
  + dna_documents + atomic_facts + key_decisions[Phase 2])
- EventLineFact / TaskFact / CommitmentFact / DnaDocumentRef / AtomicFactRef:
  子事实 dataclass
- FactChangedCallback: 事件通知 (为 Phase 3 NarrativeKernel 准备)

下游待接入 (后续 feature):
- F1.3 ClientScopeFilter (依赖本模块 can_write / is_frozen)
- F1.4 main.py top 50 处 client_id 查询切迁
- F1.5 前端 useClientFact hook (依赖 ClientFactBundle shape)
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
]
