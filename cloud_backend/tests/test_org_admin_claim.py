from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app, new_id, now_iso  # noqa: E402
from app.security import hash_password  # noqa: E402


def make_client(tmp_path, monkeypatch) -> TestClient:
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    return TestClient(create_app())


def register_user(client: TestClient, email: str) -> tuple[dict[str, str], dict]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "phone": "13800138009",
            "fullName": email.split("@", 1)[0],
            "password": "Password123!",
            "organizationName": f"{email.split('@', 1)[0]} 的组织",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    return {"Authorization": f"Bearer {payload['accessToken']}"}, payload["user"]


def seed_employee(client: TestClient, *, organization_id: str, email: str, status: str = "approved") -> str:
    user_id = new_id("emp")
    timestamp = now_iso()
    client.app.state.app_state.db.execute(
        """
        INSERT INTO employee_accounts(
            id, organization_id, email, full_name, password_hash, primary_role,
            account_status, membership_status, approved_at, approved_by,
            disabled_at, recent_mentions_json, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, 'employee', ?, 'approved', ?, NULL, NULL, '[]', ?, ?)
        """,
        (
            user_id,
            organization_id,
            email,
            email.split("@", 1)[0],
            hash_password("Password123!"),
            status,
            timestamp if status == "approved" else None,
            timestamp,
            timestamp,
        ),
    )
    return user_id


def test_user_can_claim_admin_when_organization_has_no_admin(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    headers, user = register_user(client, "claim-owner@example.com")

    status = client.get("/api/v1/me/org-membership/admin-claim-status", headers=headers)
    assert status.status_code == 200, status.text
    assert status.json()["hasAdmin"] is True
    assert status.json()["canClaim"] is False
    assert user["primaryRole"] == "admin"
    assert user["accountStatus"] == "approved"
    assert user["membershipStatus"] == "approved"

    row = client.app.state.app_state.db.fetchone("SELECT primary_role, account_status, membership_status FROM employee_accounts WHERE id = ?", (user["id"],))
    assert row["primary_role"] == "admin"
    assert row["account_status"] == "approved"
    assert row["membership_status"] == "approved"


def test_second_user_cannot_claim_after_admin_exists(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    owner_headers, owner = register_user(client, "claim-first@example.com")

    second_user_id = seed_employee(client, organization_id=owner["organizationId"], email="claim-second@example.com")
    login = client.post("/api/v1/auth/login", json={"email": "claim-second@example.com", "password": "Password123!"})
    assert login.status_code == 200, login.text
    second_headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}

    status = client.get("/api/v1/me/org-membership/admin-claim-status", headers=second_headers)
    assert status.status_code == 200, status.text
    assert status.json()["hasAdmin"] is True
    assert status.json()["canClaim"] is False

    claim = client.post("/api/v1/me/org-membership/admin-claim", headers=second_headers)
    assert claim.status_code == 409
    assert "已存在管理员" in claim.text

    row = client.app.state.app_state.db.fetchone("SELECT primary_role FROM employee_accounts WHERE id = ?", (second_user_id,))
    assert row["primary_role"] == "employee"


def test_rejected_user_cannot_claim_admin(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    headers, user = register_user(client, "claim-rejected@example.com")
    client.app.state.app_state.db.execute(
        "UPDATE employee_accounts SET account_status = 'rejected', membership_status = 'rejected' WHERE id = ?",
        (user["id"],),
    )

    status = client.get("/api/v1/me/org-membership/admin-claim-status", headers=headers)
    assert status.status_code == 200, status.text
    assert status.json()["canClaim"] is False

    claim = client.post("/api/v1/me/org-membership/admin-claim", headers=headers)
    assert claim.status_code == 403


def test_membership_rejected_user_cannot_claim_admin(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    headers, user = register_user(client, "claim-membership-rejected@example.com")
    client.app.state.app_state.db.execute(
        "UPDATE employee_accounts SET account_status = 'approved', membership_status = 'rejected' WHERE id = ?",
        (user["id"],),
    )

    status = client.get("/api/v1/me/org-membership/admin-claim-status", headers=headers)
    assert status.status_code == 200, status.text
    assert status.json()["canClaim"] is False

    claim = client.post("/api/v1/me/org-membership/admin-claim", headers=headers)
    assert claim.status_code == 403
