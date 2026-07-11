from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.sandbox_registry import (  # noqa: E402
    DEFAULT_LOCAL_SANDBOX_ID,
    activate_sandbox,
    ensure_organization_sandbox_for_session,
    set_active_sandbox_setting,
)


CLOUD_API_URL = "https://cloud.example.test"
CLOUD_TOKEN = "cloud-token-not-for-urls"


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        content: bytes = b"",
        headers: dict[str, str] | None = None,
        payload: dict | None = None,
    ) -> None:
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


def _configure_cloud(client: TestClient, token: str) -> None:
    state = client.app.state.app_state
    state.cloud_api_url = CLOUD_API_URL
    set_active_sandbox_setting(state.db, "cloud_access_token", token)


def _seed_event_line(
    client: TestClient,
    event_line_id: str,
    sandbox_id: str = DEFAULT_LOCAL_SANDBOX_ID,
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO event_lines(
            id, name, kind, status, sandbox_id, created_at, updated_at
        ) VALUES(?, '附件鉴权导出测试', 'project_line', 'active', ?, ?, ?)
        """,
        (
            event_line_id,
            sandbox_id,
            "2026-07-11T10:00:00",
            "2026-07-11T10:00:00",
        ),
    )


def _seed_event_attachment(client: TestClient, attachment_id: str, event_line_id: str) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO event_line_attachments(
            id, event_line_id, file_name, file_type, uploaded_at, local_path
        ) VALUES(?, ?, ?, 'bin', ?, '')
        """,
        (
            attachment_id,
            event_line_id,
            f"{attachment_id}.bin",
            "2026-07-11T10:00:00",
        ),
    )


def _create_workspace(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/v1/workspaces",
        json={
            "kind": "organization",
            "name": name,
            "cloudApiUrl": f"https://{name}.example.test",
        },
    )
    assert response.status_code == 200, response.text
    sandbox_id = str(response.json()["activeSandboxId"])
    # Organization workspaces used by cloud-proxy tests must carry the same
    # identity contract as a real post-login workspace.  A bare token on an
    # organization-less sandbox is intentionally rejected by the production
    # fail-closed session guard.
    state = client.app.state.app_state
    organization_id = f"org_{name.replace('-', '_')}"
    state.db.execute(
        "UPDATE sandboxes SET organization_id = ? WHERE id = ?",
        (organization_id, sandbox_id),
    )
    set_active_sandbox_setting(
        state.db,
        "cloud_session_user",
        json.dumps(
            {
                "id": f"user_{organization_id}",
                "organizationId": organization_id,
                "organizationName": f"测试组织 {organization_id}",
                "email": f"{organization_id}@example.test",
                "fullName": f"用户 {organization_id}",
                "primaryRole": "employee",
                "accountStatus": "approved",
                "membershipStatus": "approved",
            },
            ensure_ascii=False,
        ),
    )
    return sandbox_id


def _create_client_and_task(client: TestClient, suffix: str) -> tuple[str, str]:
    client_response = client.post(
        "/api/v1/clients",
        json={
            "name": f"附件沙箱客户 {suffix}",
            "alias": "",
            "domain": "attachment-scope-test",
            "type": "公益组织",
            "intro": "attachment scope test",
            "stage": "active",
            "color": "#5B7BFE",
        },
    )
    assert client_response.status_code == 200, client_response.text
    client_id = str(client_response.json()["id"])
    task_response = client.post(
        "/api/v1/tasks",
        json={
            "title": f"附件沙箱任务 {suffix}",
            "desc": "attachment scope test",
            "priority": "normal",
            "listId": "",
            "clientId": client_id,
            "sourceType": "manual",
        },
    )
    assert task_response.status_code == 200, task_response.text
    return client_id, str(task_response.json()["id"])


def _activate_organization_workspace(
    client: TestClient,
    *,
    organization_id: str,
    cloud_api_url: str,
) -> str:
    state = client.app.state.app_state
    workspace = ensure_organization_sandbox_for_session(
        state.db,
        organization_id=organization_id,
        organization_name=f"测试组织 {organization_id}",
        cloud_api_url=cloud_api_url,
    )
    session_user = {
        "id": f"user_{organization_id}",
        "organizationId": organization_id,
        "organizationName": f"测试组织 {organization_id}",
        "email": f"{organization_id}@example.test",
        "fullName": f"用户 {organization_id}",
        "primaryRole": "employee",
        "accountStatus": "approved",
        "membershipStatus": "approved",
    }
    set_active_sandbox_setting(state.db, "cloud_access_token", f"token_{organization_id}")
    set_active_sandbox_setting(
        state.db,
        "cloud_session_user",
        json.dumps(session_user, ensure_ascii=False),
    )
    return workspace.id


def _word_export_draft() -> dict:
    return {
        "eventLineName": "附件鉴权导出测试",
        "summary": "验证云端附件读取只使用 Bearer 请求头。",
        "snapshotAt": "2026-07-11T10:00:00",
        # A filtered system node prevents the snapshot fallback request while
        # preserving the legacy activity/attachment rendering path below.
        "timelineNodes": [{"kind": "system_trace", "title": "系统痕迹"}],
        "activities": [
            {
                "id": "activity_auth",
                "sourceType": "manual_note",
                "title": "附件验证",
                "summary": "展开图片和文档摘要。",
                "happenedAt": "2026-07-11T09:00:00",
                "metadata": {"taskId": "task_auth"},
            }
        ],
        "attachments": [
            {
                "id": "attachment_image_auth",
                "taskId": "task_auth",
                "title": "evidence.png",
                "mimeType": "image/png",
                "sizeBytes": 16,
                "downloadUrl": "/api/public/task-attachments/attachment_image_auth",
            },
            {
                "id": "attachment_doc_auth",
                "taskId": "task_auth",
                "title": "brief.docx",
                "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "sizeBytes": 32,
                "downloadUrl": "/api/public/task-attachments/attachment_doc_auth",
            },
        ],
        "tasks": [],
        "imagesExpandedActivityIds": ["activity_auth"],
        "docsExpandedActivityIds": ["activity_auth"],
    }


def test_attachment_cloud_proxies_forward_bearer_header(tmp_path: Path, monkeypatch) -> None:
    app = create_app(tmp_path / "data")
    calls: list[tuple[str, dict]] = []

    def fake_get(url: str, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/thumbnail"):
            return FakeResponse(content=b"jpeg", headers={"content-type": "image/jpeg"})
        if url.endswith("/text-content"):
            return FakeResponse(payload={"title": "brief.docx", "text": "summary"})
        return FakeResponse(payload={"title": "scan.png", "summary": "ocr result"})

    monkeypatch.setattr(app_main.httpx, "get", fake_get)
    with TestClient(app) as client:
        _configure_cloud(client, CLOUD_TOKEN)
        _seed_event_line(client, "event_line_proxy_auth")
        for attachment_id in ("proxy_thumb_auth", "proxy_text_auth", "proxy_ocr_auth"):
            _seed_event_attachment(client, attachment_id, "event_line_proxy_auth")

        thumbnail = client.get("/api/public/task-attachments/proxy_thumb_auth/thumbnail")
        text = client.get("/api/public/task-attachments/proxy_text_auth/text-content")
        ocr = client.get("/api/public/task-attachments/proxy_ocr_auth/ocr-summary")

    assert thumbnail.status_code == 200, thumbnail.text
    assert text.status_code == 200, text.text
    assert ocr.status_code == 200, ocr.text
    assert len(calls) == 3
    for url, kwargs in calls:
        assert kwargs["headers"] == {"Authorization": f"Bearer {CLOUD_TOKEN}"}
        assert CLOUD_TOKEN not in url


def test_attachment_binary_proxy_rejects_cloud_redirect(tmp_path: Path, monkeypatch) -> None:
    app = create_app(tmp_path / "data")

    def fake_get(url: str, **kwargs):
        return FakeResponse(
            status_code=302,
            headers={"location": "https://untrusted.example.test/leak"},
        )

    monkeypatch.setattr(app_main.httpx, "get", fake_get)
    with TestClient(app) as client:
        _configure_cloud(client, CLOUD_TOKEN)
        _seed_event_line(client, "event_line_redirect")
        _seed_event_attachment(client, "attachment_redirect", "event_line_redirect")
        response = client.get("/api/public/task-attachments/attachment_redirect")

    assert response.status_code == 502
    assert "untrusted.example.test" not in response.text


def test_attachment_cloud_proxies_without_token_make_no_request(tmp_path: Path, monkeypatch) -> None:
    app = create_app(tmp_path / "data")
    calls: list[str] = []

    def forbidden_get(url: str, **kwargs):
        calls.append(url)
        raise AssertionError("anonymous cloud request must not be sent")

    monkeypatch.setattr(app_main.httpx, "get", forbidden_get)
    with TestClient(app) as client:
        _configure_cloud(client, "")
        _seed_event_line(client, "event_line_no_token")
        for attachment_id in ("no_token_thumb", "no_token_text", "no_token_ocr"):
            _seed_event_attachment(client, attachment_id, "event_line_no_token")

        thumbnail = client.get("/api/public/task-attachments/no_token_thumb/thumbnail")
        text = client.get("/api/public/task-attachments/no_token_text/text-content")
        ocr = client.get("/api/public/task-attachments/no_token_ocr/ocr-summary")

    assert thumbnail.status_code == 404
    assert text.status_code == 404
    assert ocr.status_code == 200
    assert ocr.json()["unsupported"] is True
    assert calls == []


def test_attachment_cache_and_all_public_routes_are_sandbox_scoped(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    app = create_app(data_dir)
    calls: list[str] = []

    def fake_get(url: str, **kwargs):
        calls.append(url)
        if url.endswith("/thumbnail"):
            return FakeResponse(content=b"sandbox-a-thumbnail", headers={"content-type": "image/jpeg"})
        if url.endswith("/text-content"):
            text = "sandbox-b-text" if "scope_b_attachment" in url else "sandbox-a-text"
            return FakeResponse(payload={"title": "scope.txt", "text": text})
        if url.endswith("/ocr-summary"):
            return FakeResponse(payload={"title": "scope.png", "summary": "sandbox-a-ocr"})
        return FakeResponse(
            content=b"sandbox-a-binary",
            headers={"content-type": "application/octet-stream"},
        )

    monkeypatch.setattr(app_main.httpx, "get", fake_get)
    with TestClient(app) as client:
        _configure_cloud(client, CLOUD_TOKEN)
        _seed_event_line(client, "event_line_scope_a")
        _seed_event_attachment(client, "scope_a_attachment", "event_line_scope_a")

        legacy_cache_dir = data_dir / "cache" / "event-line-attachments"
        legacy_cache_dir.mkdir(parents=True, exist_ok=True)
        (legacy_cache_dir / "scope_a_attachment.text.json").write_text(
            json.dumps({"text": "legacy-unscoped-secret"}),
            encoding="utf-8",
        )

        binary = client.get("/api/public/task-attachments/scope_a_attachment")
        thumbnail = client.get("/api/public/task-attachments/scope_a_attachment/thumbnail")
        text_response = client.get("/api/public/task-attachments/scope_a_attachment/text-content")
        ocr = client.get("/api/public/task-attachments/scope_a_attachment/ocr-summary")

        assert binary.status_code == 200 and binary.content == b"sandbox-a-binary"
        assert thumbnail.status_code == 200 and thumbnail.content == b"sandbox-a-thumbnail"
        assert text_response.status_code == 200
        assert text_response.json()["text"] == "sandbox-a-text"
        assert "legacy-unscoped-secret" not in text_response.text
        assert ocr.status_code == 200 and ocr.json()["summary"] == "sandbox-a-ocr"
        assert len(calls) == 4

        sandbox_b = _create_workspace(client, "attachment-cache-b")
        calls_before_cross_scope_reads = list(calls)
        for suffix in ("", "/thumbnail", "/text-content", "/ocr-summary"):
            response = client.get(f"/api/public/task-attachments/scope_a_attachment{suffix}")
            assert response.status_code == 404, (suffix, response.status_code, response.text)
            assert "sandbox-a" not in response.text
        assert calls == calls_before_cross_scope_reads

        _configure_cloud(client, CLOUD_TOKEN)
        _seed_event_line(client, "event_line_scope_b", sandbox_b)
        _seed_event_attachment(client, "scope_b_attachment", "event_line_scope_b")
        b_text = client.get("/api/public/task-attachments/scope_b_attachment/text-content")
        assert b_text.status_code == 200, b_text.text
        assert b_text.json()["text"] == "sandbox-b-text"

    scoped_root = data_dir / "cache" / "event-line-attachments" / "scoped"
    sandbox_a_component = hashlib.sha256(DEFAULT_LOCAL_SANDBOX_ID.encode()).hexdigest()
    sandbox_b_component = hashlib.sha256(sandbox_b.encode()).hexdigest()
    attachment_a_component = hashlib.sha256(b"scope_a_attachment").hexdigest()
    attachment_b_component = hashlib.sha256(b"scope_b_attachment").hexdigest()
    assert (scoped_root / sandbox_a_component / f"{attachment_a_component}.text.json").is_file()
    assert (scoped_root / sandbox_b_component / f"{attachment_b_component}.text.json").is_file()
    assert sandbox_a_component != sandbox_b_component


def test_all_local_attachment_tables_fail_closed_after_sandbox_switch(tmp_path: Path, monkeypatch) -> None:
    app = create_app(tmp_path / "data")
    cloud_calls: list[str] = []

    def forbidden_get(url: str, **kwargs):
        cloud_calls.append(url)
        raise AssertionError("cross-sandbox attachment must not reach cloud")

    monkeypatch.setattr(app_main.httpx, "get", forbidden_get)
    with TestClient(app) as client:
        sandbox_a = _create_workspace(client, "attachment-parent-a")
        client_id, task_id = _create_client_and_task(client, "A")
        _seed_event_line(client, "event_line_parent_a", sandbox_a)
        db = client.app.state.app_state.db
        timestamp = "2026-07-11T10:00:00"
        common = (
            task_id,
            client_id,
            "event_line_parent_a",
            None,
            "scope.txt",
            "",
            "txt",
            "test",
            0,
            timestamp,
        )
        db.execute(
            """
            INSERT INTO task_attachments(
                id, task_id, client_id, event_line_id, document_id, title, path,
                kind, source, size_bytes, created_at
            ) VALUES('local_task_attachment_a', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            common,
        )
        db.execute(
            """
            INSERT INTO task_attachments_cloud(
                id, task_id, client_id, event_line_id, document_id, title, path,
                kind, source, size_bytes, created_at
            ) VALUES('cloud_task_attachment_a', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            common,
        )
        _seed_event_attachment(client, "event_attachment_a", "event_line_parent_a")

        _create_workspace(client, "attachment-parent-b")
        for attachment_id in (
            "local_task_attachment_a",
            "cloud_task_attachment_a",
            "event_attachment_a",
        ):
            response = client.get(f"/api/public/task-attachments/{attachment_id}")
            assert response.status_code == 404, (attachment_id, response.status_code, response.text)
        assert cloud_calls == []


def test_cloud_only_attachment_requires_scoped_parent_binding(tmp_path: Path, monkeypatch) -> None:
    app = create_app(tmp_path / "data")
    attachment_calls: list[str] = []
    snapshot_calls: list[str] = []

    snapshot_payload = {
        "eventLine": {
            "id": "event_line_cloud_only",
            "name": "Cloud-only attachment scope",
            "kind": "project_line",
            "status": "active",
        },
        "attachments": [
            {
                "id": "cloud_only_attachment",
                "sourceKind": "task_attachment",
                "title": "cloud-only.txt",
            }
        ],
        "tasks": [],
        "activities": [],
        "snapshotAt": "2026-07-11T10:00:00",
    }

    def fake_request(method: str, url: str, **kwargs):
        snapshot_calls.append(url)
        return FakeResponse(content=b"json", payload=snapshot_payload)

    def fake_get(url: str, **kwargs):
        attachment_calls.append(url)
        return FakeResponse(content=b"cloud-only-content", headers={"content-type": "text/plain"})

    monkeypatch.setattr(app_main.httpx, "request", fake_request)
    monkeypatch.setattr(app_main.httpx, "get", fake_get)
    with TestClient(app) as client:
        sandbox_id = _activate_organization_workspace(
            client,
            organization_id="org_cloud_only_attachment",
            cloud_api_url=CLOUD_API_URL,
        )
        _configure_cloud(client, CLOUD_TOKEN)
        _seed_event_line(client, "event_line_cloud_only", sandbox_id)

        unbound = client.get("/api/public/task-attachments/cloud_only_attachment")
        assert unbound.status_code == 404
        assert attachment_calls == []

        snapshot = client.get("/api/v1/event-lines/event_line_cloud_only/report-snapshot")
        assert snapshot.status_code == 200, snapshot.text
        assert snapshot_calls == [f"{CLOUD_API_URL}/api/v1/event-lines/event_line_cloud_only/report-snapshot"]

        bound = client.get("/api/public/task-attachments/cloud_only_attachment")
        assert bound.status_code == 200, bound.text
        assert bound.content == b"cloud-only-content"
        assert len(attachment_calls) == 1

        _create_workspace(client, "attachment-cloud-only-b")
        cross_scope = client.get("/api/public/task-attachments/cloud_only_attachment")
        assert cross_scope.status_code == 404
        assert len(attachment_calls) == 1


def test_report_snapshot_attachment_id_collision_cannot_leak_or_overwrite_foreign_document(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = create_app(tmp_path / "data")
    snapshot_payload: dict = {}
    snapshot_calls: list[str] = []
    download_calls: list[str] = []

    def fake_request(method: str, url: str, **kwargs):
        snapshot_calls.append(url)
        return FakeResponse(content=b"json", payload=snapshot_payload)

    def forbidden_download(url: str, **kwargs):
        download_calls.append(url)
        raise AssertionError("foreign attachment id collision must fail before download")

    monkeypatch.setattr(app_main.httpx, "request", fake_request)
    monkeypatch.setattr(app_main.httpx, "get", forbidden_download)
    with TestClient(app) as client:
        sandbox_a = _create_workspace(client, "report-snapshot-a")
        client_a, _task_a = _create_client_and_task(client, "report snapshot A")
        event_a_response = client.post(
            "/api/v1/event-lines",
            json={
                "name": "A report event",
                "kind": "project_line",
                "primaryClientId": client_a,
            },
        )
        assert event_a_response.status_code == 200, event_a_response.text
        event_a_id = str(event_a_response.json()["id"])

        db = client.app.state.app_state.db
        timestamp = "2026-07-11T10:00:00"
        db.execute(
            """
            INSERT INTO documents(
                id, client_id, folder_id, title, path, original_source_path,
                kind, source, excerpt, tags_json, created_at
            ) VALUES(
                'report_collision_document_a', ?, NULL, 'A secret report', '', '',
                'md', 'test', 'sandbox-a-report-excerpt-secret', '[]', ?
            )
            """,
            (client_a, timestamp),
        )
        db.execute(
            """
            INSERT INTO v2_documents(
                id, client_id, document_id, original_path, managed_path,
                markdown_path, file_name, kind, parse_status, preview_text,
                markdown_content, chunk_count, section_count, imported_at, updated_at
            ) VALUES(
                'report_collision_v2_a', ?, 'report_collision_document_a', '', '',
                NULL, 'a-secret.md', 'md', 'completed',
                'sandbox-a-report-preview-secret',
                'sandbox-a-report-markdown-secret', 3, 2, ?, ?
            )
            """,
            (client_a, timestamp, timestamp),
        )
        db.execute(
            """
            INSERT INTO event_line_attachments(
                id, event_line_id, document_id, file_name, file_type,
                uploaded_at, local_path
            ) VALUES(
                'shared_report_attachment_id', ?, 'report_collision_document_a',
                'a-secret.md', 'md', ?, ''
            )
            """,
            (event_a_id, timestamp),
        )

        sandbox_b = _create_workspace(client, "report-snapshot-b")
        assert sandbox_b != sandbox_a
        client_b, _task_b = _create_client_and_task(client, "report snapshot B")
        event_b_response = client.post(
            "/api/v1/event-lines",
            json={
                "name": "B report event",
                "kind": "project_line",
                "primaryClientId": client_b,
            },
        )
        assert event_b_response.status_code == 200, event_b_response.text
        event_b_id = str(event_b_response.json()["id"])
        _configure_cloud(client, CLOUD_TOKEN)
        snapshot_payload.update(
            {
                "eventLine": {
                    "id": event_b_id,
                    "name": "B report event",
                    "kind": "project_line",
                    "status": "active",
                },
                "attachments": [
                    {
                        "id": "shared_report_attachment_id",
                        "sourceKind": "event_line_attachment",
                        "title": "b-cloud.md",
                        "downloadUrl": (
                            "https://report-snapshot-b.example.test/api/public/"
                            "task-attachments/shared_report_attachment_id"
                        ),
                    }
                ],
                "tasks": [],
                "activities": [],
                "snapshotAt": timestamp,
            }
        )

        response = client.get(f"/api/v1/event-lines/{event_b_id}/report-snapshot")

        assert response.status_code == 200, response.text
        assert snapshot_calls == [
            f"https://report-snapshot-b.example.test/api/v1/event-lines/{event_b_id}/report-snapshot"
        ]
        assert download_calls == []
        assert "sandbox-a-report" not in response.text
        returned_attachment = response.json()["attachments"][0]
        assert returned_attachment.get("documentId") is None
        assert returned_attachment.get("parseStatus") == "missing_document"
        preserved = db.fetchone(
            """
            SELECT event_line_id, document_id
            FROM event_line_attachments
            WHERE id = 'shared_report_attachment_id'
            """
        )
        assert preserved is not None
        assert str(preserved["event_line_id"]) == event_a_id
        assert str(preserved["document_id"]) == "report_collision_document_a"


def test_report_snapshot_rejects_cross_origin_attachment_download(tmp_path: Path, monkeypatch) -> None:
    app = create_app(tmp_path / "data")
    snapshot_payload: dict = {}
    download_calls: list[str] = []

    def fake_request(method: str, url: str, **kwargs):
        return FakeResponse(content=b"json", payload=snapshot_payload)

    def forbidden_download(url: str, **kwargs):
        download_calls.append(url)
        raise AssertionError("cross-origin report attachment must not be downloaded")

    monkeypatch.setattr(app_main.httpx, "request", fake_request)
    monkeypatch.setattr(app_main.httpx, "get", forbidden_download)
    with TestClient(app) as client:
        _create_workspace(client, "report-origin-guard")
        client_id, _task_id = _create_client_and_task(client, "report origin guard")
        event_response = client.post(
            "/api/v1/event-lines",
            json={
                "name": "Origin guard event",
                "kind": "project_line",
                "primaryClientId": client_id,
            },
        )
        assert event_response.status_code == 200, event_response.text
        event_line_id = str(event_response.json()["id"])
        _configure_cloud(client, CLOUD_TOKEN)
        snapshot_payload.update(
            {
                "eventLine": {
                    "id": event_line_id,
                    "name": "Origin guard event",
                    "kind": "project_line",
                    "status": "active",
                },
                "attachments": [
                    {
                        "id": "cross_origin_report_attachment",
                        "sourceKind": "event_line_attachment",
                        "title": "private.txt",
                        "downloadUrl": "http://127.0.0.1:8000/private-data",
                    }
                ],
                "tasks": [],
                "activities": [],
                "snapshotAt": "2026-07-11T10:00:00",
            }
        )
        before_documents = int(
            client.app.state.app_state.db.scalar("SELECT COUNT(*) FROM documents") or 0
        )

        response = client.get(f"/api/v1/event-lines/{event_line_id}/report-snapshot")

        assert response.status_code == 200, response.text
        assert download_calls == []
        assert response.json()["attachments"][0].get("parseStatus") == "missing_document"
        assert int(
            client.app.state.app_state.db.scalar("SELECT COUNT(*) FROM documents") or 0
        ) == before_documents


def test_report_snapshot_same_origin_attachment_is_scoped_cached_and_ingested(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir = tmp_path / "data"
    app = create_app(data_dir)
    snapshot_payload: dict = {}
    download_calls: list[tuple[str, dict]] = []

    def fake_request(method: str, url: str, **kwargs):
        return FakeResponse(content=b"json", payload=snapshot_payload)

    def fake_download(url: str, **kwargs):
        download_calls.append((url, kwargs))
        return FakeResponse(
            content="same workspace cloud evidence".encode(),
            headers={"content-type": "text/plain"},
        )

    monkeypatch.setattr(app_main.httpx, "request", fake_request)
    monkeypatch.setattr(app_main.httpx, "get", fake_download)
    with TestClient(app) as client:
        sandbox_id = _create_workspace(client, "report-origin-success")
        client_id, _task_id = _create_client_and_task(client, "report origin success")
        event_response = client.post(
            "/api/v1/event-lines",
            json={
                "name": "Origin success event",
                "kind": "project_line",
                "primaryClientId": client_id,
            },
        )
        assert event_response.status_code == 200, event_response.text
        event_line_id = str(event_response.json()["id"])
        _configure_cloud(client, CLOUD_TOKEN)
        snapshot_payload.update(
            {
                "eventLine": {
                    "id": event_line_id,
                    "name": "Origin success event",
                    "kind": "project_line",
                    "status": "active",
                },
                "attachments": [
                    {
                        "id": "same_origin_report_attachment",
                        "sourceKind": "event_line_attachment",
                        "title": "evidence.txt",
                        "kind": "txt",
                        "downloadUrl": (
                            "https://report-origin-success.example.test/api/public/"
                            "task-attachments/same_origin_report_attachment"
                        ),
                    }
                ],
                "tasks": [],
                "activities": [],
                "snapshotAt": "2026-07-11T10:00:00",
            }
        )

        response = client.get(f"/api/v1/event-lines/{event_line_id}/report-snapshot")

        assert response.status_code == 200, response.text
        assert len(download_calls) == 1
        download_url, download_kwargs = download_calls[0]
        assert download_url.startswith("https://report-origin-success.example.test/")
        assert download_kwargs["headers"] == {"Authorization": f"Bearer {CLOUD_TOKEN}"}
        assert download_kwargs["follow_redirects"] is False
        attachment = response.json()["attachments"][0]
        assert attachment.get("documentId")
        stored = client.app.state.app_state.db.fetchone(
            """
            SELECT a.event_line_id, a.document_id, d.client_id, d.path
            FROM event_line_attachments a
            JOIN documents d ON d.id = a.document_id
            WHERE a.id = 'same_origin_report_attachment'
            """
        )
        assert stored is not None
        assert str(stored["event_line_id"]) == event_line_id
        assert str(stored["client_id"]) == client_id
        assert str(stored["document_id"]) == str(attachment["documentId"])
        managed_path = Path(str(stored["path"]))
        assert managed_path.is_file() and not managed_path.is_symlink()
        assert managed_path.read_bytes() == b"same workspace cloud evidence"
        sandbox_component = hashlib.sha256(sandbox_id.encode()).hexdigest()
        attachment_component = hashlib.sha256(b"same_origin_report_attachment").hexdigest()
        cached_path = (
            data_dir
            / "cache"
            / "event-line-attachments"
            / "scoped"
            / sandbox_component
            / attachment_component
        )
        assert cached_path.is_file() and not cached_path.is_symlink()
        assert cached_path.read_bytes() == b"same workspace cloud evidence"


def test_smart_brief_uses_scoped_task_parents_not_payload_hints(tmp_path: Path) -> None:
    app = create_app(tmp_path / "data")
    with TestClient(app) as client:
        sandbox_a = _create_workspace(client, "smart-brief-parent-a")
        client_a, _task_a = _create_client_and_task(client, "smart brief A")
        event_a = client.post(
            "/api/v1/event-lines",
            json={"name": "A event", "kind": "project_line", "primaryClientId": client_a},
        )
        assert event_a.status_code == 200, event_a.text
        event_a_id = str(event_a.json()["id"])

        sandbox_b = _create_workspace(client, "smart-brief-parent-b")
        client_b, task_b = _create_client_and_task(client, "smart brief B")
        event_b = client.post(
            "/api/v1/event-lines",
            json={"name": "B event", "kind": "project_line", "primaryClientId": client_b},
        )
        assert event_b.status_code == 200, event_b.text
        event_b_id = str(event_b.json()["id"])

        db = client.app.state.app_state.db
        db.execute(
            "UPDATE event_lines SET summary = ? WHERE id = ?",
            ("sandbox-a-foreign-progress-secret", event_a_id),
        )
        db.execute(
            "UPDATE event_lines SET summary = ? WHERE id = ?",
            ("sandbox-b-authoritative-progress", event_b_id),
        )
        db.execute(
            "UPDATE tasks SET event_line_id = ? WHERE id = ?",
            (event_b_id, task_b),
        )

        response = client.post(
            "/api/v1/tasks/smart-briefs",
            json={
                "tasks": [
                    {
                        "id": task_b,
                        "title": "Scoped smart brief",
                        "desc": "",
                        "clientId": client_a,
                        "eventLineId": event_a_id,
                        "attachmentTitles": ["trigger.md"],
                    }
                ]
            },
        )

        assert sandbox_a != sandbox_b
        assert response.status_code == 200, response.text
        assert len(response.json()) == 1
        assert "sandbox-b-authoritative-progress" in response.json()[0]["summary"]
        assert "sandbox-a-foreign-progress-secret" not in response.text


def test_smart_brief_never_reads_legacy_unscoped_cache(tmp_path: Path) -> None:
    app = create_app(tmp_path / "data")
    with TestClient(app) as client:
        _create_workspace(client, "smart-brief-cache-scope")
        _client_id, task_id = _create_client_and_task(client, "smart brief cache")
        client.app.state.app_state.db.set_setting(
            f"smart_brief_cache::{task_id}",
            json.dumps(
                {
                    "taskId": task_id,
                    "summary": "legacy-unscoped-smart-brief-secret",
                    "summarySourceLabels": ["legacy"],
                    "actionItems": [],
                }
            ),
        )

        response = client.post(
            "/api/v1/tasks/smart-briefs",
            json={
                "tasks": [
                    {
                        "id": task_id,
                        "title": "No context",
                        "desc": "",
                        "attachmentTitles": [],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert "legacy-unscoped-smart-brief-secret" not in response.text


def test_cloud_only_upload_validates_parents_before_any_local_write(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    app = create_app(data_dir)
    with TestClient(app) as client:
        _create_workspace(client, "upload-parent-a")
        client_a, _task_a = _create_client_and_task(client, "upload A")
        event_a = client.post(
            "/api/v1/event-lines",
            json={"name": "Upload A event", "kind": "project_line", "primaryClientId": client_a},
        )
        assert event_a.status_code == 200, event_a.text
        event_a_id = str(event_a.json()["id"])

        _create_workspace(client, "upload-parent-b")
        client_b, _task_b = _create_client_and_task(client, "upload B")
        db = client.app.state.app_state.db
        before_documents = int(db.scalar("SELECT COUNT(*) FROM documents") or 0)
        before_folders = int(db.scalar("SELECT COUNT(*) FROM client_folders") or 0)

        blocked_requests = (
            ("foreign-event.md", client_b, event_a_id),
            ("foreign-client.md", client_a, None),
        )
        for filename, client_id, event_line_id in blocked_requests:
            form = {"clientId": client_id, "taskTitle": "Cloud-only blocked upload"}
            if event_line_id:
                form["eventLineId"] = event_line_id
            response = client.post(
                "/api/v1/tasks/cloud-only-unverified-task/attachments",
                files={"file": (filename, b"must-not-be-written", "text/markdown")},
                data=form,
            )
            assert response.status_code == 404, (filename, response.status_code, response.text)

        assert int(db.scalar("SELECT COUNT(*) FROM documents") or 0) == before_documents
        assert int(db.scalar("SELECT COUNT(*) FROM client_folders") or 0) == before_folders
        assert db.scalar(
            "SELECT COUNT(*) FROM task_attachments_cloud WHERE task_id = ?",
            ("cloud-only-unverified-task",),
        ) == 0
        assert not list(data_dir.rglob("foreign-event.md"))
        assert not list(data_dir.rglob("foreign-client.md"))


def test_attachment_v2_document_cannot_cross_workspace_parent_chain(tmp_path: Path, monkeypatch) -> None:
    app = create_app(tmp_path / "data")
    cloud_calls: list[str] = []

    def forbidden_get(url: str, **kwargs):
        cloud_calls.append(url)
        raise AssertionError("foreign v2 document must fail before cloud proxy")

    monkeypatch.setattr(app_main.httpx, "get", forbidden_get)
    with TestClient(app) as client:
        _create_workspace(client, "v2-document-parent-a")
        client_a, _task_a = _create_client_and_task(client, "v2 A")
        db = client.app.state.app_state.db
        timestamp = "2026-07-11T10:00:00"
        db.execute(
            """
            INSERT INTO documents(
                id, client_id, folder_id, title, path, original_source_path,
                kind, source, excerpt, tags_json, created_at
            ) VALUES('document_v2_scope_a', ?, NULL, 'A secret', '', '',
                     'md', 'test', 'sandbox-a-document-secret', '[]', ?)
            """,
            (client_a, timestamp),
        )
        db.execute(
            """
            INSERT INTO v2_documents(
                id, client_id, document_id, original_path, managed_path,
                markdown_path, file_name, kind, preview_text,
                markdown_content, imported_at, updated_at
            ) VALUES(
                'v2_scope_a', ?, 'document_v2_scope_a', '', '', NULL,
                'a-secret.md', 'md', 'sandbox-a-v2-preview-secret',
                'sandbox-a-v2-markdown-secret', ?, ?
            )
            """,
            (client_a, timestamp, timestamp),
        )

        _create_workspace(client, "v2-document-parent-b")
        client_b, task_b = _create_client_and_task(client, "v2 B")
        db.execute(
            """
            INSERT INTO task_attachments(
                id, task_id, client_id, event_line_id, document_id, title,
                path, kind, source, size_bytes, created_at
            ) VALUES(
                'attachment_v2_cross_scope', ?, ?, NULL,
                'document_v2_scope_a', 'foreign-v2.md', '', 'md', 'test', 0, ?
            )
            """,
            (task_b, client_b, timestamp),
        )

        response = client.get(
            "/api/public/task-attachments/attachment_v2_cross_scope/text-content"
        )
        assert response.status_code == 404, response.text
        assert "sandbox-a" not in response.text
        assert cloud_calls == []


def test_attachment_cache_symlink_is_replaced_without_reading_or_overwriting_target(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir = tmp_path / "data"
    app = create_app(data_dir)
    calls: list[str] = []

    def fake_get(url: str, **kwargs):
        calls.append(url)
        return FakeResponse(payload={"title": "safe.txt", "text": "safe-cloud-text"})

    monkeypatch.setattr(app_main.httpx, "get", fake_get)
    with TestClient(app) as client:
        _configure_cloud(client, CLOUD_TOKEN)
        _seed_event_line(client, "event_line_symlink")
        _seed_event_attachment(client, "attachment_symlink", "event_line_symlink")

        scope_component = hashlib.sha256(DEFAULT_LOCAL_SANDBOX_ID.encode()).hexdigest()
        attachment_component = hashlib.sha256(b"attachment_symlink").hexdigest()
        scoped_dir = (
            data_dir
            / "cache"
            / "event-line-attachments"
            / "scoped"
            / scope_component
        )
        scoped_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
        external_target = tmp_path / "external-cache-target.json"
        external_secret = json.dumps({"text": "external-symlink-secret"})
        external_target.write_text(external_secret, encoding="utf-8")
        cache_link = scoped_dir / f"{attachment_component}.text.json"
        cache_link.symlink_to(external_target)

        response = client.get(
            "/api/public/task-attachments/attachment_symlink/text-content"
        )

        assert response.status_code == 200, response.text
        assert response.json()["text"] == "safe-cloud-text"
        assert "external-symlink-secret" not in response.text
        assert external_target.read_text(encoding="utf-8") == external_secret
        assert cache_link.is_file() and not cache_link.is_symlink()
        assert json.loads(cache_link.read_text(encoding="utf-8"))["text"] == "safe-cloud-text"
        assert len(calls) == 1


def test_cloud_event_detail_does_not_merge_foreign_same_id_attachment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = create_app(tmp_path / "data")
    calls: list[tuple[str, dict]] = []

    def fake_request(method: str, url: str, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(
            content=b"{}",
            payload={
                "eventLine": {
                    "id": "shared_cloud_event_id",
                    "name": "B 组织事件线",
                    "kind": "project_line",
                    "status": "active",
                    "organizationId": "org_attachment_b",
                    "createdAt": "2026-07-11T10:00:00",
                    "updatedAt": "2026-07-11T10:00:00",
                },
                "tasks": [],
                "activities": [],
            },
        )

    monkeypatch.setattr(app_main.httpx, "request", fake_request)
    with TestClient(app) as client:
        state = client.app.state.app_state
        scoped_sandbox_id = _activate_organization_workspace(
            client,
            organization_id="org_attachment_b",
            cloud_api_url="https://org-b.example.test",
        )
        foreign_sandbox_id = _activate_organization_workspace(
            client,
            organization_id="org_attachment_a",
            cloud_api_url="https://org-a.example.test",
        )
        set_active_sandbox_setting(state.db, "cloud_access_token", "")
        foreign_client_id, foreign_task_id = _create_client_and_task(client, "foreign-event-detail")
        _seed_event_line(client, "shared_cloud_event_id", foreign_sandbox_id)
        state.db.execute(
            """
            INSERT INTO task_attachments_cloud(
                id, task_id, client_id, event_line_id, document_id,
                title, path, kind, source, size_bytes, created_at
            ) VALUES(?, ?, ?, ?, NULL, ?, ?, 'file', 'cloud', 16, ?)
            """,
            (
                "foreign_same_id_activity",
                foreign_task_id,
                foreign_client_id,
                "shared_cloud_event_id",
                "A 组织机密附件.txt",
                str(tmp_path / "a-org-secret.txt"),
                "2026-07-11T10:00:00",
            ),
        )
        activate_sandbox(state.db, scoped_sandbox_id)

        response = client.get(
            "/api/v1/reviews/dashboard/drill-target",
            params={"targetType": "event_line", "targetId": "shared_cloud_event_id"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["eventLineDetail"]["eventLine"]["name"] == "B 组织事件线"
    assert all(
        activity["title"] != "上传附件：A 组织机密附件.txt"
        for activity in response.json()["eventLineDetail"]["activities"]
    )
    detail_calls = [
        call
        for call in calls
        if call[0].endswith("/api/v1/event-lines/shared_cloud_event_id")
    ]
    assert len(detail_calls) == 1
    assert detail_calls[0][1]["headers"] == {
        "Authorization": "Bearer token_org_attachment_b"
    }


def test_attachment_group_drill_rejects_foreign_ids_and_event_line_hints(
    tmp_path: Path,
) -> None:
    app = create_app(tmp_path / "data")

    with TestClient(app) as client:
        state = client.app.state.app_state
        scoped_sandbox_id = _activate_organization_workspace(
            client,
            organization_id="org_attachment_group_b",
            cloud_api_url="https://attachment-group-b.example.test",
        )
        foreign_sandbox_id = _activate_organization_workspace(
            client,
            organization_id="org_attachment_group_a",
            cloud_api_url="https://attachment-group-a.example.test",
        )
        set_active_sandbox_setting(state.db, "cloud_access_token", "")
        foreign_client_id, foreign_task_id = _create_client_and_task(
            client,
            "foreign-attachment-group",
        )
        foreign_event_line_id = "foreign_attachment_group_event"
        foreign_attachment_id = "foreign_attachment_group_id"
        _seed_event_line(client, foreign_event_line_id, foreign_sandbox_id)
        state.db.execute(
            """
            INSERT INTO task_attachments_cloud(
                id, task_id, client_id, event_line_id, document_id,
                title, path, kind, source, size_bytes, created_at
            ) VALUES(?, ?, ?, ?, NULL, ?, ?, 'file', 'cloud', 23, ?)
            """,
            (
                foreign_attachment_id,
                foreign_task_id,
                foreign_client_id,
                foreign_event_line_id,
                "A 组织附件组机密.txt",
                str(tmp_path / "foreign-attachment-group-secret.txt"),
                "2026-07-11T10:00:00",
            ),
        )

        activate_sandbox(state.db, scoped_sandbox_id)
        set_active_sandbox_setting(state.db, "cloud_access_token", "")
        by_id = client.get(
            "/api/v1/reviews/dashboard/drill-target",
            params={
                "targetType": "attachment_group",
                "targetId": "crafted-attachment-group",
                "targetFilters": json.dumps(
                    {"attachmentIds": [foreign_attachment_id]},
                    ensure_ascii=False,
                ),
            },
        )
        by_event_line = client.get(
            "/api/v1/reviews/dashboard/drill-target",
            params={
                "targetType": "attachment_group",
                "targetId": "crafted-event-attachment-group",
                "targetFilters": json.dumps(
                    {"eventLineId": foreign_event_line_id},
                    ensure_ascii=False,
                ),
            },
        )

    assert by_id.status_code == 200, by_id.text
    assert by_event_line.status_code == 200, by_event_line.text
    assert by_id.json()["attachments"] == []
    assert by_event_line.json()["attachments"] == []
    assert "A 组织附件组机密" not in by_id.text
    assert "A 组织附件组机密" not in by_event_line.text


def test_local_report_snapshot_rejects_foreign_attachment_ids_from_activity_metadata(
    tmp_path: Path,
) -> None:
    app = create_app(tmp_path / "data")

    with TestClient(app) as client:
        state = client.app.state.app_state
        scoped_sandbox_id = _activate_organization_workspace(
            client,
            organization_id="org_local_report_b",
            cloud_api_url="https://local-report-b.example.test",
        )
        foreign_sandbox_id = _activate_organization_workspace(
            client,
            organization_id="org_local_report_a",
            cloud_api_url="https://local-report-a.example.test",
        )
        set_active_sandbox_setting(state.db, "cloud_access_token", "")
        foreign_client_id, foreign_task_id = _create_client_and_task(client, "foreign-local-report")
        _seed_event_line(client, "event_local_report_a", foreign_sandbox_id)
        _seed_event_attachment(
            client,
            "foreign_event_attachment_from_metadata",
            "event_local_report_a",
        )
        state.db.execute(
            """
            INSERT INTO task_attachments_cloud(
                id, task_id, client_id, event_line_id, document_id,
                title, path, kind, source, size_bytes, created_at
            ) VALUES(?, ?, ?, ?, NULL, ?, ?, 'file', 'cloud', 17, ?)
            """,
            (
                "foreign_task_attachment_from_metadata",
                foreign_task_id,
                foreign_client_id,
                "event_local_report_a",
                "A 组织本地报告机密.txt",
                str(tmp_path / "foreign-local-report-secret.txt"),
                "2026-07-11T10:00:00",
            ),
        )

        activate_sandbox(state.db, scoped_sandbox_id)
        set_active_sandbox_setting(state.db, "cloud_access_token", "")
        scoped_client_id, _ = _create_client_and_task(client, "scoped-local-report")
        _seed_event_line(client, "event_local_report_b", scoped_sandbox_id)
        state.db.execute(
            "UPDATE event_lines SET primary_client_id = ? WHERE id = ?",
            (scoped_client_id, "event_local_report_b"),
        )
        state.db.execute(
            """
            INSERT INTO event_line_activities(
                id, event_line_id, source_type, source_id, happened_at,
                title, summary, metadata_json, is_key, created_at
            ) VALUES(?, ?, 'attachment', ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                "activity_foreign_attachment_hint",
                "event_local_report_b",
                "foreign_task_attachment_from_metadata",
                "2026-07-11T10:00:00",
                "B 组织活动",
                "元数据中的附件 ID 不能成为授权依据",
                json.dumps(
                    {"attachmentId": "foreign_event_attachment_from_metadata"},
                    ensure_ascii=False,
                ),
                "2026-07-11T10:00:00",
            ),
        )

        response = client.get(
            "/api/v1/event-lines/event_local_report_b/report-snapshot"
        )

    assert response.status_code == 200, response.text
    serialized = json.dumps(response.json(), ensure_ascii=False)
    # The caller-authored activity metadata itself remains visible, but it must
    # not be treated as authority to materialize either foreign attachment.
    assert response.json()["attachments"] == []
    assert "A 组织本地报告机密" not in serialized


def test_cloud_task_build_cannot_rehome_foreign_same_id_attachment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = create_app(tmp_path / "data")
    shared_cloud_task_id = "shared_cloud_task_id"

    with TestClient(app) as client:
        state = client.app.state.app_state
        scoped_sandbox_id = _activate_organization_workspace(
            client,
            organization_id="org_task_build_b",
            cloud_api_url="https://org-task-b.example.test",
        )
        _activate_organization_workspace(
            client,
            organization_id="org_task_build_a",
            cloud_api_url="https://org-task-a.example.test",
        )
        set_active_sandbox_setting(state.db, "cloud_access_token", "")
        foreign_client_id, _ = _create_client_and_task(client, "foreign-task-build")
        foreign_path = tmp_path / "foreign-task-secret.txt"
        foreign_path.write_text("foreign secret", encoding="utf-8")
        state.db.execute(
            """
            INSERT INTO task_attachments_cloud(
                id, task_id, client_id, event_line_id, document_id,
                title, path, kind, source, size_bytes, created_at
            ) VALUES(?, ?, ?, NULL, NULL, ?, ?, 'file', 'cloud', 14, ?)
            """,
            (
                "foreign_same_task_attachment",
                shared_cloud_task_id,
                foreign_client_id,
                "A 组织任务机密.txt",
                str(foreign_path),
                "2026-07-11T10:00:00",
            ),
        )

        activate_sandbox(state.db, scoped_sandbox_id)
        set_active_sandbox_setting(state.db, "cloud_access_token", "")
        scoped_client_id, scoped_task_id = _create_client_and_task(client, "scoped-task-build")
        state.db.execute(
            "UPDATE tasks SET cloud_id = ?, organization_id = ? WHERE id = ?",
            (shared_cloud_task_id, "org_task_build_b", scoped_task_id),
        )
        set_active_sandbox_setting(state.db, "cloud_access_token", "token_org_task_build_b")

        def fake_request(method: str, url: str, **kwargs):
            return FakeResponse(
                content=b"{}",
                payload={
                    "id": shared_cloud_task_id,
                    "title": "B 组织云任务",
                    "description": "不能吸入 A 组织附件",
                    "status": "todo",
                    "progressStatus": "todo",
                    "priority": "normal",
                    "listId": "list-0",
                    "clientId": scoped_client_id,
                    "organizationId": "org_task_build_b",
                    "collaborators": [],
                    "createdAt": "2026-07-11T10:00:00",
                    "updatedAt": "2026-07-11T10:00:00",
                },
            )

        monkeypatch.setattr(app_main.httpx, "request", fake_request)
        response = client.get(f"/api/v1/tasks/{scoped_task_id}/context-preview")
        foreign_row = state.db.fetchone(
            "SELECT task_id, client_id, path FROM task_attachments_cloud WHERE id = ?",
            ("foreign_same_task_attachment",),
        )

    assert response.status_code == 200, response.text
    assert foreign_row is not None
    assert str(foreign_row["task_id"]) == shared_cloud_task_id
    assert str(foreign_row["client_id"]) == foreign_client_id
    assert str(foreign_row["path"]) == str(foreign_path)
    assert foreign_path.read_text(encoding="utf-8") == "foreign secret"


def test_task_delete_cannot_delete_foreign_cloud_id_collision(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = create_app(tmp_path / "data")
    shared_cloud_task_id = "shared_delete_cloud_task_id"
    cloud_calls: list[tuple[str, str, dict]] = []

    def fake_request(method: str, url: str, **kwargs):
        cloud_calls.append((method, url, kwargs))
        return FakeResponse(content=b"{}", payload={})

    monkeypatch.setattr(app_main.httpx, "request", fake_request)
    with TestClient(app) as client:
        state = client.app.state.app_state
        scoped_sandbox_id = _activate_organization_workspace(
            client,
            organization_id="org_task_delete_b",
            cloud_api_url="https://task-delete-b.example.test",
        )
        _activate_organization_workspace(
            client,
            organization_id="org_task_delete_a",
            cloud_api_url="https://task-delete-a.example.test",
        )
        foreign_client_id, foreign_task_id = _create_client_and_task(
            client,
            "foreign-task-delete",
        )
        state.db.execute(
            "UPDATE tasks SET cloud_id = ?, organization_id = ? WHERE id = ?",
            (shared_cloud_task_id, "org_task_delete_a", foreign_task_id),
        )
        state.db.execute(
            """
            INSERT INTO task_attachments_cloud(
                id, task_id, client_id, event_line_id, document_id,
                title, path, kind, source, size_bytes, created_at
            ) VALUES(?, ?, ?, NULL, NULL, ?, ?, 'file', 'cloud', 21, ?)
            """,
            (
                "foreign_delete_collision_attachment",
                shared_cloud_task_id,
                foreign_client_id,
                "A 组织不可删除附件.txt",
                str(tmp_path / "foreign-delete-collision.txt"),
                "2026-07-11T10:00:00",
            ),
        )

        activate_sandbox(state.db, scoped_sandbox_id)
        scoped_client_id, scoped_task_id = _create_client_and_task(
            client,
            "scoped-task-delete",
        )
        state.db.execute(
            "UPDATE tasks SET cloud_id = ?, organization_id = ? WHERE id = ?",
            (shared_cloud_task_id, "org_task_delete_b", scoped_task_id),
        )

        response = client.delete(f"/api/v1/tasks/{scoped_task_id}")
        foreign_task = state.db.fetchone(
            "SELECT id, client_id FROM tasks WHERE id = ?",
            (foreign_task_id,),
        )
        foreign_attachment = state.db.fetchone(
            "SELECT id, client_id FROM task_attachments_cloud WHERE id = ?",
            ("foreign_delete_collision_attachment",),
        )
        deleted_task = state.db.fetchone(
            "SELECT id FROM tasks WHERE id = ?",
            (scoped_task_id,),
        )

    assert response.status_code == 200, response.text
    assert deleted_task is None
    assert foreign_task is not None
    assert str(foreign_task["client_id"]) == foreign_client_id
    assert foreign_attachment is not None
    assert str(foreign_attachment["client_id"]) == foreign_client_id
    delete_calls = [call for call in cloud_calls if call[0] == "DELETE"]
    assert len(delete_calls) == 1
    assert delete_calls[0][1] == (
        f"https://task-delete-b.example.test/api/v1/tasks/{shared_cloud_task_id}"
    )
    assert delete_calls[0][2]["headers"] == {
        "Authorization": "Bearer token_org_task_delete_b"
    }


def test_attachment_delete_does_not_blind_delete_other_table_collision(
    tmp_path: Path,
) -> None:
    app = create_app(tmp_path / "data")
    shared_attachment_id = "shared_cross_table_delete_attachment"

    with TestClient(app) as client:
        state = client.app.state.app_state
        scoped_sandbox_id = _activate_organization_workspace(
            client,
            organization_id="org_attachment_delete_b",
            cloud_api_url="https://attachment-delete-b.example.test",
        )
        _activate_organization_workspace(
            client,
            organization_id="org_attachment_delete_a",
            cloud_api_url="https://attachment-delete-a.example.test",
        )
        foreign_client_id, _ = _create_client_and_task(
            client,
            "foreign-attachment-delete",
        )

        activate_sandbox(state.db, scoped_sandbox_id)
        scoped_client_id, scoped_task_id = _create_client_and_task(
            client,
            "scoped-attachment-delete",
        )
        state.db.execute(
            """
            INSERT INTO task_attachments(
                id, task_id, client_id, event_line_id, document_id,
                title, path, kind, source, size_bytes, created_at
            ) VALUES(?, ?, ?, NULL, NULL, ?, ?, 'file', 'local', 11, ?)
            """,
            (
                shared_attachment_id,
                scoped_task_id,
                scoped_client_id,
                "B 组织待删除附件.txt",
                str(tmp_path / "scoped-delete.txt"),
                "2026-07-11T10:00:00",
            ),
        )
        state.db.execute(
            """
            INSERT INTO task_attachments_cloud(
                id, task_id, client_id, event_line_id, document_id,
                title, path, kind, source, size_bytes, created_at
            ) VALUES(?, ?, ?, NULL, NULL, ?, ?, 'file', 'cloud', 19, ?)
            """,
            (
                shared_attachment_id,
                scoped_task_id,
                foreign_client_id,
                "A 组织不可删除附件.txt",
                str(tmp_path / "foreign-cross-table-delete.txt"),
                "2026-07-11T10:00:00",
            ),
        )

        response = client.delete(
            f"/api/v1/tasks/{scoped_task_id}/attachments/{shared_attachment_id}"
        )
        scoped_attachment = state.db.fetchone(
            "SELECT id FROM task_attachments WHERE id = ?",
            (shared_attachment_id,),
        )
        foreign_attachment = state.db.fetchone(
            "SELECT id, client_id, title FROM task_attachments_cloud WHERE id = ?",
            (shared_attachment_id,),
        )

    assert response.status_code == 200, response.text
    assert scoped_attachment is None
    assert foreign_attachment is not None
    assert str(foreign_attachment["client_id"]) == foreign_client_id
    assert str(foreign_attachment["title"]) == "A 组织不可删除附件.txt"


def test_word_export_attachment_fetches_forward_bearer_header(tmp_path: Path, monkeypatch) -> None:
    app = create_app(tmp_path / "data")
    calls: list[tuple[str, dict]] = []

    def fake_get(url: str, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/text-content"):
            return FakeResponse(payload={"text": "云端文档摘要"})
        # Deliberately non-image bytes exercise the guarded image failure path
        # after the authenticated request has already been verified.
        return FakeResponse(content=b"not-an-image")

    monkeypatch.setattr(app_main.httpx, "get", fake_get)
    with TestClient(app) as client:
        sandbox_id = _activate_organization_workspace(
            client,
            organization_id="org_word_export_auth",
            cloud_api_url=CLOUD_API_URL,
        )
        _configure_cloud(client, CLOUD_TOKEN)
        _seed_event_line(client, "event_line_word_auth", sandbox_id)
        _seed_event_attachment(client, "attachment_image_auth", "event_line_word_auth")
        _seed_event_attachment(client, "attachment_doc_auth", "event_line_word_auth")

        draft = _word_export_draft()
        draft["attachments"][0]["downloadUrl"] = (
            "https://foreign-org.example.test/api/public/task-attachments/foreign"
        )
        response = client.post(
            "/api/v1/event-lines/event_line_word_auth/export-word",
            json=draft,
        )

    assert response.status_code == 200, response.text
    assert len(calls) == 2
    assert calls[0][0] == f"{CLOUD_API_URL}/api/public/task-attachments/attachment_image_auth"
    assert calls[1][0] == f"{CLOUD_API_URL}/api/public/task-attachments/attachment_doc_auth/text-content"
    for url, kwargs in calls:
        assert kwargs["headers"] == {"Authorization": f"Bearer {CLOUD_TOKEN}"}
        assert kwargs["follow_redirects"] is False
        assert CLOUD_TOKEN not in url
        assert "foreign-org.example.test" not in url


def test_word_export_without_token_makes_no_attachment_request(tmp_path: Path, monkeypatch) -> None:
    app = create_app(tmp_path / "data")
    calls: list[str] = []

    def forbidden_get(url: str, **kwargs):
        calls.append(url)
        raise AssertionError("anonymous cloud request must not be sent")

    monkeypatch.setattr(app_main.httpx, "get", forbidden_get)
    with TestClient(app) as client:
        _configure_cloud(client, "")
        _seed_event_line(client, "event_line_word_no_token")
        _seed_event_attachment(client, "attachment_image_auth", "event_line_word_no_token")
        _seed_event_attachment(client, "attachment_doc_auth", "event_line_word_no_token")

        response = client.post(
            "/api/v1/event-lines/event_line_word_no_token/export-word",
            json=_word_export_draft(),
        )

    assert response.status_code == 200, response.text
    assert calls == []
