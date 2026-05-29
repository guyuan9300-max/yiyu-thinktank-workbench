from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import DEFAULT_ORG_ID, create_app, hash_password, now_iso  # noqa: E402


def make_client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(tmp_path / "cloud-data"))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    return TestClient(create_app())


def auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def seed_employee(client: TestClient, *, user_id: str, email: str, organization_id: str = DEFAULT_ORG_ID) -> None:
    timestamp = now_iso()
    client.app.state.app_state.db.execute(
        """
        INSERT INTO employee_accounts(
            id, organization_id, email, full_name, password_hash, primary_role, account_status,
            membership_status, approved_at, approved_by, recent_mentions_json, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, 'employee', 'approved', 'approved', ?, 'user_admin', '[]', ?, ?)
        """,
        (user_id, organization_id, email, f"{user_id} 用户", hash_password("Password123!"), timestamp, timestamp, timestamp),
    )


def test_admin_can_authorize_employee_for_maintenance_mode(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    seed_employee(client, user_id="user_maintainer", email="maintainer@example.com")
    admin_headers = auth_headers(client, "admin@example.org", "Admin123!")
    employee_headers = auth_headers(client, "maintainer@example.com", "Password123!")

    admin_status = client.get("/api/v1/maintenance-mode/status", headers=admin_headers)
    assert admin_status.status_code == 200
    assert admin_status.json()["canEnter"] is True
    assert admin_status.json()["canManagePermissions"] is True

    denied = client.post("/api/v1/maintenance-mode/enter", headers=employee_headers)
    assert denied.status_code == 403

    update = client.patch(
        "/api/v1/admin/maintenance-mode/members",
        headers=admin_headers,
        json={"members": [{"userId": "user_maintainer", "authorized": True, "canManagePermissions": False}]},
    )
    assert update.status_code == 200, update.text

    employee_status = client.get("/api/v1/maintenance-mode/status", headers=employee_headers)
    assert employee_status.status_code == 200
    assert employee_status.json()["canEnter"] is True
    assert employee_status.json()["canManagePermissions"] is False

    entered = client.post("/api/v1/maintenance-mode/enter", headers=employee_headers)
    assert entered.status_code == 200
    assert entered.json()["active"] is True

    revoke = client.patch(
        "/api/v1/admin/maintenance-mode/members",
        headers=admin_headers,
        json={"members": [{"userId": "user_maintainer", "authorized": False, "canManagePermissions": False}]},
    )
    assert revoke.status_code == 200, revoke.text

    revoked_status = client.get("/api/v1/maintenance-mode/status", headers=employee_headers)
    assert revoked_status.status_code == 200
    assert revoked_status.json()["canEnter"] is False


def test_maintenance_permissions_are_organization_scoped(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    timestamp = now_iso()
    db = client.app.state.app_state.db
    db.execute(
        "INSERT INTO organizations(id, name, slug, created_at, updated_at) VALUES('org_other', '其他组织', 'other-org', ?, ?)",
        (timestamp, timestamp),
    )
    seed_employee(client, user_id="user_default_employee", email="default-employee@example.com")
    db.execute(
        """
        INSERT INTO employee_accounts(
            id, organization_id, email, full_name, password_hash, primary_role, account_status,
            membership_status, approved_at, approved_by, recent_mentions_json, created_at, updated_at
        ) VALUES('user_other_admin', 'org_other', 'other-admin@example.com', '其他管理员', ?, 'admin', 'approved',
            'approved', ?, 'user_other_admin', '[]', ?, ?)
        """,
        (hash_password("Password123!"), timestamp, timestamp, timestamp),
    )
    other_headers = auth_headers(client, "other-admin@example.com", "Password123!")

    members = client.get("/api/v1/admin/maintenance-mode/members", headers=other_headers)
    assert members.status_code == 200
    assert all(item["userId"] != "user_default_employee" for item in members.json())

    cross_org_update = client.patch(
        "/api/v1/admin/maintenance-mode/members",
        headers=other_headers,
        json={"members": [{"userId": "user_default_employee", "authorized": True, "canManagePermissions": False}]},
    )
    assert cross_org_update.status_code == 404
