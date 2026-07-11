from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import main as app_main  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import ObjectStorageSettingsPayload  # noqa: E402
from app.services.object_storage.settings_store import (  # noqa: E402
    get_object_storage_settings,
    save_object_storage_settings,
)
from app.services.sandbox_registry import (  # noqa: E402
    activate_sandbox,
    ensure_organization_sandbox_for_session,
    get_sandbox_setting,
    set_sandbox_setting,
)


class _JsonResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.text = self.content.decode("utf-8")
        self.headers: dict[str, str] = {}

    def json(self) -> dict[str, Any]:
        return self._payload


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(tmp_path / "data")) as test_client:
        yield test_client


def _seed_org_workspace(
    client: TestClient,
    *,
    org_id: str,
    cloud_url: str,
    role: str = "admin",
) -> str:
    db = client.app.state.app_state.db
    workspace = ensure_organization_sandbox_for_session(
        db,
        organization_id=org_id,
        organization_name=org_id,
        cloud_api_url=cloud_url,
        cloud_instance_id=f"cloud-{org_id}",
    )
    sandbox_id = workspace.id
    set_sandbox_setting(db, sandbox_id, "cloud_access_token", f"token-{org_id}")
    set_sandbox_setting(db, sandbox_id, "cloud_refresh_token", f"refresh-{org_id}")
    session_payload = json.dumps(
        {
            "id": f"user-{org_id}",
            "organizationId": org_id,
            "organizationName": org_id,
            "email": f"{org_id}@example.test",
            "fullName": f"User {org_id}",
            "primaryRole": role,
            "accountStatus": "approved",
            "membershipStatus": "approved",
        },
        ensure_ascii=False,
    )
    set_sandbox_setting(db, sandbox_id, "cloud_session_user", session_payload)
    set_sandbox_setting(db, sandbox_id, "cloud_session_user_snapshot", session_payload)
    return sandbox_id


def _storage_payload(bucket: str, *, secret: str) -> ObjectStorageSettingsPayload:
    return ObjectStorageSettingsPayload(
        provider="volcano_tos",
        credentials={"access_key_id": f"AK-{secret}", "secret_access_key": secret},
        extraConfig={"bucket": bucket, "region": "cn-beijing"},
        enabled=True,
    )


def test_cloud_sync_writes_response_to_request_start_sandbox(client: TestClient, monkeypatch) -> None:
    db = client.app.state.app_state.db
    org_a = _seed_org_workspace(
        client,
        org_id="org-a",
        cloud_url="https://org-a.example.test",
    )
    org_b = _seed_org_workspace(
        client,
        org_id="org-b",
        cloud_url="https://org-b.example.test",
    )
    save_object_storage_settings(
        db,
        _storage_payload("bucket-a-old", secret="SECRET-A-OLD"),
        now_iso="2026-07-11T10:00:00+08:00",
        sandbox_id=org_a,
    )
    save_object_storage_settings(
        db,
        _storage_payload("bucket-b", secret="SECRET-B"),
        now_iso="2026-07-11T10:00:00+08:00",
        sandbox_id=org_b,
    )
    assert client.post(f"/api/v1/workspaces/{org_a}/activate").status_code == 200

    def fake_request(method: str, url: str, **kwargs: Any) -> _JsonResponse:
        assert method == "GET"
        assert url == "https://org-a.example.test/api/v1/settings/org-object-storage-config/secret"
        assert kwargs["headers"]["Authorization"] == "Bearer token-org-a"
        # Simulate the user changing workspaces while the cloud response is in flight.
        activate_sandbox(db, org_b)
        return _JsonResponse(
            {
                "orgId": "org-a",
                "provider": "volcano_tos",
                "credentials": {"access_key_id": "AK-A-NEW", "secret_access_key": "SECRET-A-NEW"},
                "extraConfig": {"bucket": "bucket-a-new", "region": "cn-beijing"},
                "enabled": True,
                "hasCredentials": True,
                "configuredBy": "admin-a",
                "updatedAt": "2026-07-11T10:01:00+08:00",
            }
        )

    monkeypatch.setattr(app_main.httpx, "request", fake_request)

    response = client.get("/api/v1/settings/object-storage")

    assert response.status_code == 200, response.text
    assert response.json()["extraConfig"]["bucket"] == "bucket-a-new"
    record_a = get_object_storage_settings(db, sandbox_id=org_a)
    record_b = get_object_storage_settings(db, sandbox_id=org_b)
    assert record_a.extraConfig["bucket"] == "bucket-a-new"
    assert record_a.credentials["secret_access_key"] == "SECRET-A-NEW"
    assert record_b.extraConfig["bucket"] == "bucket-b"
    assert record_b.credentials["secret_access_key"] == "SECRET-B"


def test_cloud_sync_rejects_response_for_another_organization(client: TestClient, monkeypatch) -> None:
    db = client.app.state.app_state.db
    sandbox_id = _seed_org_workspace(
        client,
        org_id="org-expected",
        cloud_url="https://expected.example.test",
    )
    assert client.post(f"/api/v1/workspaces/{sandbox_id}/activate").status_code == 200
    save_object_storage_settings(
        db,
        _storage_payload("bucket-expected", secret="SECRET-EXPECTED"),
        now_iso="2026-07-11T10:00:00+08:00",
        sandbox_id=sandbox_id,
    )

    def fake_request(method: str, url: str, **kwargs: Any) -> _JsonResponse:
        assert method == "GET"
        assert url == "https://expected.example.test/api/v1/settings/org-object-storage-config/secret"
        return _JsonResponse(
            {
                "orgId": "org-unexpected",
                "provider": "volcano_tos",
                "credentials": {
                    "access_key_id": "AK-UNEXPECTED",
                    "secret_access_key": "SECRET-UNEXPECTED",
                },
                "extraConfig": {"bucket": "bucket-unexpected", "region": "cn-beijing"},
                "enabled": True,
                "hasCredentials": True,
                "updatedAt": "2026-07-11T10:01:00+08:00",
            }
        )

    monkeypatch.setattr(app_main.httpx, "request", fake_request)

    response = client.get("/api/v1/settings/object-storage")

    assert response.status_code == 200, response.text
    assert response.json()["extraConfig"]["bucket"] == "bucket-expected"
    record = get_object_storage_settings(db, sandbox_id=sandbox_id)
    assert record.extraConfig["bucket"] == "bucket-expected"
    assert record.credentials["secret_access_key"] == "SECRET-EXPECTED"


def test_member_public_sync_preserves_scoped_credentials(client: TestClient, monkeypatch) -> None:
    db = client.app.state.app_state.db
    sandbox_id = _seed_org_workspace(
        client,
        org_id="org-member",
        cloud_url="https://member.example.test",
        role="employee",
    )
    assert client.post(f"/api/v1/workspaces/{sandbox_id}/activate").status_code == 200
    save_object_storage_settings(
        db,
        _storage_payload("bucket-old", secret="SECRET-KEEP"),
        now_iso="2026-07-11T10:00:00+08:00",
        sandbox_id=sandbox_id,
    )

    def fake_request(method: str, url: str, **kwargs: Any) -> _JsonResponse:
        assert method == "GET"
        assert url == "https://member.example.test/api/v1/settings/org-object-storage-config"
        assert kwargs["headers"]["Authorization"] == "Bearer token-org-member"
        return _JsonResponse(
            {
                "orgId": "org-member",
                "provider": "volcano_tos",
                "extraConfig": {"bucket": "bucket-new", "region": "cn-beijing"},
                "enabled": True,
                "hasCredentials": True,
                "configuredBy": "admin-member",
                "updatedAt": "2026-07-11T10:02:00+08:00",
            }
        )

    monkeypatch.setattr(app_main.httpx, "request", fake_request)

    response = client.get("/api/v1/settings/object-storage")

    assert response.status_code == 200, response.text
    record = get_object_storage_settings(db, sandbox_id=sandbox_id)
    assert record.extraConfig["bucket"] == "bucket-new"
    assert record.credentials["secret_access_key"] == "SECRET-KEEP"
    assert record.hasCredentials is True


def test_volatile_cloud_session_is_frozen_for_object_storage_sync(client: TestClient, monkeypatch) -> None:
    db = client.app.state.app_state.db
    sandbox_id = _seed_org_workspace(
        client,
        org_id="org-volatile",
        cloud_url="https://volatile.example.test",
    )
    assert client.post(f"/api/v1/workspaces/{sandbox_id}/activate").status_code == 200
    session_user = get_sandbox_setting(db, sandbox_id, "cloud_session_user", "")
    set_sandbox_setting(db, sandbox_id, "cloud_access_token", "")
    set_sandbox_setting(db, sandbox_id, "cloud_refresh_token", "")
    set_sandbox_setting(db, sandbox_id, "cloud_session_user", "")
    client.app.state.app_state.volatile_cloud_sessions[sandbox_id] = {
        "cloud_access_token": "volatile-access",
        "cloud_refresh_token": "volatile-refresh",
        "cloud_session_user": session_user,
    }

    def fake_request(method: str, url: str, **kwargs: Any) -> _JsonResponse:
        assert method == "GET"
        assert url == "https://volatile.example.test/api/v1/settings/org-object-storage-config/secret"
        assert kwargs["headers"]["Authorization"] == "Bearer volatile-access"
        return _JsonResponse(
            {
                "orgId": "org-volatile",
                "provider": "volcano_tos",
                "credentials": {
                    "access_key_id": "AK-VOLATILE",
                    "secret_access_key": "SECRET-VOLATILE",
                },
                "extraConfig": {"bucket": "bucket-volatile", "region": "cn-beijing"},
                "enabled": True,
                "hasCredentials": True,
                "configuredBy": "admin-volatile",
                "updatedAt": "2026-07-11T10:03:00+08:00",
            }
        )

    monkeypatch.setattr(app_main.httpx, "request", fake_request)

    response = client.get("/api/v1/settings/object-storage")

    assert response.status_code == 200, response.text
    assert response.json()["extraConfig"]["bucket"] == "bucket-volatile"
    assert get_object_storage_settings(
        db,
        sandbox_id=sandbox_id,
    ).credentials["secret_access_key"] == "SECRET-VOLATILE"


def test_organization_storage_without_session_is_redacted_and_read_only(client: TestClient) -> None:
    db = client.app.state.app_state.db
    sandbox_id = _seed_org_workspace(
        client,
        org_id="org-logged-out",
        cloud_url="https://logged-out.example.test",
    )
    assert client.post(f"/api/v1/workspaces/{sandbox_id}/activate").status_code == 200
    save_object_storage_settings(
        db,
        _storage_payload("bucket-logged-out", secret="SECRET-LOGGED-OUT"),
        now_iso="2026-07-11T10:04:00+08:00",
        sandbox_id=sandbox_id,
    )
    set_sandbox_setting(db, sandbox_id, "cloud_access_token", "")
    set_sandbox_setting(db, sandbox_id, "cloud_refresh_token", "")
    set_sandbox_setting(db, sandbox_id, "cloud_session_user", "")
    client.app.state.app_state.volatile_cloud_sessions.pop(sandbox_id, None)

    visible = client.get("/api/v1/settings/object-storage")
    updated = client.put(
        "/api/v1/settings/object-storage",
        json=_storage_payload("bucket-overwrite", secret="SECRET-OVERWRITE").model_dump(),
    )

    assert visible.status_code == 200, visible.text
    assert visible.json()["credentials"] == {}
    assert visible.json()["hasCredentials"] is True
    assert updated.status_code == 401, updated.text
    record = get_object_storage_settings(db, sandbox_id=sandbox_id)
    assert record.extraConfig["bucket"] == "bucket-logged-out"
    assert record.credentials["secret_access_key"] == "SECRET-LOGGED-OUT"


def test_background_attachment_upload_uses_initiating_workspace(client: TestClient, monkeypatch) -> None:
    db = client.app.state.app_state.db
    org_a = _seed_org_workspace(
        client,
        org_id="org-upload-a",
        cloud_url="https://upload-a.example.test",
    )

    created_client = client.post(
        "/api/v1/clients",
        json={
            "name": "上传隔离客户",
            "alias": "",
            "domain": "测试",
            "type": "公益组织",
            "intro": "后台上传隔离测试",
            "stage": "active",
        },
    )
    assert created_client.status_code == 200, created_client.text
    client_id = str(created_client.json()["id"])
    created_line = client.post(
        "/api/v1/event-lines",
        json={"name": "上传隔离事件线", "kind": "project_line", "primaryClientId": client_id},
    )
    assert created_line.status_code == 200, created_line.text
    event_line_id = str(created_line.json()["id"])
    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "上传隔离任务",
            "desc": "验证后台上传固定发起空间",
            "priority": "normal",
            "listId": "",
            "clientId": client_id,
            "eventLineId": event_line_id,
            "sourceType": "manual",
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_id = str(created_task.json()["id"])

    org_b = _seed_org_workspace(
        client,
        org_id="org-upload-b",
        cloud_url="https://upload-b.example.test",
    )
    assert client.post(f"/api/v1/workspaces/{org_a}/activate").status_code == 200

    queued: list[tuple[Any, tuple[Any, ...], dict[str, Any]]] = []

    class QueuedThread:
        def __init__(
            self,
            *args: Any,
            target: Any = None,
            args_for_target: tuple[Any, ...] = (),
            kwargs: dict[str, Any] | None = None,
            **thread_kwargs: Any,
        ) -> None:
            del args, thread_kwargs
            self.target = target
            self.target_args = args_for_target
            self.target_kwargs = kwargs or {}

        def start(self) -> None:
            queued.append((self.target, self.target_args, self.target_kwargs))

    with monkeypatch.context() as thread_patch:
        thread_patch.setattr(app_main.threading, "Thread", QueuedThread)
        uploaded = client.post(
            f"/api/v1/tasks/{task_id}/attachments",
            files={"file": ("scope.md", b"# scoped upload", "text/markdown")},
            data={
                "clientId": client_id,
                "eventLineId": event_line_id,
                "taskTitle": "上传隔离任务",
            },
        )
    assert uploaded.status_code == 200, uploaded.text
    upload_jobs = [job for job in queued if getattr(job[0], "__name__", "") == "_bg_upload"]
    assert len(upload_jobs) == 1

    assert client.post(f"/api/v1/workspaces/{org_b}/activate").status_code == 200
    calls: list[tuple[str, str]] = []

    def fake_post(url: str, **kwargs: Any) -> _JsonResponse:
        calls.append((url, str(kwargs["headers"]["Authorization"])))
        return _JsonResponse({"ok": True})

    monkeypatch.setattr(app_main.httpx, "post", fake_post)
    target, target_args, target_kwargs = upload_jobs[0]
    target(*target_args, **target_kwargs)

    assert calls == [
        (
            f"https://upload-a.example.test/api/v1/tasks/{task_id}/attachments",
            "Bearer token-org-upload-a",
        )
    ]
