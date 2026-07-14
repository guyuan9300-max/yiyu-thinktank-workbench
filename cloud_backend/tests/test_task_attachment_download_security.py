from __future__ import annotations

import base64
import sys
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import DEFAULT_ORG_ID, TASK_ATTACHMENT_UPLOAD_LIMIT_BYTES, create_app, now_iso
from app.security import hash_password


FOREIGN_ORG_ID = "org_attachment_download_foreign"
FOREIGN_USER_ID = "user_attachment_download_foreign"
FOREIGN_EMAIL = "attachment-download-foreign@example.com"
PASSWORD = "Password123!"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _make_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(tmp_path / "cloud-data"))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("VOLCENGINE_API_KEY", raising=False)
    return TestClient(create_app())


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def _seed_foreign_user(client: TestClient) -> dict[str, str]:
    timestamp = now_iso()
    db = client.app.state.app_state.db
    db.execute(
        "INSERT INTO organizations(id, name, slug, created_at, updated_at) VALUES(?, '附件外组织', 'attachment-foreign', ?, ?)",
        (FOREIGN_ORG_ID, timestamp, timestamp),
    )
    db.execute(
        """
        INSERT INTO employee_accounts(
            id, organization_id, email, full_name, password_hash, primary_role, account_status,
            membership_status, approved_at, approved_by, recent_mentions_json, created_at, updated_at
        ) VALUES(?, ?, ?, '附件外组织用户', ?, 'employee', 'approved', 'approved', ?, NULL, '[]', ?, ?)
        """,
        (
            FOREIGN_USER_ID,
            FOREIGN_ORG_ID,
            FOREIGN_EMAIL,
            hash_password(PASSWORD),
            timestamp,
            timestamp,
            timestamp,
        ),
    )
    return _login(client, FOREIGN_EMAIL, PASSWORD)


def _create_task(client: TestClient, headers: dict[str, str], title: str) -> str:
    response = client.post("/api/v1/tasks", json={"title": title, "listId": "list-0"}, headers=headers)
    assert response.status_code == 200, response.text
    return str(response.json()["id"])


def _upload(
    client: TestClient,
    headers: dict[str, str],
    task_id: str,
    *,
    name: str,
    content: bytes,
    mime_type: str,
) -> str:
    response = client.post(
        f"/api/v1/tasks/{task_id}/attachments",
        headers=headers,
        data={"title": name},
        files={"file": (name, content, mime_type)},
    )
    assert response.status_code == 200, response.text
    match = next(item for item in response.json()["attachments"] if item["title"] == name)
    return str(match["id"])


def test_attachment_surfaces_require_session_and_enforce_tenant_then_disappear_after_delete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeImage:
        width = 1
        height = 1

        def save(self, output, **_kwargs) -> None:  # type: ignore[no-untyped-def]
            output.write(PNG_1X1)

    fake_image_module = types.SimpleNamespace(open=lambda _path: _FakeImage(), LANCZOS=1)
    monkeypatch.setitem(sys.modules, "PIL", types.SimpleNamespace(Image=fake_image_module))
    client = _make_client(tmp_path, monkeypatch)
    owner_headers = _login(client, "admin@yiyu-system.com", "Admin123!")
    foreign_headers = _seed_foreign_user(client)
    task_id = _create_task(client, owner_headers, "附件下载鉴权任务")
    text_id = _upload(
        client,
        owner_headers,
        task_id,
        name="边界说明.txt",
        content="仅本任务成员可见".encode(),
        mime_type="text/plain",
    )
    image_id = _upload(
        client,
        owner_headers,
        task_id,
        name="边界图片.png",
        content=PNG_1X1,
        mime_type="image/png",
    )
    paths = [
        f"/api/public/task-attachments/{text_id}",
        f"/api/public/task-attachments/{text_id}/text-content",
        f"/api/public/task-attachments/{image_id}/thumbnail",
        f"/api/public/task-attachments/{image_id}/ocr-summary",
    ]
    canonical_download_path = f"/api/v1/tasks/{task_id}/attachments/{text_id}/download"

    for path in paths:
        assert client.get(path).status_code == 401
        assert client.get(path, headers=foreign_headers).status_code == 403
        response = client.get(path, headers=owner_headers)
        expected_status = 503 if path.endswith("/ocr-summary") else 200
        assert response.status_code == expected_status, (path, response.text)

    download = client.get(paths[0], headers=owner_headers)
    assert download.content == "仅本任务成员可见".encode()
    assert download.headers["content-type"].startswith("text/plain")
    assert download.headers["content-disposition"].startswith("attachment;")
    canonical_download = client.get(canonical_download_path, headers=owner_headers)
    assert canonical_download.status_code == 200
    assert canonical_download.content == download.content
    assert client.get(canonical_download_path).status_code == 401
    assert client.get(canonical_download_path, headers=foreign_headers).status_code == 404

    deleted = client.delete(f"/api/v1/tasks/{task_id}", headers=owner_headers)
    assert deleted.status_code == 200, deleted.text
    for path in paths:
        assert client.get(path, headers=owner_headers).status_code == 404
    assert client.get(canonical_download_path, headers=owner_headers).status_code == 404


def test_ocr_uses_each_organizations_own_ark_key_and_never_falls_back_to_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _make_client(tmp_path, monkeypatch)
    owner_headers = _login(client, "admin@yiyu-system.com", "Admin123!")
    foreign_headers = _seed_foreign_user(client)
    state = client.app.state.app_state
    state.db.execute(
        "UPDATE employee_accounts SET primary_role = 'admin' WHERE id = ?",
        (FOREIGN_USER_ID,),
    )

    def configure(headers: dict[str, str], key: str, model: str) -> None:
        response = client.post(
            "/api/v1/settings/org-ai-config",
            headers=headers,
            json={
                "aiProvider": "openai_compatible",
                "aiProviderLabel": "豆包火山方舟",
                "aiBaseUrl": "https://ark.cn-beijing.volces.com/api/v3",
                "aiModel": model,
                "apiKey": key,
            },
        )
        assert response.status_code == 200, response.text

    configure(owner_headers, "ark-key-org-a", "ark-ocr-model-a")
    configure(foreign_headers, "ark-key-org-b", "ark-ocr-model-b")
    owner_task_id = _create_task(client, owner_headers, "组织 A OCR")
    foreign_task_id = _create_task(client, foreign_headers, "组织 B OCR")
    owner_image_id = _upload(
        client,
        owner_headers,
        owner_task_id,
        name="org-a.png",
        content=PNG_1X1,
        mime_type="image/png",
    )
    foreign_image_id = _upload(
        client,
        foreign_headers,
        foreign_task_id,
        name="org-b.png",
        content=PNG_1X1,
        mime_type="image/png",
    )

    calls: list[tuple[str, str, str]] = []

    class _FakeArkResponse:
        status_code = 200

        def __init__(self, summary: str) -> None:
            self._summary = summary

        def json(self) -> dict:
            return {"choices": [{"message": {"content": self._summary}}]}

    def fake_post(url: str, *, headers: dict, json: dict, timeout: float):  # type: ignore[no-untyped-def]
        authorization = str(headers.get("Authorization") or "")
        model = str(json.get("model") or "")
        calls.append((url, authorization, model))
        return _FakeArkResponse(f"summary:{authorization}:{model}")

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    owner_response = client.get(
        f"/api/public/task-attachments/{owner_image_id}/ocr-summary",
        headers=owner_headers,
    )
    foreign_response = client.get(
        f"/api/public/task-attachments/{foreign_image_id}/ocr-summary",
        headers=foreign_headers,
    )
    assert owner_response.status_code == 200, owner_response.text
    assert foreign_response.status_code == 200, foreign_response.text
    assert calls == [
        (
            "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
            "Bearer ark-key-org-a",
            "ark-ocr-model-a",
        ),
        (
            "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
            "Bearer ark-key-org-b",
            "ark-ocr-model-b",
        ),
    ]

    # Even if a process-wide key exists, an org that clears its key must fail
    # explicitly instead of borrowing another sandbox's/global credential.
    monkeypatch.setenv("ARK_API_KEY", "forbidden-global-fallback")
    cleared = client.post(
        "/api/v1/settings/org-ai-config",
        headers=foreign_headers,
        json={
            "aiProvider": "openai_compatible",
            "aiProviderLabel": "豆包火山方舟",
            "aiBaseUrl": "https://ark.cn-beijing.volces.com/api/v3",
            "aiModel": "ark-ocr-model-b",
            "clearApiKey": True,
        },
    )
    assert cleared.status_code == 200, cleared.text
    missing_key = client.get(
        f"/api/public/task-attachments/{foreign_image_id}/ocr-summary",
        headers=foreign_headers,
    )
    assert missing_key.status_code == 503, missing_key.text
    assert "当前组织未配置" in missing_key.json()["detail"]
    assert len(calls) == 2


def test_task_attachment_over_25_mib_is_rejected_before_file_or_db_side_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _make_client(tmp_path, monkeypatch)
    headers = _login(client, "admin@yiyu-system.com", "Admin123!")
    task_id = _create_task(client, headers, "附件大小上限任务")
    state = client.app.state.app_state
    target_dir = state.data_dir / "task-attachments" / DEFAULT_ORG_ID / task_id
    before_count = int(
        state.db.scalar("SELECT COUNT(*) FROM task_attachments WHERE task_id = ?", (task_id,)) or 0
    )

    response = client.post(
        f"/api/v1/tasks/{task_id}/attachments",
        headers=headers,
        files={
            "file": (
                "too-large.bin",
                b"x" * (TASK_ATTACHMENT_UPLOAD_LIMIT_BYTES + 1),
                "application/octet-stream",
            )
        },
    )

    assert response.status_code == 413, response.text
    assert not target_dir.exists()
    after_count = int(
        state.db.scalar("SELECT COUNT(*) FROM task_attachments WHERE task_id = ?", (task_id,)) or 0
    )
    assert after_count == before_count

    event_line_response = client.post(
        "/api/v1/event-lines",
        headers=headers,
        json={"name": "事件线附件大小上限", "kind": "project_line"},
    )
    assert event_line_response.status_code == 200, event_line_response.text
    event_line_id = str(event_line_response.json()["id"])
    event_target_dir = state.data_dir / "event-line-attachments" / DEFAULT_ORG_ID / event_line_id
    event_before_count = int(
        state.db.scalar(
            "SELECT COUNT(*) FROM event_line_attachments WHERE event_line_id = ?",
            (event_line_id,),
        )
        or 0
    )

    event_response = client.post(
        f"/api/v1/event-lines/{event_line_id}/attachments",
        headers=headers,
        files={
            "file": (
                "too-large-event.bin",
                b"y" * (TASK_ATTACHMENT_UPLOAD_LIMIT_BYTES + 1),
                "application/octet-stream",
            )
        },
    )

    assert event_response.status_code == 413, event_response.text
    assert not event_target_dir.exists()
    event_after_count = int(
        state.db.scalar(
            "SELECT COUNT(*) FROM event_line_attachments WHERE event_line_id = ?",
            (event_line_id,),
        )
        or 0
    )
    assert event_after_count == event_before_count
