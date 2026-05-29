"""W1-3 验证 · OrganizationDirectory(SSOT getter)

跑法:
    backend/.venv/bin/python3 -m pytest tests/test_organization_directory.py -v

设计:
- fixture:跑 mock sync 填充 mirror 表,然后用 directory 查
- 验证所有 getter 返回正确的 dataclass
- 验证容错:不存在的 id 返回 None / []
- 验证 immutability(frozen dataclass)
"""
from __future__ import annotations

import json
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.db import Database  # noqa: E402
from app.modules.organization import (  # noqa: E402
    Department,
    Organization,
    User,
    get_organization_directory,
    sync_organization_directory,
)


# ── Fixtures(复用 sync 测试的真实样本数据)──


def _profile():
    return {
        "organization": {"organizationId": "org_yiyu_default", "name": "示例工作台",
                         "slug": "yiyu", "updatedAt": "2026-05-19T07:11:27"},
        "departments": [
            {"id": "department_gq160gdz", "name": "战略发展部", "color": "#5B7BFE",
             "leaderUserId": "user_admin_demo", "leaderName": "管理员甲", "active": True,
             "updatedAt": "2026-05-19T07:11:27"},
            {"id": "department_b3zvoei7", "name": "合作发展部", "color": "#14B8A6",
             "leaderUserId": "emp_efdd076c31", "leaderName": "乐乐", "active": True,
             "updatedAt": "2026-05-19T07:11:27"},
            {"id": "department_sufbu60r", "name": "技术创新部", "color": "#0EA5E9",
             "leaderUserId": "emp_ebf2ea94ed", "leaderName": "成员乙", "active": True,
             "updatedAt": "2026-05-19T07:11:27"},
            {"id": "dept_info_data", "name": "信息数据部(已停用)", "color": "",
             "leaderUserId": None, "leaderName": "", "active": False,
             "updatedAt": "2026-05-19T07:11:27"},
        ],
        "bindings": [
            {"userId": "user_admin_demo", "departmentId": "department_gq160gdz",
             "isManager": True, "taskEditScope": "department",
             "canApproveTasks": True, "canReassignTasks": True, "canChangeDeadline": True,
             "projectRoleLabels": ["CEO"]},
            {"userId": "emp_efdd076c31", "departmentId": "department_b3zvoei7",
             "isManager": True, "managerUserId": "user_admin_demo", "taskEditScope": "self",
             "projectRoleLabels": ["合作总监"]},
            {"userId": "emp_ebf2ea94ed", "departmentId": "department_sufbu60r",
             "isManager": True, "taskEditScope": "self"},
            {"userId": "user_admin", "departmentId": None,
             "isManager": True, "taskEditScope": "department"},
        ],
    }


def _employees():
    """混合状态员工(reviewer W3:测过滤行为不能只用 approved 用户)"""
    return [
        {"id": "user_admin_demo", "fullName": "管理员甲", "email": "admin-demo@example.org",
         "primaryRole": "admin", "accountStatus": "approved",
         "membershipStatus": "approved", "departmentId": "department_gq160gdz",
         "isDepartmentLead": True, "updatedAt": "2026-05-19T07:11:27"},
        {"id": "emp_efdd076c31", "fullName": "乐乐", "email": "member-a@example.org",
         "primaryRole": "employee", "accountStatus": "approved",
         "membershipStatus": "approved", "departmentId": "department_b3zvoei7",
         "isDepartmentLead": True, "updatedAt": "2026-05-19T07:11:27"},
        {"id": "emp_ebf2ea94ed", "fullName": "成员乙", "email": "member-b@example.org",
         "primaryRole": "employee", "accountStatus": "approved",
         "membershipStatus": "approved", "departmentId": "department_sufbu60r",
         "isDepartmentLead": True, "updatedAt": "2026-05-19T07:11:27"},
        {"id": "user_admin", "fullName": "系统管理员", "email": "admin@example.org",
         "primaryRole": "admin", "accountStatus": "approved",
         "membershipStatus": "approved", "departmentId": None,
         "isDepartmentLead": True, "updatedAt": "2026-05-19T07:11:27"},
        # pending:等审批,不应在默认 list_users() 里出现
        {"id": "emp_pending_test", "fullName": "申请中员工", "email": "p@k.org",
         "primaryRole": "employee", "accountStatus": "pending",
         "membershipStatus": "pending", "departmentId": None,
         "isDepartmentLead": False, "updatedAt": "2026-05-20T01:00:00"},
        # disabled:被禁,不应在默认 list_users() 里出现
        {"id": "emp_disabled_test", "fullName": "禁用员工", "email": "d@k.org",
         "primaryRole": "employee", "accountStatus": "disabled",
         "membershipStatus": "approved", "departmentId": "department_b3zvoei7",
         "isDepartmentLead": False, "updatedAt": "2026-05-15T10:00:00"},
    ]


def _mock_http(profile, employees):
    def http(base, path, token, **kw):
        if path == "/api/v1/settings/org-model/profile":
            return profile
        if path == "/api/v1/employees/directory":
            return employees
        raise ValueError(path)
    return http


@pytest.fixture
def directory(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    # seed clients + related_user_ids
    db.conn.execute(
        """INSERT INTO clients(id, name, alias, domain, type, intro, stage, color, created_at, updated_at, related_user_ids_json)
           VALUES('client_a', '客户A', '', '项目', '项目', '', '待导入资料', '#5B7BFE',
                  '2026-05-20', '2026-05-20', ?)""",
        (json.dumps(["user_admin_demo", "emp_efdd076c31"]),),
    )
    db.conn.execute(
        """INSERT INTO clients(id, name, alias, domain, type, intro, stage, color, created_at, updated_at, related_user_ids_json)
           VALUES('client_b', '客户B', '', '项目', '项目', '', '待导入资料', '#5B7BFE',
                  '2026-05-20', '2026-05-20', ?)""",
        (json.dumps(["user_admin_demo"]),),
    )
    db.conn.commit()

    sync_organization_directory(
        db,
        cloud_base_url="http://t", cloud_token="x",
        http_get=_mock_http(_profile(), _employees()),
        now_iso=lambda: "2026-05-20T12:00:00",
    )
    return get_organization_directory(db)


# ── Tests ──


@pytest.mark.integration
def test_get_organization(directory):
    org = directory.get_organization()
    assert isinstance(org, Organization)
    assert org.id == "org_yiyu_default"
    assert org.name == "示例工作台"


@pytest.mark.integration
def test_list_active_departments(directory):
    depts = directory.list_active_departments()
    names = [d.name for d in depts]
    # 信息数据部 active=0,不应出现
    assert "信息数据部(已停用)" not in names
    assert set(names) == {"战略发展部", "合作发展部", "技术创新部"}


@pytest.mark.integration
def test_list_all_departments_includes_inactive(directory):
    all_depts = directory.list_all_departments()
    names = [d.name for d in all_depts]
    assert "信息数据部(已停用)" in names
    assert len(all_depts) == 4


@pytest.mark.integration
def test_get_department_by_id_returns_dataclass(directory):
    dept = directory.get_department_by_id("department_gq160gdz")
    assert isinstance(dept, Department)
    assert dept.name == "战略发展部"
    assert dept.leader_user_id == "user_admin_demo"
    assert dept.active is True


@pytest.mark.integration
def test_get_department_by_id_not_found_returns_none(directory):
    assert directory.get_department_by_id("nonexistent") is None
    assert directory.get_department_by_id("") is None


@pytest.mark.integration
def test_get_user_by_id(directory):
    user = directory.get_user_by_id("user_admin_demo")
    assert isinstance(user, User)
    assert user.full_name == "管理员甲"
    assert user.is_manager is True
    assert user.task_edit_scope == "department"
    assert "CEO" in user.project_role_labels


@pytest.mark.integration
def test_get_user_by_id_not_found(directory):
    assert directory.get_user_by_id("ghost") is None


@pytest.mark.integration
def test_list_users_by_department(directory):
    users = directory.list_users(department_id="department_b3zvoei7")
    assert len(users) == 1
    assert users[0].full_name == "乐乐"


@pytest.mark.integration
def test_list_users_default_excludes_pending_and_disabled(directory):
    """默认 status='approved',pending/disabled 用户不应出现(reviewer W3)"""
    users = directory.list_users()  # 默认参数
    names = {u.full_name for u in users}
    assert "管理员甲" in names
    assert "申请中员工" not in names  # pending 被过滤
    assert "禁用员工" not in names      # disabled 被过滤
    assert len(users) == 4


@pytest.mark.integration
def test_list_users_explicit_status_filter(directory):
    """显式过滤特定 status 能拿到对应用户(reviewer W3)"""
    pending_users = directory.list_users(account_status="pending")
    assert {u.full_name for u in pending_users} == {"申请中员工"}

    disabled_users = directory.list_users(account_status="disabled")
    assert {u.full_name for u in disabled_users} == {"禁用员工"}


@pytest.mark.integration
def test_list_users_no_status_filter_returns_all(directory):
    """account_status=None 拿全部用户(reviewer W3:容易被忽略的路径)"""
    all_users = directory.list_users(account_status=None)
    assert len(all_users) == 6  # 4 approved + 1 pending + 1 disabled
    statuses = {u.account_status for u in all_users}
    assert statuses == {"approved", "pending", "disabled"}


@pytest.mark.integration
def test_get_department_leader(directory):
    leader = directory.get_department_leader("department_gq160gdz")
    assert isinstance(leader, User)
    assert leader.full_name == "管理员甲"


@pytest.mark.integration
def test_get_department_leader_for_no_leader_dept(directory):
    """信息数据部没有 leader_user_id → 返回 None"""
    leader = directory.get_department_leader("dept_info_data")
    assert leader is None


@pytest.mark.integration
def test_list_department_leaders(directory):
    """所有部门负责人 + manager 标记的人"""
    leaders = directory.list_department_leaders()
    names = {u.full_name for u in leaders}
    # 4 个人都 is_department_lead=true 或 is_manager=true
    assert names == {"管理员甲", "乐乐", "成员乙", "系统管理员"}


@pytest.mark.integration
def test_list_users_visible_for_client(directory):
    """client_a 关联了 管理员甲 + 乐乐"""
    users = directory.list_users_visible_for_client("client_a")
    names = [u.full_name for u in users]
    assert names == ["管理员甲", "乐乐"]  # 按 order_index


@pytest.mark.integration
def test_list_users_visible_for_client_empty(directory):
    """不存在的 client → []"""
    assert directory.list_users_visible_for_client("client_ghost") == []
    assert directory.list_users_visible_for_client("") == []


@pytest.mark.integration
def test_list_clients_visible_for_user(directory):
    """管理员甲能看见 client_a + client_b"""
    cids = directory.list_clients_visible_for_user("user_admin_demo")
    assert set(cids) == {"client_a", "client_b"}


@pytest.mark.integration
def test_list_clients_visible_for_user_no_relation(directory):
    """成员乙没绑过任何 client → []"""
    cids = directory.list_clients_visible_for_user("emp_ebf2ea94ed")
    assert cids == []


@pytest.mark.unit
def test_dataclass_is_frozen():
    """User / Department / Organization 都是 frozen,不能改"""
    org = Organization(id="o1", name="测试")
    with pytest.raises(FrozenInstanceError):
        org.name = "修改"  # type: ignore[misc]

    dept = Department(id="d1", organization_id="o1", name="部门")
    with pytest.raises(FrozenInstanceError):
        dept.active = False  # type: ignore[misc]

    user = User(id="u1", organization_id="o1", department_id=None, full_name="名")
    with pytest.raises(FrozenInstanceError):
        user.full_name = "改"  # type: ignore[misc]
