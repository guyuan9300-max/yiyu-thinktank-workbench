from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import DEFAULT_ORG_ID, _department_invite_code, create_app, now_iso  # noqa: E402


def make_client(tmp_path, monkeypatch) -> TestClient:
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Member123!")
    return TestClient(create_app())


def seed_department(app) -> None:
    timestamp = now_iso()
    app.state.app_state.db.execute(
        """
        INSERT OR REPLACE INTO org_departments(id, organization_id, name, color, active, updated_at)
        VALUES('dept_customer_service', ?, '客户服务部', '#14B8A6', 1, ?)
        """,
        (DEFAULT_ORG_ID, timestamp),
    )


def auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def member_headers(client: TestClient) -> dict[str, str]:
    invite_code = _department_invite_code(
        "dept_customer_service",
        organization_id=DEFAULT_ORG_ID,
        organization_name="益语智库",
        department_name="客户服务部",
        order=3,
    )
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "object-storage-member@example.com",
            "fullName": "对象存储测试成员",
            "phone": "13900139001",
            "password": "Member123!",
            "inviteCode": invite_code,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["user"]["membershipStatus"] == "approved"
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_admin_writes_and_member_reads_object_storage_secret(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    seed_department(client.app)
    admin_headers = auth_headers(client, "admin@yiyu-system.com", "Admin123!")

    saved = client.post(
        "/api/v1/settings/org-object-storage-config",
        headers=admin_headers,
        json={
            "provider": "volcano_tos",
            "credentials": {"access_key_id": "AK", "secret_access_key": "SK"},
            "extraConfig": {"endpoint": "tos-cn-beijing.volces.com", "region": "cn-beijing", "bucket": "yiyu-files"},
            "enabled": True,
        },
    )
    assert saved.status_code == 200, saved.text
    payload = saved.json()
    assert payload["provider"] == "volcano_tos"
    assert payload["enabled"] is True
    assert payload["hasCredentials"] is True
    assert "credentials" not in payload

    member_auth = member_headers(client)
    visible = client.get("/api/v1/settings/org-object-storage-config", headers=member_auth)
    assert visible.status_code == 200, visible.text
    assert visible.json()["hasCredentials"] is True
    assert "credentials" not in visible.json()

    forbidden_secret = client.get("/api/v1/settings/org-object-storage-config/secret", headers=member_auth)
    assert forbidden_secret.status_code == 403, forbidden_secret.text

    secret = client.get("/api/v1/settings/org-object-storage-config/secret", headers=admin_headers)
    assert secret.status_code == 200, secret.text
    secret_payload = secret.json()
    assert secret_payload["credentials"] == {"access_key_id": "AK", "secret_access_key": "SK"}
    assert secret_payload["extraConfig"]["bucket"] == "yiyu-files"

    updated = client.post(
        "/api/v1/settings/org-object-storage-config",
        headers=admin_headers,
        json={
            "provider": "volcano_tos",
            "credentials": {},
            "extraConfig": {"endpoint": "tos-cn-beijing.volces.com", "region": "cn-beijing", "bucket": "yiyu-files-next"},
            "enabled": True,
        },
    )
    assert updated.status_code == 200, updated.text
    preserved_secret = client.get("/api/v1/settings/org-object-storage-config/secret", headers=admin_headers)
    assert preserved_secret.status_code == 200, preserved_secret.text
    assert preserved_secret.json()["credentials"] == {"access_key_id": "AK", "secret_access_key": "SK"}
    assert preserved_secret.json()["extraConfig"]["bucket"] == "yiyu-files-next"


def test_member_cannot_update_org_object_storage(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    seed_department(client.app)
    member_auth = member_headers(client)

    response = client.post(
        "/api/v1/settings/org-object-storage-config",
        headers=member_auth,
        json={
            "provider": "volcano_tos",
            "credentials": {"access_key_id": "AK", "secret_access_key": "SK"},
            "extraConfig": {"bucket": "yiyu-files"},
            "enabled": True,
        },
    )
    assert response.status_code == 403
