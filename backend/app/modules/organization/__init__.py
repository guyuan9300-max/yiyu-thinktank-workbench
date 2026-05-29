"""organization 模块 · v2.1 SSOT 落地点

铁律:
- 部门 / 员工 / 组织定义的唯一真相源 = 火山云 cloud_backend
- 本地这 4 张 mirror 表只读缓存(synced_from_cloud_at 标记新鲜度)
- 业务代码禁止直接写这 4 张表,只能通过 sync 程序写
- 部门 id / 部门名等所有读取走 OrganizationDirectory getter,禁止硬编码

对外只 export Repository + 类型,不暴露内部 SQL。
"""

from .schema import (
    SCHEMA_SQL,
    MIRROR_TABLE_NAMES,
    ORGANIZATION_SCHEMA_VERSION,
)
from .views import VIEWS_SQL, VIEW_NAMES
from .sync import (
    SyncReport,
    SyncTableReport,
    sync_organization_directory,
)
from .types import Organization, Department, User
from .repository import (
    OrganizationDirectory,
    get_organization_directory,
)

__all__ = [
    # schema
    "SCHEMA_SQL",
    "MIRROR_TABLE_NAMES",
    "ORGANIZATION_SCHEMA_VERSION",
    # views
    "VIEWS_SQL",
    "VIEW_NAMES",
    # sync
    "SyncReport",
    "SyncTableReport",
    "sync_organization_directory",
    # types
    "Organization",
    "Department",
    "User",
    # repository (SSOT getter)
    "OrganizationDirectory",
    "get_organization_directory",
]
