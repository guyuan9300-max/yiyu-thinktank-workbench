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


def login_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def customer_service_invite() -> str:
    return _department_invite_code(
        "dept_customer_service",
        organization_id=DEFAULT_ORG_ID,
        organization_name="益语智库",
        department_name="客户服务部",
        order=3,
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
            "organizationName": "个人注册组织",
        },
    )
    assert register.status_code == 200, register.text
    payload = register.json()
    assert payload["accessToken"]
    assert payload["refreshToken"]
    assert payload["user"]["email"] == "new-personal-user@example.com"
    assert payload["user"]["phone"] == "+8613800138000"
    assert payload["user"]["primaryRole"] == "admin"
    assert payload["user"]["accountStatus"] == "approved"
    assert payload["user"]["membershipStatus"] == "approved"

    login = client.post(
        "/api/v1/auth/login",
        json={
            "identifier": "13800138000",
            "password": "Password123!",
        },
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["email"] == "new-personal-user@example.com"
    assert login.json()["user"]["primaryRole"] == "admin"
    assert login.json()["user"]["membershipStatus"] == "approved"
    role_row = app.state.app_state.db.fetchone(
        "SELECT role FROM employee_role_bindings WHERE user_id = ? AND role = 'admin'",
        (login.json()["user"]["id"],),
    )
    assert role_row is not None


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


def test_valid_invite_registration_syncs_org_ai_config_and_space_profile(tmp_path, monkeypatch):
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Simulate123!")

    app = create_app()
    seed_registration_departments(app)
    client = TestClient(app)
    admin_headers = login_headers(client, "admin@yiyu-system.com", "Admin123!")

    configured = client.post(
        "/api/v1/settings/org-ai-config",
        json={
            "aiProvider": "openai-compatible",
            "aiProviderLabel": "云端统一大模型",
            "aiBaseUrl": "https://models.example.com/v1",
            "aiModel": "yiyu-cloud-model",
            "apiKey": "sk-shared-cloud",
        },
        headers=admin_headers,
    )
    assert configured.status_code == 200, configured.text

    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": "invited-member@example.com",
            "fullName": "受邀同事",
            "phone": "13900139000",
            "password": "Password123!",
            "inviteCode": customer_service_invite(),
            "jobTitle": "客户经理",
        },
    )
    assert register.status_code == 200, register.text
    payload = register.json()
    assert payload["user"]["accountStatus"] == "approved"
    assert payload["user"]["membershipStatus"] == "approved"
    assert payload["user"]["organizationId"] == DEFAULT_ORG_ID
    assert payload["user"]["departmentId"] == "dept_customer_service"
    member_headers = {"Authorization": f"Bearer {payload['accessToken']}"}

    membership = client.get("/api/v1/me/org-membership", headers=member_headers)
    assert membership.status_code == 200, membership.text
    assert membership.json()["hasOrganization"] is True
    assert membership.json()["membershipStatus"] == "approved"
    assert membership.json()["organizationWorkspaceClientId"]

    ai_secret = client.get("/api/v1/settings/org-ai-config/secret", headers=member_headers)
    assert ai_secret.status_code == 403
    runtime_secret = client.get("/api/v1/settings/org-ai-config/runtime-secret", headers=member_headers)
    assert runtime_secret.status_code == 200, runtime_secret.text
    assert runtime_secret.json()["apiKey"] == "sk-shared-cloud"
    assert runtime_secret.json()["aiModel"] == "yiyu-cloud-model"
    assert runtime_secret.json()["cloudInstanceId"]
    assert runtime_secret.json()["configVersion"]

    # 新客户端只走运行配置下发 + 本机直连；云端代理接口已撤下。
    assert client.get("/api/v1/org-ai/status", headers=member_headers).status_code == 404
    assert client.post("/api/v1/org-ai/chat/completions", json={}, headers=member_headers).status_code == 404

    org_profile = client.get("/api/v1/settings/org-model/profile", headers=member_headers)
    assert org_profile.status_code == 200, org_profile.text
    assert org_profile.json()["organization"]["organizationId"] == DEFAULT_ORG_ID
    assert any(item["id"] == "dept_customer_service" for item in org_profile.json()["departments"])


def test_admin_transfer_promotes_target_and_keeps_one_admin_guard(tmp_path, monkeypatch):
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Simulate123!")

    app = create_app()
    seed_registration_departments(app)
    client = TestClient(app)
    admin_headers = login_headers(client, "admin@yiyu-system.com", "Admin123!")

    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": "next-admin@example.com",
            "fullName": "接任管理员",
            "phone": "17316888678",
            "password": "Password123!",
            "inviteCode": customer_service_invite(),
        },
    )
    assert registered.status_code == 200, registered.text
    target_user = registered.json()["user"]
    target_headers = {"Authorization": f"Bearer {registered.json()['accessToken']}"}

    transferred = client.post(
        "/api/v1/admin/employees/transfer-admin",
        json={
            "targetUserId": target_user["id"],
            "currentAdminAction": "demote_to_member",
            "currentAdminDepartmentId": "dept_customer_service",
        },
        headers=admin_headers,
    )
    assert transferred.status_code == 200, transferred.text

    db = app.state.app_state.db
    new_admin = db.fetchone("SELECT primary_role FROM employee_accounts WHERE id = ?", (target_user["id"],))
    old_admin = db.fetchone("SELECT primary_role, department_id FROM employee_accounts WHERE email = ?", ("admin@yiyu-system.com",))
    assert new_admin["primary_role"] == "admin"
    assert old_admin["primary_role"] == "employee"
    assert old_admin["department_id"] == "dept_customer_service"

    demote_last_admin = client.patch(
        f"/api/v1/admin/employees/{target_user['id']}/role",
        json={"role": "employee"},
        headers=target_headers,
    )
    assert demote_last_admin.status_code == 400, demote_last_admin.text
    assert "至少需要保留一名管理员" in demote_last_admin.text


def test_register_without_invite_requires_new_org_name_when_admin_exists(tmp_path, monkeypatch):
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Simulate123!")

    app = create_app()
    seed_registration_departments(app)
    client = TestClient(app)

    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": "existing-invited-member@example.com",
            "phone": "13800138204",
            "fullName": "已有云账号同事",
            "password": "Password123!",
        },
    )
    assert register.status_code == 409, register.text
    assert "成员加入请填写组织或部门邀请码" in register.text

    joined = client.post(
        "/api/v1/auth/register",
        json={
            "email": "existing-invited-member@example.com",
            "phone": "13800138204",
            "fullName": "已有云账号同事",
            "password": "Password123!",
            "inviteCode": customer_service_invite(),
            "jobTitle": "客户成功",
        },
    )
    assert joined.status_code == 200, joined.text
    payload = joined.json()
    assert payload["user"]["membershipStatus"] == "approved"
    assert payload["user"]["organizationId"] == DEFAULT_ORG_ID
    assert payload["user"]["departmentId"] == "dept_customer_service"


def test_register_without_invite_claims_adminless_cloud(tmp_path, monkeypatch):
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")

    app = create_app()
    db = app.state.app_state.db
    timestamp = now_iso()
    db.execute(
        "UPDATE employee_accounts SET primary_role = 'employee', account_status = 'approved', membership_status = 'approved', updated_at = ?",
        (timestamp,),
    )
    db.execute("DELETE FROM employee_role_bindings WHERE role = 'admin'")
    client = TestClient(app)

    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": "claim-adminless@example.com",
            "phone": "13800138205",
            "fullName": "接管空云端",
            "password": "Password123!",
        },
    )
    assert register.status_code == 200, register.text
    payload = register.json()
    assert payload["user"]["primaryRole"] == "admin"
    assert payload["user"]["accountStatus"] == "approved"
    assert payload["user"]["membershipStatus"] == "approved"

    member_headers = {"Authorization": f"Bearer {payload['accessToken']}"}
    org_profile = client.get("/api/v1/settings/org-model/profile", headers=member_headers)
    assert org_profile.status_code == 200, org_profile.text
    assert org_profile.json()["organization"]["organizationId"] == DEFAULT_ORG_ID
