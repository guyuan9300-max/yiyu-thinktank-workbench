"""W1-2 验证 · organization 模块 sync 逻辑

跑法:
    backend/.venv/bin/python3 -m pytest tests/test_organization_sync.py -v

设计:
- 用 mock HTTP 注入(不碰真实云端)
- 验证 4 张 mirror 表都被正确写入
- 验证 deleted scenario:云端删了的 row 本地也删
- 验证 HTTP 失败:旧 mirror 保留,返回 failed
- 验证 sync 程序的写绕过 readonly trigger(每次 UPSERT 都刷 synced_from_cloud_at)
"""
from __future__ import annotations

import json
import sys
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.db import Database  # noqa: E402
from app.modules.organization.sync import (  # noqa: E402
    SyncReport,
    sync_organization_directory,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(tmp_path / "app.db")


def _profile_v1() -> dict:
    """模拟火山云 /api/v1/settings/org-model/profile 响应"""
    return {
        "organization": {
            "organizationId": "org_yiyu_default",
            "name": "益语智库",
            "slug": "yiyu-thinktank",
            "updatedAt": "2026-05-19T07:11:27",
        },
        "departments": [
            {"id": "department_gq160gdz", "name": "战略发展部", "color": "#5B7BFE",
             "leaderUserId": "user_guyuan", "leaderName": "顾源源", "active": True,
             "updatedAt": "2026-05-19T07:11:27"},
            {"id": "department_b3zvoei7", "name": "合作发展部", "color": "#14B8A6",
             "leaderUserId": "emp_efdd076c31", "leaderName": "乐乐", "active": True,
             "updatedAt": "2026-05-19T07:11:27"},
            {"id": "department_sufbu60r", "name": "技术创新部", "color": "#0EA5E9",
             "leaderUserId": "emp_ebf2ea94ed", "leaderName": "林佳维", "active": True,
             "updatedAt": "2026-05-19T07:11:27"},
        ],
        "bindings": [
            {"userId": "user_guyuan", "departmentId": "department_gq160gdz",
             "isManager": True, "taskEditScope": "department",
             "canApproveTasks": True, "canReassignTasks": True, "canChangeDeadline": True,
             "projectRoleLabels": ["CEO"]},
            {"userId": "emp_efdd076c31", "departmentId": "department_b3zvoei7",
             "isManager": True, "managerUserId": "user_guyuan", "taskEditScope": "self",
             "projectRoleLabels": ["合作总监"]},
            {"userId": "emp_ebf2ea94ed", "departmentId": "department_sufbu60r",
             "isManager": True, "taskEditScope": "self"},
            {"userId": "user_admin", "departmentId": None,
             "isManager": True, "taskEditScope": "department",
             "canApproveTasks": True, "canReassignTasks": True, "canChangeDeadline": True},
        ],
    }


def _employees_v1() -> list[dict]:
    """模拟真实生产员工列表 · 混合 approved/pending/disabled 状态(reviewer W3 修)"""
    return [
        {"id": "user_guyuan", "fullName": "顾源源", "email": "guyuan@klngo.org",
         "primaryRole": "admin", "accountStatus": "approved",
         "membershipStatus": "approved", "departmentId": "department_gq160gdz",
         "departmentName": "战略发展部", "isDepartmentLead": True,
         "updatedAt": "2026-05-19T07:11:27"},
        {"id": "user_admin", "fullName": "系统管理员", "email": "admin@yiyu-system.com",
         "primaryRole": "admin", "accountStatus": "approved",
         "membershipStatus": "approved", "departmentId": None,
         "isDepartmentLead": True, "updatedAt": "2026-05-19T07:11:27"},
        {"id": "emp_ebf2ea94ed", "fullName": "林佳维", "email": "1446530230@qq.com",
         "primaryRole": "employee", "accountStatus": "approved",
         "membershipStatus": "approved", "departmentId": "department_sufbu60r",
         "departmentName": "技术创新部", "isDepartmentLead": True,
         "updatedAt": "2026-05-19T07:11:27"},
        {"id": "emp_efdd076c31", "fullName": "乐乐", "email": "chenzhenli@klngo.org",
         "primaryRole": "employee", "accountStatus": "approved",
         "membershipStatus": "approved", "departmentId": "department_b3zvoei7",
         "departmentName": "合作发展部", "isDepartmentLead": True,
         "updatedAt": "2026-05-19T07:11:27"},
        # pending:已申请但未审批
        {"id": "emp_pending_001", "fullName": "申请中员工", "email": "pending@klngo.org",
         "primaryRole": "employee", "accountStatus": "pending",
         "membershipStatus": "pending", "departmentId": None,
         "isDepartmentLead": False, "updatedAt": "2026-05-20T01:00:00"},
        # disabled:被禁用
        {"id": "emp_disabled_001", "fullName": "已禁用员工", "email": "disabled@klngo.org",
         "primaryRole": "employee", "accountStatus": "disabled",
         "membershipStatus": "approved", "departmentId": "department_b3zvoei7",
         "isDepartmentLead": False, "updatedAt": "2026-05-15T10:00:00"},
    ]


def _make_mock_http(profile: dict, employees: list):
    """Mock HTTP:只覆盖 2 个云端 endpoint(client_related_users 走本地 clients 派生)"""
    def mock_http(base_url, path, token, **kwargs):
        if path == "/api/v1/settings/org-model/profile":
            return profile
        if path == "/api/v1/employees/directory":
            return employees
        raise ValueError(f"unexpected path: {path}")
    return mock_http


def _seed_local_clients(db: Database, clients: list[tuple[str, str, list[str]]]) -> None:
    """在本地 clients 表插入测试数据 (id, name, related_user_ids)"""
    now = "2026-05-20T10:00:00"
    for cid, name, related in clients:
        db.conn.execute(
            """
            INSERT INTO clients(id, name, alias, domain, type, intro, stage, color,
                                created_at, updated_at, related_user_ids_json)
            VALUES(?, ?, '', '项目', '项目', '', '待导入资料', '#5B7BFE', ?, ?, ?)
            """,
            (cid, name, now, now, json.dumps(related)),
        )
    db.conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# 主功能测试
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_first_sync_writes_all_4_tables(db: Database):
    """第一次 sync 把云端 4 类数据全写进 4 张 mirror 表"""
    _seed_local_clients(db, [
        ("client_a", "客户A", ["user_guyuan", "emp_efdd076c31"]),
        ("client_b", "客户B", ["user_guyuan"]),
    ])
    report = sync_organization_directory(
        db,
        cloud_base_url="http://test",
        cloud_token="fake-token",
        http_get=_make_mock_http(_profile_v1(), _employees_v1()),
        now_iso=lambda: "2026-05-20T12:00:00",
    )
    assert report.status == "ok", f"sync failed: {report.error}"
    assert {r.table for r in report.tables} == {
        "mirror_organizations", "mirror_departments", "mirror_users", "mirror_client_related_users"
    }

    # organization
    rows = db.fetchall("SELECT id, name FROM mirror_organizations")
    assert len(rows) == 1 and rows[0]["name"] == "益语智库"

    # departments(3 个)
    rows = db.fetchall("SELECT id, name, leader_name FROM mirror_departments ORDER BY name")
    names = [r["name"] for r in rows]
    assert names == ["合作发展部", "战略发展部", "技术创新部"]

    # users(4 个)
    rows = db.fetchall("SELECT id, full_name, department_id, is_manager, is_department_lead FROM mirror_users ORDER BY full_name")
    full_names = [r["full_name"] for r in rows]
    assert "顾源源" in full_names and "乐乐" in full_names and "林佳维" in full_names and "系统管理员" in full_names
    by_name = {r["full_name"]: r for r in rows}
    assert by_name["顾源源"]["department_id"] == "department_gq160gdz"
    assert by_name["顾源源"]["is_manager"] == 1
    assert by_name["顾源源"]["is_department_lead"] == 1

    # client_related_users(3 行:client_a 2 + client_b 1)
    rows = db.fetchall("SELECT client_id, user_id, order_index FROM mirror_client_related_users ORDER BY client_id, order_index")
    assert len(rows) == 3
    assert rows[0]["client_id"] == "client_a" and rows[0]["user_id"] == "user_guyuan"
    assert rows[1]["client_id"] == "client_a" and rows[1]["user_id"] == "emp_efdd076c31"
    assert rows[2]["client_id"] == "client_b" and rows[2]["user_id"] == "user_guyuan"


@pytest.mark.integration
def test_second_sync_removes_deleted_user(db: Database):
    """云端删了乐乐 → 第二次 sync 本地 mirror_users 也删"""
    # 第一次:4 人都在
    sync_organization_directory(
        db, cloud_base_url="http://t", cloud_token="x",
        derive_cru_from_local=False,
        http_get=_make_mock_http(_profile_v1(), _employees_v1()),
        now_iso=lambda: "2026-05-20T12:00:00",
    )
    assert db.fetchone("SELECT 1 FROM mirror_users WHERE id='emp_efdd076c31'") is not None

    # 第二次:云端少了乐乐
    employees_no_le = [e for e in _employees_v1() if e["id"] != "emp_efdd076c31"]
    profile_no_le = _profile_v1()
    profile_no_le["bindings"] = [b for b in profile_no_le["bindings"] if b["userId"] != "emp_efdd076c31"]

    report = sync_organization_directory(
        db, cloud_base_url="http://t", cloud_token="x",
        derive_cru_from_local=False,
        http_get=_make_mock_http(profile_no_le, employees_no_le),
        now_iso=lambda: "2026-05-20T13:00:00",
    )
    assert report.status == "ok"
    assert db.fetchone("SELECT 1 FROM mirror_users WHERE id='emp_efdd076c31'") is None
    # 其他 3 人还在
    assert db.fetchone("SELECT 1 FROM mirror_users WHERE id='user_guyuan'") is not None


@pytest.mark.integration
def test_second_sync_removes_deleted_client_relation(db: Database):
    """改本地 clients.related_user_ids_json → 第二次 sync mirror_client_related_users 缩减"""
    _seed_local_clients(db, [("client_a", "A", ["user_guyuan", "emp_efdd076c31"])])

    sync_organization_directory(
        db, cloud_base_url="http://t", cloud_token="x",
        http_get=_make_mock_http(_profile_v1(), _employees_v1()),
        now_iso=lambda: "2026-05-20T12:00:00",
    )
    assert len(db.fetchall("SELECT 1 FROM mirror_client_related_users WHERE client_id='client_a'")) == 2

    # 改本地 clients(模拟 cloud sync 把 related_user_ids 缩成 1 个)
    db.conn.execute(
        "UPDATE clients SET related_user_ids_json = ? WHERE id = 'client_a'",
        (json.dumps(["user_guyuan"]),),
    )
    db.conn.commit()

    report = sync_organization_directory(
        db, cloud_base_url="http://t", cloud_token="x",
        http_get=_make_mock_http(_profile_v1(), _employees_v1()),
        now_iso=lambda: "2026-05-20T13:00:00",
    )
    assert report.status == "ok"
    rows = db.fetchall("SELECT user_id FROM mirror_client_related_users WHERE client_id='client_a'")
    assert len(rows) == 1 and rows[0]["user_id"] == "user_guyuan"


@pytest.mark.integration
def test_http_failure_keeps_old_mirror(db: Database):
    """HTTP 报错 → 旧 mirror 不动,返回 failed"""
    # 先写入老数据
    sync_organization_directory(
        db, cloud_base_url="http://t", cloud_token="x",
        derive_cru_from_local=False,
        http_get=_make_mock_http(_profile_v1(), _employees_v1()),
        now_iso=lambda: "2026-05-20T12:00:00",
    )
    before = db.fetchall("SELECT id FROM mirror_users")

    # 模拟网络断
    def broken_http(base_url, path, token, **kwargs):
        raise urllib.error.URLError("connection refused")

    report = sync_organization_directory(
        db, cloud_base_url="http://t", cloud_token="x",
        http_get=broken_http,
        now_iso=lambda: "2026-05-20T13:00:00",
    )
    assert report.status == "failed"
    assert "http" in (report.error or "")
    after = db.fetchall("SELECT id FROM mirror_users")
    assert {r["id"] for r in before} == {r["id"] for r in after}


@pytest.mark.integration
def test_missing_token_returns_skipped(db: Database):
    """没有 token / URL → skipped,不报错"""
    report = sync_organization_directory(
        db, cloud_base_url="", cloud_token="x",
        http_get=lambda *a, **kw: pytest.fail("should not call http"),
        now_iso=lambda: "2026-05-20T12:00:00",
    )
    assert report.status == "skipped"


@pytest.mark.integration
def test_sync_writes_bypass_readonly_trigger(db: Database):
    """sync 程序写 mirror 表绕过 readonly trigger(每次刷新 synced_from_cloud_at)"""
    sync_organization_directory(
        db, cloud_base_url="http://t", cloud_token="x",
        derive_cru_from_local=False,
        http_get=_make_mock_http(_profile_v1(), _employees_v1()),
        now_iso=lambda: "2026-05-20T12:00:00",
    )
    sync_organization_directory(
        db, cloud_base_url="http://t", cloud_token="x",
        derive_cru_from_local=False,
        http_get=_make_mock_http(_profile_v1(), _employees_v1()),
        now_iso=lambda: "2026-05-20T13:00:00",  # 新时间戳
    )
    # 没抛 IntegrityError 就算过
    rows = db.fetchall("SELECT synced_from_cloud_at FROM mirror_users WHERE id='user_guyuan'")
    assert rows[0]["synced_from_cloud_at"] == "2026-05-20T13:00:00"


@pytest.mark.integration
def test_derive_cru_disabled_keeps_table_untouched(db: Database):
    """derive_cru_from_local=False → mirror_client_related_users 不动"""
    _seed_local_clients(db, [("client_a", "A", ["user_guyuan"])])
    sync_organization_directory(
        db, cloud_base_url="http://t", cloud_token="x",
        derive_cru_from_local=True,
        http_get=_make_mock_http(_profile_v1(), _employees_v1()),
        now_iso=lambda: "2026-05-20T12:00:00",
    )
    assert len(db.fetchall("SELECT 1 FROM mirror_client_related_users")) == 1

    # 第二次禁用 derive → 上次数据保留
    sync_organization_directory(
        db, cloud_base_url="http://t", cloud_token="x",
        derive_cru_from_local=False,
        http_get=_make_mock_http(_profile_v1(), _employees_v1()),
        now_iso=lambda: "2026-05-20T13:00:00",
    )
    assert len(db.fetchall("SELECT 1 FROM mirror_client_related_users")) == 1


@pytest.mark.integration
def test_sync_includes_pending_and_disabled_users(db: Database):
    """sync 把所有 accountStatus 的用户都写进 mirror,过滤交给查询层(reviewer W3)"""
    sync_organization_directory(
        db, cloud_base_url="http://t", cloud_token="x",
        derive_cru_from_local=False,
        http_get=_make_mock_http(_profile_v1(), _employees_v1()),
        now_iso=lambda: "2026-05-20T12:00:00",
    )
    # pending + disabled 用户都应该在 mirror 表里
    statuses = {r["account_status"] for r in db.fetchall("SELECT account_status FROM mirror_users")}
    assert "approved" in statuses
    assert "pending" in statuses
    assert "disabled" in statuses


@pytest.mark.integration
def test_http_401_token_expired_keeps_old_mirror(db: Database):
    """HTTP 401(token 过期)→ sync 失败,旧 mirror 保留(reviewer W3)"""
    # 先有数据
    sync_organization_directory(
        db, cloud_base_url="http://t", cloud_token="x",
        derive_cru_from_local=False,
        http_get=_make_mock_http(_profile_v1(), _employees_v1()),
        now_iso=lambda: "2026-05-20T12:00:00",
    )
    before_count = len(db.fetchall("SELECT 1 FROM mirror_users"))
    assert before_count > 0

    # 模拟 token 过期 → HTTP 401
    def http_401(base_url, path, token, **kwargs):
        raise urllib.error.HTTPError(
            url=base_url + path, code=401, msg="Unauthorized",
            hdrs=None, fp=None,  # type: ignore[arg-type]
        )

    report = sync_organization_directory(
        db, cloud_base_url="http://t", cloud_token="x",
        derive_cru_from_local=False,
        http_get=http_401,
        now_iso=lambda: "2026-05-20T13:00:00",
    )
    assert report.status == "failed"
    assert "401" in (report.error or "") or "http" in (report.error or "")
    # 老数据保留
    after_count = len(db.fetchall("SELECT 1 FROM mirror_users"))
    assert after_count == before_count


@pytest.mark.integration
def test_malformed_json_response_returns_failed(db: Database):
    """云端返回结构不对(没 organization key)→ sync 失败,不污染本地(reviewer W3)"""
    def http_bad_shape(base_url, path, token, **kwargs):
        if path == "/api/v1/settings/org-model/profile":
            return {"unexpected": "shape"}  # 缺少 organization key
        if path == "/api/v1/employees/directory":
            return []
        raise ValueError(path)

    report = sync_organization_directory(
        db, cloud_base_url="http://t", cloud_token="x",
        derive_cru_from_local=False,
        http_get=http_bad_shape,
        now_iso=lambda: "2026-05-20T12:00:00",
    )
    assert report.status == "failed"
    assert "shape" in (report.error or "") or "organization" in (report.error or "")
    # mirror 表里没有任何 row
    assert len(db.fetchall("SELECT 1 FROM mirror_users")) == 0


@pytest.mark.integration
def test_user_guyuan_role_data_correct(db: Database):
    """验证 binding 数据正确合并到 user(顾源源 = CEO,task_edit_scope=department)"""
    sync_organization_directory(
        db, cloud_base_url="http://t", cloud_token="x",
        derive_cru_from_local=False,
        http_get=_make_mock_http(_profile_v1(), _employees_v1()),
        now_iso=lambda: "2026-05-20T12:00:00",
    )
    row = db.fetchone("""
        SELECT is_manager, task_edit_scope, can_approve_tasks, project_role_labels_json
        FROM mirror_users WHERE id='user_guyuan'
    """)
    assert row["is_manager"] == 1
    assert row["task_edit_scope"] == "department"
    assert row["can_approve_tasks"] == 1
    labels = json.loads(row["project_role_labels_json"])
    assert "CEO" in labels
