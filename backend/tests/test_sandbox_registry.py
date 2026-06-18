from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.sandbox_registry import (  # noqa: E402
    ACTIVE_SANDBOX_SETTING_KEY,
    DEFAULT_LOCAL_SANDBOX_ID,
    ensure_sandbox_registry,
    get_active_sandbox,
    list_sandboxes,
)


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def test_new_database_bootstraps_local_workspace(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db

    response = client.get("/api/v1/workspaces")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["activeSandboxId"] == DEFAULT_LOCAL_SANDBOX_ID
    assert len(payload["workspaces"]) == 1
    workspace = payload["workspaces"][0]
    assert workspace["id"] == DEFAULT_LOCAL_SANDBOX_ID
    assert workspace["kind"] == "local"
    assert workspace["name"] == "本机工作空间"
    assert workspace["isLegacyDefault"] is True
    assert db.get_setting(ACTIVE_SANDBOX_SETTING_KEY, "") == DEFAULT_LOCAL_SANDBOX_ID

    current = client.get("/api/v1/workspaces/current")
    assert current.status_code == 200, current.text
    assert current.json()["id"] == DEFAULT_LOCAL_SANDBOX_ID


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
    assert db.get_setting("cloud_api_url", "") == "https://cloud.example.test"
    assert db.get_setting("cloud_session_user", "") != ""


def test_registry_initialization_is_idempotent(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")

    first = ensure_sandbox_registry(db)
    second = ensure_sandbox_registry(db)
    records = list_sandboxes(db)

    assert first == second == DEFAULT_LOCAL_SANDBOX_ID
    assert len(records) == 1


def test_invalid_active_sandbox_repairs_to_existing_default(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    ensure_sandbox_registry(db)
    db.set_setting(ACTIVE_SANDBOX_SETTING_KEY, "missing_sandbox")

    repaired = ensure_sandbox_registry(db)

    assert repaired == DEFAULT_LOCAL_SANDBOX_ID
    assert db.get_setting(ACTIVE_SANDBOX_SETTING_KEY, "") == DEFAULT_LOCAL_SANDBOX_ID
