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
    clear_active_cloud_session,
    create_sandbox,
    ensure_organization_sandbox_for_session,
    ensure_sandbox_registry,
    get_active_sandbox,
    get_active_sandbox_setting,
    get_sandbox_local_identity_id,
    get_sandbox_setting,
    list_sandboxes,
    set_sandbox_setting,
)
from app.services.workspace_context import load_workspace_context  # noqa: E402


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
    assert current.json()["runtimeStatus"] == "local_draft"
    assert current.json()["requiresLogin"] is False


def test_workspace_current_reports_needs_login_for_existing_org_without_token(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    created = client.post(
        "/api/v1/workspaces",
        json={"kind": "organization", "name": "星丛", "cloudApiUrl": "https://star.example.test"},
    )
    assert created.status_code == 200, created.text

    current = client.get("/api/v1/workspaces/current")
    assert current.status_code == 200, current.text
    payload = current.json()
    assert payload["kind"] == "organization"
    assert payload["runtimeStatus"] == "needs_login"
    assert payload["requiresLogin"] is True
    assert "重新登录" in payload["statusMessage"] or "云端地址" in payload["statusMessage"]


def test_explicit_missing_workspace_context_does_not_fallback_to_local(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db

    ctx = load_workspace_context(db, "sbx_missing_target")

    assert ctx.sandbox_id == "sbx_missing_target"
    assert ctx.kind == "missing"
    assert ctx.identity_state == "error"
    assert "不存在" in ctx.identity_error


def test_workspace_current_reports_ready_when_org_has_session_token(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    workspace = ensure_organization_sandbox_for_session(
        db,
        organization_id="org_a",
        organization_name="组织 A",
        cloud_api_url="https://cloud-a.example.test",
    )
    active_id = workspace.id
    set_sandbox_setting(db, active_id, "cloud_access_token", "token-a")
    set_sandbox_setting(
        db,
        active_id,
        "cloud_session_user",
        json.dumps(
            {
                "id": "user_a",
                "organizationId": "org_a",
                "organizationName": "组织 A",
                "email": "a@example.test",
                "fullName": "用户 A",
            },
            ensure_ascii=False,
        ),
    )

    current = client.get("/api/v1/workspaces/current")
    assert current.status_code == 200, current.text
    payload = current.json()
    assert payload["runtimeStatus"] == "ready"
    assert payload["requiresLogin"] is False
    assert payload["sessionSnapshot"]["fullName"] == "用户 A"


def test_workspace_current_reports_identity_error_for_mismatched_identity(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    org = create_sandbox(db, kind="organization", name="组织 B", cloud_api_url="https://cloud-b.example.test")
    db.execute(
        """
        UPDATE sandboxes
           SET identity_state = 'mismatch',
               identity_error = '云实例或组织身份不一致'
         WHERE id = ?
        """,
        (org.id,),
    )
    activate_sandbox(db, org.id)

    current = client.get("/api/v1/workspaces/current")
    assert current.status_code == 200, current.text
    payload = current.json()
    assert payload["runtimeStatus"] == "identity_error"
    assert payload["requiresLogin"] is False
    assert "不一致" in payload["statusMessage"]


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


def test_organization_workspace_identity_prefers_cloud_instance_over_url(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    ensure_sandbox_registry(db)

    first = ensure_organization_sandbox_for_session(
        db,
        organization_id="org_same_id",
        organization_name="同名组织",
        cloud_api_url="https://cloud.example.test",
        cloud_instance_id="cloud_instance_a",
    )
    set_sandbox_setting(db, first.id, "cloud_access_token", "token-a")

    second = ensure_organization_sandbox_for_session(
        db,
        organization_id="org_same_id",
        organization_name="同名组织",
        cloud_api_url="https://cloud.example.test",
        cloud_instance_id="cloud_instance_b",
    )
    set_sandbox_setting(db, second.id, "cloud_access_token", "token-b")

    assert first.id != second.id
    assert first.organizationId == second.organizationId == "org_same_id"
    assert first.cloudInstanceId == "cloud_instance_a"
    assert second.cloudInstanceId == "cloud_instance_b"

    again = ensure_organization_sandbox_for_session(
        db,
        organization_id="org_same_id",
        organization_name="同名组织",
        cloud_api_url="https://cloud.example.test",
        cloud_instance_id="cloud_instance_a",
    )
    assert again.id == first.id
    assert get_active_sandbox_setting(db, "cloud_access_token", "") == "token-a"


def test_verified_identity_archives_sessionless_legacy_shell(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    ensure_sandbox_registry(db)
    stale = ensure_organization_sandbox_for_session(
        db,
        organization_id="org_target",
        organization_name="目标组织",
        cloud_api_url="https://wrong-cloud.example.test",
    )
    verified = ensure_organization_sandbox_for_session(
        db,
        organization_id="org_target",
        organization_name="目标组织",
        cloud_api_url="https://right-cloud.example.test",
        cloud_instance_id="cloud-instance-target",
    )
    assert verified.id != stale.id
    assert verified.cloudInstanceId == "cloud-instance-target"

    visible_ids = {item.id for item in list_sandboxes(db)}
    assert stale.id not in visible_ids
    stale_row = db.fetchone("SELECT status, metadata_json FROM sandboxes WHERE id = ?", (stale.id,))
    assert stale_row is not None
    assert stale_row["status"] == "archived"
    assert json.loads(stale_row["metadata_json"])["archivedReason"] == "superseded_unverified_org_shell"


def test_verified_identity_archives_legacy_shell_using_another_cloud_endpoint(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    ensure_sandbox_registry(db)
    endpoint_owner = ensure_organization_sandbox_for_session(
        db,
        organization_id="org_endpoint_owner",
        organization_name="云端所属组织",
        cloud_api_url="https://first-cloud.example.test",
        cloud_instance_id="cloud-instance-first",
    )
    stale = ensure_organization_sandbox_for_session(
        db,
        organization_id="org_target",
        organization_name="目标组织",
        cloud_api_url="https://first-cloud.example.test",
    )
    set_sandbox_setting(db, stale.id, "cloud_access_token", "stale-token")
    set_sandbox_setting(db, stale.id, "cloud_refresh_token", "stale-refresh")
    verified = ensure_organization_sandbox_for_session(
        db,
        organization_id="org_target",
        organization_name="目标组织",
        cloud_api_url="https://second-cloud.example.test",
        cloud_instance_id="cloud-instance-second",
    )

    assert verified.id != stale.id
    visible_ids = {item.id for item in list_sandboxes(db)}
    assert endpoint_owner.id in visible_ids
    assert verified.id in visible_ids
    assert stale.id not in visible_ids
    stale_row = db.fetchone("SELECT status, metadata_json FROM sandboxes WHERE id = ?", (stale.id,))
    assert stale_row is not None
    assert stale_row["status"] == "archived"
    metadata = json.loads(stale_row["metadata_json"])
    assert metadata["archivedReason"] == "superseded_conflicting_cloud_endpoint"
    assert metadata["conflictingEndpointOwnerSandboxId"] == endpoint_owner.id


def test_new_workspace_does_not_inherit_legacy_global_cloud_token(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    db.set_setting("cloud_access_token", "legacy-token")
    ensure_sandbox_registry(db)
    assert get_sandbox_setting(db, DEFAULT_LOCAL_SANDBOX_ID, "cloud_access_token", "") == ""

    org = create_sandbox(db, kind="organization", name="新组织", cloud_api_url="https://new-cloud.example.test")
    activate_sandbox(db, org.id)

    assert get_active_sandbox_setting(db, "cloud_access_token", "") == ""
    assert get_sandbox_setting(db, DEFAULT_LOCAL_SANDBOX_ID, "cloud_access_token", "") == ""


def test_matching_legacy_cloud_session_repairs_non_legacy_org_workspace(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    ensure_sandbox_registry(db)
    yiyu = ensure_organization_sandbox_for_session(
        db,
        organization_id="org_yiyu_default",
        organization_name="益语智库",
        cloud_api_url="http://192.0.2.10",
    )
    set_sandbox_setting(db, yiyu.id, "cloud_access_token", "token-yiyu")
    set_sandbox_setting(db, yiyu.id, "cloud_refresh_token", "refresh-yiyu")
    set_sandbox_setting(
        db,
        yiyu.id,
        "cloud_session_user",
        json.dumps(
            {
                "id": "emp_yiyu",
                "organizationId": "org_yiyu_default",
                "organizationName": "益语智库",
                "email": "user@example.test",
                "fullName": "用户",
                "primaryRole": "employee",
                "accountStatus": "approved",
                "membershipStatus": "approved",
            },
            ensure_ascii=False,
        ),
    )
    xingcong = ensure_organization_sandbox_for_session(
        db,
        organization_id="org_xingcong",
        organization_name="星丛",
        cloud_api_url="http://118.145.244.188",
    )
    set_sandbox_setting(db, xingcong.id, "cloud_access_token", "")
    set_sandbox_setting(db, xingcong.id, "cloud_refresh_token", "")
    set_sandbox_setting(db, xingcong.id, "cloud_session_user", get_sandbox_setting(db, yiyu.id, "cloud_session_user", ""))
    db.set_setting("cloud_api_url", "http://118.145.244.188")
    db.set_setting("cloud_access_token", "token-xingcong")
    db.set_setting("cloud_refresh_token", "refresh-xingcong")
    db.set_setting(
        "cloud_session_user",
        json.dumps(
            {
                "id": "emp_xingcong",
                "organizationId": "org_xingcong",
                "organizationName": "星丛",
                "email": "user@example.test",
                "fullName": "用户",
                "primaryRole": "admin",
                "accountStatus": "approved",
                "membershipStatus": "approved",
            },
            ensure_ascii=False,
        ),
    )

    activate_sandbox(db, xingcong.id)

    assert get_active_sandbox_setting(db, "cloud_access_token", "") == "token-xingcong"
    assert get_active_sandbox_setting(db, "cloud_refresh_token", "") == "refresh-xingcong"
    assert json.loads(get_active_sandbox_setting(db, "cloud_session_user", ""))["organizationId"] == "org_xingcong"
    assert json.loads(get_sandbox_setting(db, yiyu.id, "cloud_session_user", ""))["organizationId"] == "org_yiyu_default"


def test_mismatched_workspace_session_is_not_reported_connected(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    ensure_sandbox_registry(db)
    workspace = ensure_organization_sandbox_for_session(
        db,
        organization_id="org_xingcong",
        organization_name="星丛",
        cloud_api_url="http://118.145.244.188",
    )
    set_sandbox_setting(db, workspace.id, "cloud_access_token", "token-wrong")
    set_sandbox_setting(db, workspace.id, "cloud_refresh_token", "refresh-wrong")
    set_sandbox_setting(
        db,
        workspace.id,
        "cloud_session_user",
        json.dumps(
            {
                "id": "emp_yiyu",
                "organizationId": "org_yiyu_default",
                "organizationName": "益语智库",
                "email": "user@example.test",
                "fullName": "用户",
                "primaryRole": "employee",
                "accountStatus": "approved",
                "membershipStatus": "approved",
            },
            ensure_ascii=False,
        ),
    )

    active = get_active_sandbox(db)

    assert active.id == workspace.id
    assert active.cloudConnected is False
    assert active.cloudConnectionStatus == "needs_login"
    assert active.cloudUserFullName is None
    assert active.sessionSnapshot["fullName"] == "用户"
    assert active.runtimeStatus == "identity_error"


def test_clearing_cloud_session_keeps_last_session_snapshot_for_relogin_state(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    workspace = ensure_organization_sandbox_for_session(
        db,
        organization_id="org_snapshot",
        organization_name="快照组织",
        cloud_api_url="https://snapshot.example.test",
    )
    session_payload = json.dumps(
        {
            "id": "emp_snapshot",
            "organizationId": "org_snapshot",
            "organizationName": "快照组织",
            "email": "snapshot@example.test",
            "fullName": "快照用户",
            "primaryRole": "employee",
            "accountStatus": "approved",
            "membershipStatus": "approved",
        },
        ensure_ascii=False,
    )
    set_sandbox_setting(db, workspace.id, "cloud_access_token", "token")
    set_sandbox_setting(db, workspace.id, "cloud_refresh_token", "refresh")
    set_sandbox_setting(db, workspace.id, "cloud_session_user", session_payload)
    set_sandbox_setting(db, workspace.id, "cloud_session_user_snapshot", session_payload)

    clear_active_cloud_session(db)
    active = get_active_sandbox(db)

    assert active.id == workspace.id
    assert active.runtimeStatus == "needs_login"
    assert active.cloudUserFullName is None
    assert active.sessionSnapshot["fullName"] == "快照用户"


def test_workspace_diagnostics_report_session_integrity_without_token_values(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    workspace = ensure_organization_sandbox_for_session(
        db,
        organization_id="org_diag",
        organization_name="诊断组织",
        cloud_api_url="https://diag.example.test",
        cloud_instance_id="cli_diag",
    )
    set_sandbox_setting(db, workspace.id, "cloud_access_token", "secret-access-token")
    set_sandbox_setting(db, workspace.id, "cloud_refresh_token", "secret-refresh-token")
    set_sandbox_setting(
        db,
        workspace.id,
        "cloud_session_user",
        json.dumps(
            {
                "id": "emp_diag",
                "organizationId": "org_diag",
                "organizationName": "诊断组织",
                "email": "diag@example.test",
                "fullName": "诊断用户",
                "primaryRole": "admin",
                "accountStatus": "approved",
                "membershipStatus": "approved",
            },
            ensure_ascii=False,
        ),
    )

    response = client.get("/api/v1/workspaces/diagnostics")

    assert response.status_code == 200, response.text
    payload = response.json()
    record = next(item for item in payload["workspaces"] if item["sandboxId"] == workspace.id)
    assert record["hasAccessToken"] is True
    assert record["hasRefreshToken"] is True
    assert record["sessionUserFullName"] == "诊断用户"
    assert "secret-access-token" not in response.text
    assert "secret-refresh-token" not in response.text


def test_auth_me_in_org_workspace_without_token_does_not_fall_back_to_local_draft(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    created = client.post(
        "/api/v1/workspaces",
        json={"kind": "organization", "name": "星丛", "cloudApiUrl": "http://118.145.244.188"},
    )
    assert created.status_code == 200, created.text

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["authenticated"] is False
    assert payload["sessionMode"] == "cloud"
    assert payload["user"] is None
    assert "本机草稿" not in (payload.get("message") or "")


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
    active_org = ensure_organization_sandbox_for_session(
        db,
        organization_id="org_logout_d",
        organization_name="组织 D",
        cloud_api_url="https://cloud-d.example.test",
        cloud_instance_id="cloud-d",
    )
    other_org = ensure_organization_sandbox_for_session(
        db,
        organization_id="org_logout_e",
        organization_name="组织 E",
        cloud_api_url="https://cloud-e.example.test",
        cloud_instance_id="cloud-e",
    )
    set_sandbox_setting(db, active_org.id, "cloud_access_token", "token-active")
    set_sandbox_setting(db, active_org.id, "cloud_refresh_token", "refresh-active")
    set_sandbox_setting(db, other_org.id, "cloud_access_token", "token-other")
    for workspace, organization_id, organization_name in (
        (active_org, "org_logout_d", "组织 D"),
        (other_org, "org_logout_e", "组织 E"),
    ):
        set_sandbox_setting(
            db,
            workspace.id,
            "cloud_session_user",
            json.dumps(
                {
                    "id": f"user_{organization_id}",
                    "organizationId": organization_id,
                    "organizationName": organization_name,
                    "email": f"{organization_id}@example.test",
                    "fullName": f"{organization_name}用户",
                    "primaryRole": "admin",
                    "accountStatus": "approved",
                    "membershipStatus": "approved",
                },
                ensure_ascii=False,
            ),
        )
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
    assert auth_in_org.json()["authenticated"] is False
    assert auth_in_org.json()["sessionMode"] == "cloud"
    assert auth_in_org.json()["user"] is None
    assert get_sandbox_local_identity_id(db, DEFAULT_LOCAL_SANDBOX_ID) == local_user_id

    response = client.post(f"/api/v1/workspaces/{DEFAULT_LOCAL_SANDBOX_ID}/activate")
    assert response.status_code == 404, response.text
