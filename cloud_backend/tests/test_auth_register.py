from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import DEFAULT_ORG_ID, create_app  # noqa: E402
from app.security import hash_password  # noqa: E402


def test_register_returns_tokens_and_allows_immediate_login(tmp_path, monkeypatch):
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Qinghua123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Jianing123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Yishuo123!")

    client = TestClient(create_app())

    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new-personal-user@example.com",
            "fullName": "个人注册用户",
            "password": "Password123!",
        },
    )
    assert register.status_code == 200, register.text
    payload = register.json()
    assert payload["accessToken"]
    assert payload["refreshToken"]
    assert payload["user"]["email"] == "new-personal-user@example.com"
    assert payload["user"]["accountStatus"] == "approved"

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "new-personal-user@example.com",
            "password": "Password123!",
        },
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["email"] == "new-personal-user@example.com"


def test_legacy_pending_account_can_login_without_manual_approval(tmp_path, monkeypatch):
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Qinghua123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Jianing123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Yishuo123!")

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
    assert login.json()["user"]["accountStatus"] == "approved"

    row = db.fetchone("SELECT account_status, approved_at FROM employee_accounts WHERE id = ?", ("emp_legacy_pending",))
    assert row is not None
    assert row["account_status"] == "approved"
    assert row["approved_at"]
