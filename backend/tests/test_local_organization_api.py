"""W1-4a 验证 · /api/v1/local/organization/* endpoint

跑法:
    backend/.venv/bin/python3 -m pytest backend/tests/test_local_organization_api.py -v

设计:
- 用 FastAPI TestClient(create_app + tmp data_dir)
- 空 db 测 profile endpoint:应返回 None + 空 list,不报错
- 用 sync_organization_directory 直接 seed mirror 表 → profile endpoint 返回正确
- sync endpoint:cloud 没配 → 400;mock cloud 配好 → 调通(用 mock)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.main import create_app  # noqa: E402
from app.modules.organization import sync_organization_directory  # noqa: E402


def _make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def _profile_sample():
    return {
        "organization": {"organizationId": "org_yiyu_default", "name": "益语智库",
                         "slug": "yiyu", "updatedAt": "2026-05-19T07:11:27"},
        "departments": [
            {"id": "department_gq160gdz", "name": "战略发展部", "color": "#5B7BFE",
             "leaderUserId": "user_guyuan", "leaderName": "顾源源", "active": True,
             "updatedAt": "2026-05-19T07:11:27"},
            {"id": "department_b3zvoei7", "name": "合作发展部", "color": "#14B8A6",
             "leaderUserId": "emp_efdd076c31", "leaderName": "乐乐", "active": True,
             "updatedAt": "2026-05-19T07:11:27"},
        ],
        "bindings": [
            {"userId": "user_guyuan", "departmentId": "department_gq160gdz",
             "isManager": True, "taskEditScope": "department",
             "canApproveTasks": True, "projectRoleLabels": ["CEO"]},
        ],
    }


def _employees_sample():
    return [
        {"id": "user_guyuan", "fullName": "顾源源", "email": "guyuan@klngo.org",
         "primaryRole": "admin", "accountStatus": "approved",
         "departmentId": "department_gq160gdz",
         "isDepartmentLead": True, "updatedAt": "2026-05-19T07:11:27"},
    ]


def _mock_http(profile, employees):
    def http(base, path, token, **kw):
        if path == "/api/v1/settings/org-model/profile":
            return profile
        if path == "/api/v1/employees/directory":
            return employees
        raise ValueError(path)
    return http


def test_profile_empty_db_returns_safe_shape(tmp_path: Path):
    """空 mirror 表 → organization=None, departments=[], users=[],不报错"""
    client = _make_client(tmp_path)
    resp = client.get("/api/v1/local/organization/profile")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["organization"] is None
    assert body["departments"] == []
    assert body["users"] == []


def test_profile_after_sync_returns_full_data(tmp_path: Path):
    """seed mirror 表后 profile 返回完整数据"""
    client = _make_client(tmp_path)
    # 通过 create_app 启动的 db 跟我们调 sync 的 db 必须是同一个,绕过 cloud_session
    # 直接拿 app.state.db
    state = client.app.state.app_state  # type: ignore[attr-defined]

    sync_organization_directory(
        state.db,
        cloud_base_url="http://t", cloud_token="x",
        http_get=_mock_http(_profile_sample(), _employees_sample()),
        now_iso=lambda: "2026-05-20T12:00:00",
    )

    resp = client.get("/api/v1/local/organization/profile")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["organization"]["id"] == "org_yiyu_default"
    assert body["organization"]["name"] == "益语智库"

    dept_names = [d["name"] for d in body["departments"]]
    assert "战略发展部" in dept_names
    assert "合作发展部" in dept_names

    user_names = [u["fullName"] for u in body["users"]]
    assert "顾源源" in user_names

    guyuan = next(u for u in body["users"] if u["id"] == "user_guyuan")
    assert guyuan["departmentId"] == "department_gq160gdz"
    assert guyuan["isManager"] is True
    assert guyuan["taskEditScope"] == "department"
    assert "CEO" in guyuan["projectRoleLabels"]


def test_scoped_sync_with_empty_sandbox_preserves_other_sandbox_cru(
    tmp_path: Path,
) -> None:
    client = _make_client(tmp_path)
    db = client.app.state.app_state.db
    db.execute(
        """
        INSERT INTO mirror_client_related_users(
            client_id, user_id, order_index, cloud_updated_at, synced_from_cloud_at
        ) VALUES(?, ?, 0, ?, ?)
        """,
        ("client-b", "user-b", "2026-07-10T00:00:00Z", "2026-07-10T00:00:00Z"),
    )
    profile_a = {
        "organization": {
            "organizationId": "org-a",
            "name": "组织 A",
            "slug": "org-a",
            "updatedAt": "2026-07-11T00:00:00Z",
        },
        "departments": [],
        "bindings": [],
    }

    report = sync_organization_directory(
        db,
        cloud_base_url="https://org-a.example.test",
        cloud_token="token-a",
        client_sandbox_id="sandbox-a-with-no-clients",
        expected_organization_id="org-a",
        http_get=_mock_http(profile_a, []),
        now_iso=lambda: "2026-07-11T00:00:00Z",
    )

    assert report.status == "ok"
    assert db.fetchone(
        """
        SELECT client_id, user_id
        FROM mirror_client_related_users
        WHERE client_id = ? AND user_id = ?
        """,
        ("client-b", "user-b"),
    ) is not None


def test_sync_rejects_unexpected_cloud_organization_before_writes(
    tmp_path: Path,
) -> None:
    client = _make_client(tmp_path)
    db = client.app.state.app_state.db

    report = sync_organization_directory(
        db,
        cloud_base_url="https://org-a.example.test",
        cloud_token="token-a",
        expected_organization_id="org-a",
        http_get=_mock_http(_profile_sample(), _employees_sample()),
        now_iso=lambda: "2026-07-11T00:00:00Z",
    )

    assert report.status == "failed"
    assert report.error == "organization identity mismatch"
    assert db.scalar("SELECT COUNT(1) FROM mirror_organizations") == 0


def test_sync_without_cloud_returns_error(tmp_path: Path):
    """没配 cloud token → 客户端错误(400 / 503,具体看 cloud_api_base_url 行为)"""
    client = _make_client(tmp_path)
    resp = client.post("/api/v1/local/organization/sync")
    # 不管是 400 (我们 if 拦截) 还是 503 (cloud_api_base_url 提前抛)
    # 都说明 cloud 没配,系统正确拒绝
    assert resp.status_code in (400, 503), f"expected 400 or 503, got {resp.status_code}: {resp.text}"
