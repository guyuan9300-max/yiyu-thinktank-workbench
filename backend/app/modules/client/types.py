"""client 模块对外类型 — 镜像 cloud_backend ClientRecord shape

Phase 1 F1.1 产出。给 L2 ClientFactView (F1.2) + ClientScopeFilter (F1.3) 使用。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


# ── 状态枚举 ───────────────────────────────────────────────
ClientStage = Literal[
    "lead",
    "discovery",
    "active",
    "paused",
    "frozen",
    "archived",
    "lost",
]
"""客户阶段。
- lead/discovery/active: 正常推进
- paused: 暂停
- frozen: 同步冻结 (多账号同步时本地此状态不被云端覆盖, 修 v1.0 frozen_at bug 的关键)
- archived: 归档 (仍可读, 默认列表隐藏)
- lost: 失败 (业务终止)
"""


@dataclass(frozen=True)
class ClientRecord:
    """对外的客户记录类型 — 与 clients 表行结构对齐。

    immutable, 业务代码不能直接修改, 通过 ClientRepository.update() 改。
    """

    id: str
    name: str
    alias: str
    domain: str
    type: str
    intro: str
    stage: ClientStage
    color: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ClientCreatePayload:
    """创建客户的输入 payload"""

    name: str
    alias: str = ""
    domain: str = ""
    type: str = ""
    intro: str = ""
    stage: ClientStage = "lead"
    color: str = "#5B7BFE"


@dataclass(frozen=True)
class ClientUpdatePayload:
    """部分更新 — 所有字段都是 optional, None 表示不改"""

    name: str | None = None
    alias: str | None = None
    domain: str | None = None
    type: str | None = None
    intro: str | None = None
    stage: ClientStage | None = None
    color: str | None = None
