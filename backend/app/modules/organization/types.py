"""organization 模块类型 · frozen dataclass(不可变,符合 v2.1 原则)"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Organization:
    id: str
    name: str
    slug: str = ""
    cloud_updated_at: str = ""
    synced_from_cloud_at: str = ""


@dataclass(frozen=True)
class Department:
    id: str
    organization_id: str
    name: str
    color: str = ""
    leader_user_id: str | None = None
    leader_name: str = ""
    parent_department_id: str | None = None
    active: bool = True
    cloud_updated_at: str = ""
    synced_from_cloud_at: str = ""


@dataclass(frozen=True)
class User:
    id: str
    organization_id: str
    department_id: str | None
    full_name: str
    email: str = ""
    primary_role: str = ""
    account_status: str = ""
    membership_status: str = ""
    is_department_lead: bool = False
    is_manager: bool = False
    manager_user_id: str | None = None
    task_edit_scope: str = "self"  # self | department | organization
    can_approve_tasks: bool = False
    can_reassign_tasks: bool = False
    can_change_deadline: bool = False
    project_role_labels: tuple[str, ...] = field(default_factory=tuple)
    avatar_url: str = ""
    cloud_updated_at: str = ""
    synced_from_cloud_at: str = ""
