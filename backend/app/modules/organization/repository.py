"""organization 模块 · OrganizationDirectory(SSOT 统一 getter)

v2.1 铁律:所有读部门 / 员工 / 客户同事关联的代码,**只能**通过这个 directory,
不能直接 SQL,不能硬编码部门 id。

用法:
    from app.modules.organization import get_organization_directory

    directory = get_organization_directory(db)
    dept = directory.get_department_by_id("department_gq160gdz")
    if dept and dept.active:
        ...

    # 获取一个 client 的可见同事
    users = directory.list_users_visible_for_client("client_a")

设计:
- 完全只读(读 mirror_* 表,不写)
- 不缓存(SQLite 已经够快 + sync 后看到最新数据)
- 容错:数据缺失返回 None / []
- frozen dataclass 返回(immutable,跨线程安全)
"""
from __future__ import annotations

import json
from typing import Any

from .types import Department, Organization, User


class OrganizationDirectory:
    """SSOT 统一 getter · 所有部门 / 员工读取的唯一入口"""

    def __init__(self, db: Any):
        self._db = db

    # ─────────────────────────────────────────────────────────────────────
    # Organization
    # ─────────────────────────────────────────────────────────────────────

    def get_organization(self, organization_id: str | None = None) -> Organization | None:
        """获取组织 · 不传 id 返回默认(本地通常只有 1 个)"""
        if organization_id:
            row = self._db.fetchone(
                "SELECT * FROM mirror_organizations WHERE id = ?", (organization_id,)
            )
        else:
            row = self._db.fetchone("SELECT * FROM mirror_organizations LIMIT 1")
        return _row_to_organization(row) if row else None

    def list_organizations(self) -> list[Organization]:
        rows = self._db.fetchall("SELECT * FROM mirror_organizations ORDER BY name")
        return [_row_to_organization(r) for r in rows]

    # ─────────────────────────────────────────────────────────────────────
    # Department
    # ─────────────────────────────────────────────────────────────────────

    def get_department_by_id(self, department_id: str) -> Department | None:
        if not department_id:
            return None
        row = self._db.fetchone(
            "SELECT * FROM mirror_departments WHERE id = ?", (department_id,)
        )
        return _row_to_department(row) if row else None

    def list_active_departments(self, organization_id: str | None = None) -> list[Department]:
        if organization_id:
            rows = self._db.fetchall(
                "SELECT * FROM mirror_departments WHERE organization_id = ? AND active = 1 ORDER BY name",
                (organization_id,),
            )
        else:
            rows = self._db.fetchall(
                "SELECT * FROM mirror_departments WHERE active = 1 ORDER BY name"
            )
        return [_row_to_department(r) for r in rows]

    def list_all_departments(self, organization_id: str | None = None) -> list[Department]:
        """包括 inactive(管理界面用)"""
        if organization_id:
            rows = self._db.fetchall(
                "SELECT * FROM mirror_departments WHERE organization_id = ? ORDER BY active DESC, name",
                (organization_id,),
            )
        else:
            rows = self._db.fetchall(
                "SELECT * FROM mirror_departments ORDER BY active DESC, name"
            )
        return [_row_to_department(r) for r in rows]

    def get_department_leader(self, department_id: str) -> User | None:
        """部门负责人(从 mirror_users 拿,不只看 mirror_departments.leader_user_id 字段)"""
        dept = self.get_department_by_id(department_id)
        if not dept or not dept.leader_user_id:
            return None
        return self.get_user_by_id(dept.leader_user_id)

    # ─────────────────────────────────────────────────────────────────────
    # User
    # ─────────────────────────────────────────────────────────────────────

    def get_user_by_id(self, user_id: str) -> User | None:
        # [B] 5/25 PM (顾源源 path C): 用 org_members_v 让人 + bot 统一可查.
        # 前端可能传 bot actor_id (bot_60ab0ec2b071) 查"成员资料", view 也命中.
        if not user_id:
            return None
        row = self._db.fetchone(
            "SELECT * FROM org_members_v WHERE id = ?", (user_id,)
        )
        return _row_to_user(row) if row else None

    def list_users(
        self,
        *,
        organization_id: str | None = None,
        department_id: str | None = None,
        account_status: str | None = "approved",
    ) -> list[User]:
        # [B] 5/25 PM (顾源源 path C): 列组织成员 → 走 view (含 bot).
        # 战略发展部部门复盘看的成员名单从这里来 — 机器人庆华会被列入.
        clauses = []
        params: list[Any] = []
        if organization_id:
            clauses.append("organization_id = ?")
            params.append(organization_id)
        if department_id:
            clauses.append("department_id = ?")
            params.append(department_id)
        if account_status:
            clauses.append("account_status = ?")
            params.append(account_status)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self._db.fetchall(
            f"SELECT * FROM org_members_v{where} ORDER BY full_name",
            tuple(params),
        )
        return [_row_to_user(r) for r in rows]

    def list_department_leaders(self, organization_id: str | None = None) -> list[User]:
        """所有部门负责人。管理层头衔属于组织级可见范围, 不再混入部门负责人。"""
        if organization_id:
            rows = self._db.fetchall(
                """
                SELECT * FROM mirror_users
                WHERE organization_id = ?
                  AND is_department_lead = 1
                  AND account_status = 'approved'
                ORDER BY full_name
                """,
                (organization_id,),
            )
        else:
            rows = self._db.fetchall(
                """
                SELECT * FROM mirror_users
                WHERE is_department_lead = 1
                  AND account_status = 'approved'
                ORDER BY full_name
                """
            )
        return [_row_to_user(r) for r in rows]

    # ─────────────────────────────────────────────────────────────────────
    # Client ↔ User 关联(项目同事)
    # ─────────────────────────────────────────────────────────────────────

    def list_users_visible_for_client(self, client_id: str) -> list[User]:
        """某个客户的所有"项目同事"(可见者).

        [B] 5/25 PM (path C): 客户协同视图改 view, 让 bot 也能在协同名单显示.
        但 mirror_client_related_users 表只存 user 关联, bot 不在 JOIN 命中,
        除非有专门 bot ↔ client 关联表 (P1).
        """
        if not client_id:
            return []
        rows = self._db.fetchall(
            """
            SELECT u.* FROM org_members_v u
            JOIN mirror_client_related_users cru ON cru.user_id = u.id
            WHERE cru.client_id = ?
              AND u.account_status = 'approved'
            ORDER BY cru.order_index, u.full_name
            """,
            (client_id,),
        )
        return [_row_to_user(r) for r in rows]

    def list_clients_visible_for_user(self, user_id: str) -> list[str]:
        """某个用户能看见的所有客户 id 列表"""
        if not user_id:
            return []
        rows = self._db.fetchall(
            """
            SELECT DISTINCT client_id FROM mirror_client_related_users
            WHERE user_id = ?
            ORDER BY client_id
            """,
            (user_id,),
        )
        return [str(r["client_id"]) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# 行 → dataclass 转换
# ─────────────────────────────────────────────────────────────────────────────


def _row_to_organization(row) -> Organization:
    return Organization(
        id=str(row["id"]),
        name=str(row["name"] or ""),
        slug=str(row["slug"] or ""),
        cloud_updated_at=str(row["cloud_updated_at"] or ""),
        synced_from_cloud_at=str(row["synced_from_cloud_at"] or ""),
    )


def _row_to_department(row) -> Department:
    return Department(
        id=str(row["id"]),
        organization_id=str(row["organization_id"] or ""),
        name=str(row["name"] or ""),
        color=str(row["color"] or ""),
        leader_user_id=str(row["leader_user_id"]) if row["leader_user_id"] else None,
        leader_name=str(row["leader_name"] or ""),
        parent_department_id=str(row["parent_department_id"]) if row["parent_department_id"] else None,
        active=bool(row["active"]),
        cloud_updated_at=str(row["cloud_updated_at"] or ""),
        synced_from_cloud_at=str(row["synced_from_cloud_at"] or ""),
    )


def _row_to_user(row) -> User:
    raw_labels = row["project_role_labels_json"] or "[]"
    try:
        labels = json.loads(raw_labels)
    except json.JSONDecodeError:
        labels = []
    if not isinstance(labels, list):
        labels = []
    return User(
        id=str(row["id"]),
        organization_id=str(row["organization_id"] or ""),
        department_id=str(row["department_id"]) if row["department_id"] else None,
        full_name=str(row["full_name"] or ""),
        email=str(row["email"] or ""),
        primary_role=str(row["primary_role"] or ""),
        account_status=str(row["account_status"] or ""),
        membership_status=str(row["membership_status"] or ""),
        is_department_lead=bool(row["is_department_lead"]),
        is_manager=bool(row["is_manager"]),
        visibility_scope=str(row["visibility_scope"] or "self"),
        management_title_id=str(row["management_title_id"]) if row["management_title_id"] else None,
        management_title_name=str(row["management_title_name"]) if row["management_title_name"] else None,
        manager_user_id=str(row["manager_user_id"]) if row["manager_user_id"] else None,
        task_edit_scope=str(row["task_edit_scope"] or "self"),
        can_approve_tasks=bool(row["can_approve_tasks"]),
        can_reassign_tasks=bool(row["can_reassign_tasks"]),
        can_change_deadline=bool(row["can_change_deadline"]),
        project_role_labels=tuple(str(x) for x in labels),
        avatar_url=str(row["avatar_url"] or ""),
        cloud_updated_at=str(row["cloud_updated_at"] or ""),
        synced_from_cloud_at=str(row["synced_from_cloud_at"] or ""),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 单例工厂(避免每次 import 都 new 一个 OrganizationDirectory)
# ─────────────────────────────────────────────────────────────────────────────


def get_organization_directory(db: Any) -> OrganizationDirectory:
    """获取 directory 实例 · 跟 db 一对一"""
    return OrganizationDirectory(db)
