from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database  # noqa: E402
from app.main import create_app, normalize_configured_cloud_api_url  # noqa: E402
from app.services.sandbox_registry import (  # noqa: E402
    ACTIVE_SANDBOX_SETTING_KEY,
    DEFAULT_LOCAL_SANDBOX_ID,
    activate_sandbox,
    create_sandbox,
    ensure_organization_sandbox_for_session,
    ensure_sandbox_registry,
    get_active_sandbox,
    get_active_sandbox_setting,
    get_sandbox_setting,
    list_sandboxes,
    set_sandbox_setting,
)


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def test_cloud_url_normalization_defaults_public_hosts_to_https() -> None:
    assert normalize_configured_cloud_api_url("118.145.244.188.sslip.io") == "https://118.145.244.188.sslip.io"
    assert normalize_configured_cloud_api_url("cloud.example.test/") == "https://cloud.example.test"
    assert normalize_configured_cloud_api_url("http://cloud.example.test") == "http://cloud.example.test"
    assert normalize_configured_cloud_api_url("localhost:8000") == "http://localhost:8000"
    assert normalize_configured_cloud_api_url("127.0.0.1:8000") == "http://127.0.0.1:8000"


def test_new_database_bootstraps_local_workspace(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db

    response = client.get("/api/v1/workspaces")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["activeSandboxId"] == DEFAULT_LOCAL_SANDBOX_ID
    assert payload["workspaces"] == []
    assert payload["localDraftSummary"]["available"] is True
    assert payload["localDraftSummary"]["active"] is True
    assert db.get_setting(ACTIVE_SANDBOX_SETTING_KEY, "") == DEFAULT_LOCAL_SANDBOX_ID

    current = client.get("/api/v1/workspaces/current")
    assert current.status_code == 200, current.text
    assert current.json()["id"] == DEFAULT_LOCAL_SANDBOX_ID
    assert current.json()["kind"] == "local"
    assert current.json()["name"] == "未连接组织的本机草稿"


def test_existing_cloud_session_bootstraps_organization_workspace(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    db.set_setting("cloud_api_url", "https://cloud.example.test")
    db.set_setting(
        "cloud_session_user",
        json.dumps(
            {
                "id": "user_1",
                "organizationId": "org_demo",
                "organizationName": "测试组织",
                "email": "demo@example.com",
            },
            ensure_ascii=False,
        ),
    )

    active_id = ensure_sandbox_registry(db)
    active = get_active_sandbox(db)

    assert active_id == "sbx_org_org_demo"
    assert active.id == "sbx_org_org_demo"
    assert active.kind == "organization"
    assert active.name == "测试组织"
    assert active.organizationId == "org_demo"
    assert active.organizationName == "测试组织"
    assert active.cloudApiUrl == "https://cloud.example.test"
    assert get_sandbox_setting(db, active.id, "cloud_api_url", "") == "https://cloud.example.test"
    assert get_sandbox_setting(db, active.id, "cloud_session_user", "") != ""
    assert db.get_setting("cloud_api_url", "") == "https://cloud.example.test"
    assert db.get_setting("cloud_session_user", "") != ""
    records = list_sandboxes(db)
    assert all(record.kind == "organization" for record in records)


def test_registry_initialization_is_idempotent(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")

    first = ensure_sandbox_registry(db)
    second = ensure_sandbox_registry(db)
    records = list_sandboxes(db)

    assert first == second == DEFAULT_LOCAL_SANDBOX_ID
    assert records == []


def test_invalid_active_sandbox_repairs_to_existing_default(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    ensure_sandbox_registry(db)
    db.set_setting(ACTIVE_SANDBOX_SETTING_KEY, "missing_sandbox")

    repaired = ensure_sandbox_registry(db)

    assert repaired == DEFAULT_LOCAL_SANDBOX_ID
    assert db.get_setting(ACTIVE_SANDBOX_SETTING_KEY, "") == DEFAULT_LOCAL_SANDBOX_ID


def test_workspace_api_can_create_activate_and_scope_cloud_url(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    created = client.post(
        "/api/v1/workspaces",
        json={"kind": "organization", "name": "组织 A", "cloudApiUrl": "https://cloud-a.example.test"},
    )
    assert created.status_code == 200, created.text
    payload = created.json()
    active_id = payload["activeSandboxId"]
    active_workspace = next(item for item in payload["workspaces"] if item["id"] == active_id)
    assert active_workspace["name"] == "组织 A"
    assert active_workspace["cloudApiUrl"] == "https://cloud-a.example.test"

    settings = client.get("/api/v1/settings")
    assert settings.status_code == 200, settings.text
    assert settings.json()["settings"]["cloudApiUrl"] == "https://cloud-a.example.test"

    response = client.post(f"/api/v1/workspaces/{DEFAULT_LOCAL_SANDBOX_ID}/activate")
    assert response.status_code == 404, response.text
    settings = client.get("/api/v1/settings")
    assert settings.status_code == 200, settings.text
    assert settings.json()["settings"]["cloudApiUrl"] == "https://cloud-a.example.test"

    update = client.post("/api/v1/settings", json={"cloudApiUrl": "https://local-cloud.example.test"})
    assert update.status_code == 200, update.text
    assert update.json()["settings"]["cloudApiUrl"] == "https://local-cloud.example.test"

    response = client.post(f"/api/v1/workspaces/{active_id}/activate")
    assert response.status_code == 200, response.text
    settings = client.get("/api/v1/settings")
    assert settings.status_code == 200, settings.text
    assert settings.json()["settings"]["cloudApiUrl"] == "https://local-cloud.example.test"


def test_sandbox_cloud_tokens_do_not_bleed_between_workspaces(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    ensure_sandbox_registry(db)
    local_id = DEFAULT_LOCAL_SANDBOX_ID
    org = create_sandbox(db, kind="organization", name="组织 B", cloud_api_url="https://cloud-b.example.test")

    set_sandbox_setting(db, local_id, "cloud_access_token", "token-local")
    set_sandbox_setting(db, org.id, "cloud_access_token", "token-org")

    activate_sandbox(db, org.id)
    assert get_active_sandbox_setting(db, "cloud_access_token", "") == "token-org"
    assert get_sandbox_setting(db, local_id, "cloud_access_token", "") == "token-local"


def test_organization_workspace_identity_includes_cloud_url(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    ensure_sandbox_registry(db)

    first = ensure_organization_sandbox_for_session(
        db,
        organization_id="org_same_id",
        organization_name="同名组织",
        cloud_api_url="https://cloud-a.example.test/",
    )
    set_sandbox_setting(db, first.id, "cloud_access_token", "token-a")
    second = ensure_organization_sandbox_for_session(
        db,
        organization_id="org_same_id",
        organization_name="同名组织",
        cloud_api_url="https://cloud-b.example.test",
    )
    set_sandbox_setting(db, second.id, "cloud_access_token", "token-b")

    assert first.id != second.id
    assert first.organizationId == second.organizationId == "org_same_id"
    assert get_sandbox_setting(db, first.id, "cloud_api_url", "") == "https://cloud-a.example.test"
    assert get_sandbox_setting(db, second.id, "cloud_api_url", "") == "https://cloud-b.example.test"

    again = ensure_organization_sandbox_for_session(
        db,
        organization_id="org_same_id",
        organization_name="同名组织",
        cloud_api_url="https://cloud-a.example.test",
    )
    assert again.id == first.id
    assert get_active_sandbox_setting(db, "cloud_access_token", "") == "token-a"


def test_new_workspace_does_not_inherit_legacy_global_cloud_token(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    db.set_setting("cloud_access_token", "legacy-token")
    ensure_sandbox_registry(db)
    assert get_sandbox_setting(db, DEFAULT_LOCAL_SANDBOX_ID, "cloud_access_token", "") == "legacy-token"

    org = create_sandbox(db, kind="organization", name="新组织", cloud_api_url="https://new-cloud.example.test")
    activate_sandbox(db, org.id)

    assert get_active_sandbox_setting(db, "cloud_access_token", "") == ""
    assert get_sandbox_setting(db, DEFAULT_LOCAL_SANDBOX_ID, "cloud_access_token", "") == "legacy-token"


def test_workspace_update_does_not_change_other_workspace_cloud_url(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    first = client.post(
        "/api/v1/workspaces",
        json={"kind": "organization", "name": "组织 C", "cloudApiUrl": "https://cloud-c.example.test"},
    ).json()
    org_id = first["activeSandboxId"]

    response = client.patch(f"/api/v1/workspaces/{org_id}", json={"cloudApiUrl": "https://cloud-c2.example.test"})
    assert response.status_code == 200, response.text
    current = client.get("/api/v1/workspaces/current").json()
    assert current["cloudApiUrl"] == "https://cloud-c2.example.test"

    response = client.post(f"/api/v1/workspaces/{DEFAULT_LOCAL_SANDBOX_ID}/activate")
    assert response.status_code == 404, response.text
    current = client.get("/api/v1/workspaces/current").json()
    assert current["id"] == org_id
    assert current["cloudApiUrl"] == "https://cloud-c2.example.test"


def test_cloud_logout_clears_only_active_workspace_cloud_session(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    local_user_id = "local-user-1"
    db.execute(
        """
        INSERT INTO local_identities(
            id, email, phone_number, full_name, password_hash, local_organization_name,
            organization_mode, pending_invite_code, pending_department_id, job_title,
            manager_name, current_focus, membership_status, bound_cloud_user_id,
            bound_cloud_organization_id, bound_cloud_email, created_at, updated_at, last_login_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            local_user_id,
            "local@example.com",
            None,
            "本机用户",
            "hash",
            "本机组织",
            "create",
            None,
            None,
            None,
            None,
            "",
            "approved",
            None,
            None,
            None,
            "2026-06-18T00:00:00+00:00",
            "2026-06-18T00:00:00+00:00",
            None,
        ),
    )
    db.set_setting("local_session_user_id", local_user_id)
    active_org = create_sandbox(db, kind="organization", name="组织 D", cloud_api_url="https://cloud-d.example.test")
    other_org = create_sandbox(db, kind="organization", name="组织 E", cloud_api_url="https://cloud-e.example.test")
    set_sandbox_setting(db, active_org.id, "cloud_access_token", "token-active")
    set_sandbox_setting(db, active_org.id, "cloud_refresh_token", "refresh-active")
    set_sandbox_setting(db, other_org.id, "cloud_access_token", "token-other")
    activate_sandbox(db, active_org.id)
    client.app.state.app_state.cloud_api_url = "https://cloud-d.example.test"

    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 200, response.text
    assert response.json()["sessionMode"] == "local"
    assert response.json()["authenticated"] is True
    assert response.json()["localIdentityStatus"] in {"draft", "ready"}
    assert db.get_setting("local_session_user_id", "") == local_user_id
    assert get_sandbox_setting(db, active_org.id, "cloud_access_token", "") == ""
    assert get_sandbox_setting(db, active_org.id, "cloud_refresh_token", "") == ""
    assert get_sandbox_setting(db, other_org.id, "cloud_access_token", "") == "token-other"


def test_local_identity_is_bound_to_local_workspace_not_org_workspace(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db

    local = client.post(
        "/api/v1/local-auth/register",
        json={
            "email": "workspace-local@example.com",
            "phone": "13800138008",
            "fullName": "本机空间用户",
            "password": "Password123!",
            "organizationMode": "create",
            "organizationName": "本机个人空间",
        },
    )
    assert local.status_code == 200, local.text
    local_user_id = local.json()["user"]["id"]
    current = client.get("/api/v1/workspaces/current").json()
    assert current["id"] == DEFAULT_LOCAL_SANDBOX_ID
    assert current["localIdentityId"] == local_user_id

    org = create_sandbox(db, kind="organization", name="组织 F", cloud_api_url="https://cloud-f.example.test")
    activate_sandbox(db, org.id)

    auth_in_org = client.get("/api/v1/auth/me")
    assert auth_in_org.status_code == 200, auth_in_org.text
    assert auth_in_org.json()["authenticated"] is True
    assert auth_in_org.json()["sessionMode"] == "local"
    assert auth_in_org.json()["localIdentityStatus"] in {"draft", "ready"}

    response = client.post(f"/api/v1/workspaces/{DEFAULT_LOCAL_SANDBOX_ID}/activate")
    assert response.status_code == 404, response.text
