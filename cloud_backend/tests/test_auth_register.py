from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import DEFAULT_ORG_ID, _department_invite_code, create_app, now_iso  # noqa: E402
from app.security import hash_password  # noqa: E402


def seed_registration_departments(app) -> None:
    db = app.state.app_state.db
    timestamp = now_iso()
    db.execute("UPDATE organizations SET name = ?, updated_at = ? WHERE id = ?", ("益语智库", timestamp, DEFAULT_ORG_ID))
    for department_id, name, color in [
        ("dept_consult_strategy", "咨询策略部", "#5B7BFE"),
        ("dept_tech_development", "科技发展部", "#F59E0B"),
        ("dept_info_data", "信息数据部", "#10B981"),
        ("dept_customer_service", "客户服务部", "#14B8A6"),
    ]:
        db.execute(
            """
            INSERT OR REPLACE INTO org_departments(id, organization_id, name, color, active, updated_at)
            VALUES(?, ?, ?, ?, 1, ?)
            """,
            (department_id, DEFAULT_ORG_ID, name, color, timestamp),
        )


def test_register_returns_tokens_and_allows_immediate_login(tmp_path, monkeypatch):
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Simulate123!")

    app = create_app()
    seed_registration_departments(app)
    client = TestClient(app)

    invite = client.get("/api/v1/auth/invite-code/resolve", params={"code": "dept_customer_service"})
    assert invite.status_code == 200, invite.text
    assert invite.json()["valid"] is True
    assert invite.json()["departmentId"] == "dept_customer_service"
    formatted_invite = _department_invite_code(
        "dept_customer_service",
        organization_id=DEFAULT_ORG_ID,
        organization_name="益语智库",
        department_name="客户服务部",
        order=3,
    )
    share_text_invite = client.get("/api/v1/auth/invite-code/resolve", params={"code": f"客户服务部：邀请码 {formatted_invite}"})
    assert share_text_invite.status_code == 200, share_text_invite.text
    assert share_text_invite.json()["valid"] is True
    assert share_text_invite.json()["departmentId"] == "dept_customer_service"

    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new-personal-user@example.com",
            "fullName": "个人注册用户",
            "phone": "13800138000",
            "password": "Password123!",
        },
    )
    assert register.status_code == 200, register.text
    payload = register.json()
    assert payload["accessToken"]
    assert payload["refreshToken"]
    assert payload["user"]["email"] == "new-personal-user@example.com"
    assert payload["user"]["phone"] == "+8613800138000"
    assert payload["user"]["accountStatus"] == "approved"
    assert payload["user"]["membershipStatus"] == "none"

    login = client.post(
        "/api/v1/auth/login",
        json={
            "identifier": "13800138000",
            "password": "Password123!",
        },
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["email"] == "new-personal-user@example.com"
    assert login.json()["user"]["membershipStatus"] == "none"
    blocked_tasks = client.get("/api/v1/tasks", headers={"Authorization": f"Bearer {login.json()['accessToken']}"})
    assert blocked_tasks.status_code == 403
    assert "组织身份尚未确认" in blocked_tasks.text


def test_legacy_pending_account_can_login_without_manual_approval(tmp_path, monkeypatch):
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Simulate123!")

    app = create_app()
    db = app.state.app_state.db
    db.execute(
        """
        INSERT INTO employee_accounts(
            id, organization_id, email, full_name, password_hash, primary_role, account_status,
            approved_at, approved_by, rejected_reason, disabled_at, recent_mentions_json, last_login_at,
            department_id, department_name, job_title, manager_name, current_focus, is_department_lead, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, 'employee', 'pending', NULL, NULL, NULL, NULL, '[]', NULL, NULL, NULL, NULL, NULL, '', 0, ?, ?)
        """,
        (
            "emp_legacy_pending",
            DEFAULT_ORG_ID,
            "legacy-pending@example.com",
            "旧待审核用户",
            hash_password("Password123!"),
            "2026-04-07T00:00:00",
            "2026-04-07T00:00:00",
        ),
    )
    client = TestClient(app)

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "legacy-pending@example.com",
            "password": "Password123!",
        },
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["accountStatus"] == "pending"
    assert login.json()["user"]["membershipStatus"] == "pending"
    blocked_tasks = client.get("/api/v1/tasks", headers={"Authorization": f"Bearer {login.json()['accessToken']}"})
    assert blocked_tasks.status_code == 403
    assert "组织身份尚未确认" in blocked_tasks.text

    row = db.fetchone("SELECT account_status, membership_status, approved_at FROM employee_accounts WHERE id = ?", ("emp_legacy_pending",))
    assert row is not None
    assert row["account_status"] == "pending"
    assert row["membership_status"] == "pending"
    assert not row["approved_at"]
