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

    ai_status = client.get("/api/v1/org-ai/status", headers=member_headers)
    assert ai_status.status_code == 200, ai_status.text
    assert ai_status.json()["available"] is True
    assert ai_status.json()["aiProvider"] == "openai-compatible"
    assert ai_status.json()["aiModel"] == "yiyu-cloud-model"
    assert "apiKey" not in ai_status.text

    class FakeOrgAiResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "组织 AI 已可用"}}]}

    class FakeOrgAiClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, *, headers, json):
            assert url == "https://models.example.com/v1/chat/completions"
            assert headers["Authorization"] == "Bearer sk-shared-cloud"
            assert json["model"] == "yiyu-cloud-model"
            return FakeOrgAiResponse()

    import httpx

    monkeypatch.setattr(httpx, "Client", FakeOrgAiClient)
    proxy = client.post(
        "/api/v1/org-ai/chat/completions",
        json={
            "model": "member-override-should-be-ignored",
            "messages": [{"role": "user", "content": "ping"}],
            "stream": False,
        },
        headers=member_headers,
    )
    assert proxy.status_code == 200, proxy.text
    assert proxy.json()["choices"][0]["message"]["content"] == "组织 AI 已可用"

    org_profile = client.get("/api/v1/settings/org-model/profile", headers=member_headers)
    assert org_profile.status_code == 200, org_profile.text
    assert org_profile.json()["organization"]["organizationId"] == DEFAULT_ORG_ID
    assert any(item["id"] == "dept_customer_service" for item in org_profile.json()["departments"])


def test_existing_cloud_account_apply_valid_invite_unlocks_member_resources(tmp_path, monkeypatch):
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
            "fullName": "已有云账号同事",
            "password": "Password123!",
        },
    )
    assert register.status_code == 200, register.text
    member_headers = {"Authorization": f"Bearer {register.json()['accessToken']}"}
    blocked_profile = client.get("/api/v1/settings/org-model/profile", headers=member_headers)
    assert blocked_profile.status_code == 403

    applied = client.post(
        "/api/v1/me/org-membership/apply",
        json={
            "inviteCode": customer_service_invite(),
            "jobTitle": "客户成功",
        },
        headers=member_headers,
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["hasOrganization"] is True
    assert applied.json()["membershipStatus"] == "approved"
    assert applied.json()["organizationId"] == DEFAULT_ORG_ID
    assert applied.json()["departmentId"] == "dept_customer_service"

    org_profile = client.get("/api/v1/settings/org-model/profile", headers=member_headers)
    assert org_profile.status_code == 200, org_profile.text
    assert org_profile.json()["organization"]["organizationId"] == DEFAULT_ORG_ID
