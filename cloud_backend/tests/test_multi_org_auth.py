from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import DEFAULT_ORG_ID, _department_invite_code, create_app, now_iso  # noqa: E402
from app.security import hash_password, verify_password  # noqa: E402


def _make_client(tmp_path, monkeypatch) -> TestClient:
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Simulate123!")
    app = create_app()
    return TestClient(app)


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed_department_invite(client: TestClient) -> str:
    db = client.app.state.app_state.db
    timestamp = now_iso()
    db.execute("UPDATE organizations SET name = ?, updated_at = ? WHERE id = ?", ("益语智库", timestamp, DEFAULT_ORG_ID))
    db.execute(
        """
        INSERT OR REPLACE INTO org_departments(id, organization_id, name, color, active, updated_at)
        VALUES('dept_customer_service', ?, '客户服务部', '#14B8A6', 1, ?)
        """,
        (DEFAULT_ORG_ID, timestamp),
    )
    return _department_invite_code(
        "dept_customer_service",
        organization_id=DEFAULT_ORG_ID,
        organization_name="益语智库",
        department_name="客户服务部",
        order=3,
    )


def test_identity_can_create_second_org_and_choose_on_login(tmp_path, monkeypatch) -> None:
    client = _make_client(tmp_path, monkeypatch)

    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": "multi-owner@example.com",
            "fullName": "多组织用户",
            "phone": "13800138010",
            "password": "Password123!",
            "organizationName": "初始组织",
        },
    )
    assert registered.status_code == 200, registered.text
    first_payload = registered.json()
    first_org_id = first_payload["user"]["organizationId"]

    created = client.post(
        "/api/v1/auth/organizations/create",
        json={"organizationName": "第二组织"},
        headers=_auth_header(first_payload["accessToken"]),
    )
    assert created.status_code == 200, created.text
    second_payload = created.json()
    second_org_id = second_payload["user"]["organizationId"]
    assert second_org_id != first_org_id
    assert second_payload["user"]["primaryRole"] == "admin"
    assert second_payload["user"]["membershipStatus"] == "approved"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "multi-owner@example.com", "password": "Password123!"},
    )
    assert login.status_code == 200, login.text
    login_payload = login.json()
    assert login_payload["organizationSelectionRequired"] is True
    assert not login_payload.get("accessToken")
    candidate_ids = {item["organizationId"] for item in login_payload["organizations"]}
    assert {first_org_id, second_org_id}.issubset(candidate_ids)

    selected = client.post(
        "/api/v1/auth/select-organization",
        json={
            "organizationSelectionToken": login_payload["organizationSelectionToken"],
            "organizationId": second_org_id,
        },
    )
    assert selected.status_code == 200, selected.text
    selected_payload = selected.json()
    assert selected_payload["organizationSelectionRequired"] is False
    assert selected_payload["accessToken"]
    assert selected_payload["user"]["organizationId"] == second_org_id


def test_identity_can_join_another_org_with_invite(tmp_path, monkeypatch) -> None:
    client = _make_client(tmp_path, monkeypatch)
    invite_code = _seed_department_invite(client)

    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": "multi-joiner@example.com",
            "fullName": "跨组织成员",
            "phone": "13800138011",
            "password": "Password123!",
            "organizationName": "个人组织",
        },
    )
    assert registered.status_code == 200, registered.text
    first_org_id = registered.json()["user"]["organizationId"]

    joined = client.post(
        "/api/v1/auth/organizations/join",
        json={"inviteCode": invite_code, "jobTitle": "项目协作者"},
        headers=_auth_header(registered.json()["accessToken"]),
    )
    assert joined.status_code == 200, joined.text
    joined_payload = joined.json()
    assert joined_payload["user"]["organizationId"] == DEFAULT_ORG_ID
    assert joined_payload["user"]["departmentId"] == "dept_customer_service"
    assert joined_payload["user"]["membershipStatus"] == "approved"

    login = client.post(
        "/api/v1/auth/login",
        json={"identifier": "13800138011", "password": "Password123!"},
    )
    assert login.status_code == 200, login.text
    payload = login.json()
    assert payload["organizationSelectionRequired"] is True
    candidate_ids = {item["organizationId"] for item in payload["organizations"]}
    assert {first_org_id, DEFAULT_ORG_ID}.issubset(candidate_ids)


def test_invalid_invite_does_not_create_extra_membership(tmp_path, monkeypatch) -> None:
    client = _make_client(tmp_path, monkeypatch)

    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": "invalid-invite@example.com",
            "fullName": "邀请码测试",
            "phone": "13800138012",
            "password": "Password123!",
            "organizationName": "原组织",
        },
    )
    assert registered.status_code == 200, registered.text
    token = registered.json()["accessToken"]

    failed = client.post(
        "/api/v1/auth/organizations/join",
        json={"inviteCode": "not-a-real-invite"},
        headers=_auth_header(token),
    )
    assert failed.status_code == 400

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "invalid-invite@example.com", "password": "Password123!"},
    )
    assert login.status_code == 200, login.text
    payload = login.json()
    assert payload["organizationSelectionRequired"] is False
    assert payload["accessToken"]


def test_admin_reset_password_syncs_member_and_identity_hashes_for_any_org(tmp_path, monkeypatch) -> None:
    client = _make_client(tmp_path, monkeypatch)

    owner = client.post(
        "/api/v1/auth/register",
        json={
            "email": "reset-owner@example.com",
            "fullName": "其他组织管理员",
            "phone": "13800138013",
            "password": "Password123!",
            "organizationName": "其他组织",
        },
    )
    assert owner.status_code == 200, owner.text
    owner_payload = owner.json()
    organization_id = owner_payload["user"]["organizationId"]
    headers = _auth_header(owner_payload["accessToken"])

    db = client.app.state.app_state.db
    timestamp = now_iso()
    db.execute(
        """
        INSERT INTO cloud_identities(id, email, phone_number, full_name, password_hash, last_login_at, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?, NULL, ?, ?)
        """,
        (
            "ident_reset_member",
            "reset-member@example.com",
            "+8613800138014",
            "被重置成员",
            hash_password("OldIdentity123!"),
            timestamp,
            timestamp,
        ),
    )
    db.execute(
        """
        INSERT INTO employee_accounts(
            id, identity_id, organization_id, email, phone_number, full_name, password_hash, primary_role,
            account_status, membership_status, approved_at, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "emp_reset_member",
            "ident_reset_member",
            organization_id,
            "reset-member@example.com",
            "+8613800138014",
            "被重置成员",
            hash_password("OldEmployee123!"),
            "employee",
            "approved",
            "approved",
            timestamp,
            timestamp,
            timestamp,
        ),
    )

    reset = client.post(
        "/api/v1/admin/employees/emp_reset_member/reset-password",
        json={"newPassword": "NewPassword123!"},
        headers=headers,
    )
    assert reset.status_code == 200, reset.text

    row = db.fetchone(
        """
        SELECT e.password_hash AS employee_hash, i.password_hash AS identity_hash
        FROM employee_accounts e
        JOIN cloud_identities i ON i.id = e.identity_id
        WHERE e.id = ?
        """,
        ("emp_reset_member",),
    )
    assert row is not None
    assert row["employee_hash"] == row["identity_hash"]
    assert verify_password("NewPassword123!", row["employee_hash"])
    assert verify_password("NewPassword123!", row["identity_hash"])

    login = client.post(
        "/api/v1/auth/login",
        json={"identifier": "reset-member@example.com", "password": "NewPassword123!"},
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["id"] == "emp_reset_member"
    assert login.json()["user"]["organizationId"] == organization_id
