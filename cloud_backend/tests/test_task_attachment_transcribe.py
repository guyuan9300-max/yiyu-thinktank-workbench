from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import main as cloud_main  # noqa: E402
from app.main import DEFAULT_ORG_ID, create_app, now_iso  # noqa: E402


def _set_seed_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(tmp_path / "cloud-data"))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Simulate123!")


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@yiyu-system.com", "password": "Admin123!"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def _enable_explicit_test_ai(client: TestClient, headers: dict[str, str], monkeypatch) -> None:
    configured = client.post(
        "/api/v1/settings/org-ai-config",
        headers=headers,
        json={
            "aiProvider": "openai-compatible",
            "aiProviderLabel": "测试组织模型",
            "aiBaseUrl": "https://models.example.com/v1",
            "aiModel": "test-model",
            "apiKey": "test-org-key",
        },
    )
    assert configured.status_code == 200, configured.text
    asr_configured = client.post(
        "/api/v1/settings/org-asr-config",
        headers=headers,
        json={
            "provider": "doubao_file",
            "appId": "attachment-test-app-id",
            "accessToken": "attachment-test-access-token",
        },
    )
    assert asr_configured.status_code == 200, asr_configured.text
    monkeypatch.setattr(cloud_main, "_generate_recording_summary", lambda **_: "测试摘要")


def _insert_client(app, client_id: str, client_name: str) -> None:
    timestamp = now_iso()
    app.state.app_state.db.execute(
        "INSERT INTO clients(id, organization_id, name, alias, created_at, updated_at) VALUES(?, ?, ?, NULL, ?, ?)",
        (client_id, DEFAULT_ORG_ID, client_name, timestamp, timestamp),
    )


def test_transcribe_attachment_resolves_client_name_without_500(tmp_path: Path, monkeypatch) -> None:
    """回归: 转写端点曾因 task_row['client_name'](非 tasks 表字段, SELECT * 不含它)
    抛 sqlite3.Row 的 IndexError → 整个端点 500。现改为按 client_id 从 clients 表解析。
    带客户的任务转写应 200 且回传转写文本, 不再 500。"""
    _set_seed_env(tmp_path, monkeypatch)
    # mock 豆包 ASR, 不真调云端; 返回一段文本让端点走到 client_name 解析这一步
    monkeypatch.setattr(
        cloud_main,
        "transcribe_audio_with_doubao",
        lambda *args, **kwargs: "这是一段用于回归测试的录音转写文本内容。",
    )
    app = create_app()
    _insert_client(app, "client_transcribe_regr", "转写回归客户")
    client = TestClient(app)
    headers = _auth_headers(client)
    _enable_explicit_test_ai(client, headers, monkeypatch)

    task_resp = client.post(
        "/api/v1/tasks",
        json={"title": "录音转写回归任务", "clientId": "client_transcribe_regr", "listId": "list-0"},
        headers=headers,
    )
    assert task_resp.status_code == 200, task_resp.text
    task_id = task_resp.json()["id"]

    upload = client.post(
        f"/api/v1/tasks/{task_id}/attachments",
        files={"file": ("note.m4a", b"\x00\x01\x02fake-audio-bytes-for-test", "audio/mp4")},
        data={"title": "回归录音"},
        headers=headers,
    )
    assert upload.status_code == 200, upload.text
    attachments = upload.json().get("attachments") or []
    audio = next((a for a in attachments if str(a.get("mimeType") or "").startswith("audio/")), None)
    assert audio is not None, f"未找到音频附件: {attachments}"

    # 修复前: 此处 task_row['client_name'] 抛 IndexError → 500
    resp = client.post(
        f"/api/v1/tasks/{task_id}/attachments/{audio['id']}/transcribe-to-document",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["transcript"].startswith("这是一段")
    assert body["attachmentId"] == audio["id"]


def test_transcribe_attachment_without_client_ok(tmp_path: Path, monkeypatch) -> None:
    """无客户归属的任务转写也应正常(client_name 解析为 None, 不报错)。"""
    _set_seed_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        cloud_main,
        "transcribe_audio_with_doubao",
        lambda *args, **kwargs: "无客户归属的回归测试转写文本内容。",
    )
    app = create_app()
    client = TestClient(app)
    headers = _auth_headers(client)
    _enable_explicit_test_ai(client, headers, monkeypatch)

    task_resp = client.post("/api/v1/tasks", json={"title": "无客户录音任务", "listId": "list-0"}, headers=headers)
    assert task_resp.status_code == 200, task_resp.text
    task_id = task_resp.json()["id"]

    upload = client.post(
        f"/api/v1/tasks/{task_id}/attachments",
        files={"file": ("note.m4a", b"\x00\x01\x02fake-audio", "audio/mp4")},
        data={"title": "回归录音2"},
        headers=headers,
    )
    assert upload.status_code == 200, upload.text
    audio = next((a for a in (upload.json().get("attachments") or []) if str(a.get("mimeType") or "").startswith("audio/")), None)
    assert audio is not None

    resp = client.post(
        f"/api/v1/tasks/{task_id}/attachments/{audio['id']}/transcribe-to-document",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize("provider_fails", [False, True])
def test_transcribe_uses_ephemeral_public_copy_and_always_cleans_up(
    tmp_path: Path,
    monkeypatch,
    provider_fails: bool,
) -> None:
    _set_seed_env(tmp_path, monkeypatch)
    monkeypatch.setenv("YIYU_CLOUD_PUBLIC_BASE_URL", "https://cloud.example")
    monkeypatch.setenv("YIYU_SMART_INPUT_AUDIO_TTL_SECONDS", "1")
    original_audio = b"temporary-public-copy-regression-audio"
    observed: dict[str, object] = {}

    def fake_transcribe(
        audio_bytes: bytes,
        *,
        file_name: str | None,
        mime_type: str | None,
        app_id: str,
        access_token: str,
        public_url: str | None,
    ) -> str:
        assert audio_bytes == original_audio
        assert file_name and file_name.endswith(".m4a")
        assert mime_type == "audio/mp4"
        assert app_id == "attachment-test-app-id"
        assert access_token == "attachment-test-access-token"
        assert public_url is not None
        file_key = public_url.rsplit("/", 1)[-1]
        assert re.fullmatch(r"[0-9a-f]{32}\.m4a", file_key)
        temporary_path = tmp_path / "cloud-data" / "smart-input-audio" / file_key
        assert temporary_path.read_bytes() == original_audio
        # An in-flight provider fetch may outlive the TTL.  Lazy cleanup must
        # preserve the registered active file until the transcription finishes.
        stale_time = time.time() - 10
        os.utime(temporary_path, (stale_time, stale_time))
        assert cloud_main._cleanup_expired_smart_input_audio(client.app.state.app_state) == 0
        assert temporary_path.exists()
        observed["temporary_path"] = temporary_path
        if provider_fails:
            raise RuntimeError("provider rejected test audio")
        return "临时公开副本已安全完成转写。"

    monkeypatch.setattr(cloud_main, "transcribe_audio_with_doubao", fake_transcribe)
    app = create_app()
    client = TestClient(app)
    headers = _auth_headers(client)
    _enable_explicit_test_ai(client, headers, monkeypatch)
    task_response = client.post(
        "/api/v1/tasks",
        json={"title": "临时副本清理回归", "listId": "list-0"},
        headers=headers,
    )
    assert task_response.status_code == 200, task_response.text
    task_id = task_response.json()["id"]
    upload_response = client.post(
        f"/api/v1/tasks/{task_id}/attachments",
        files={"file": ("note.m4a", original_audio, "audio/mp4")},
        data={"title": "临时副本录音"},
        headers=headers,
    )
    assert upload_response.status_code == 200, upload_response.text
    attachment = next(
        item
        for item in upload_response.json().get("attachments", [])
        if str(item.get("mimeType") or "").startswith("audio/")
    )

    # The permanent attachment is never reopened for anonymous provider access.
    anonymous_download = client.get(f"/api/public/task-attachments/{attachment['id']}")
    assert anonymous_download.status_code == 401

    response = client.post(
        f"/api/v1/tasks/{task_id}/attachments/{attachment['id']}/transcribe-to-document",
        headers=headers,
    )
    assert response.status_code == (400 if provider_fails else 200), response.text
    temporary_path = observed.get("temporary_path")
    assert isinstance(temporary_path, Path)
    assert not temporary_path.exists()

    permanent_row = app.state.app_state.db.fetchone(
        "SELECT path FROM task_attachments WHERE id = ?",
        (attachment["id"],),
    )
    assert permanent_row is not None
    assert (app.state.app_state.data_dir / str(permanent_row["path"])).exists()


def test_smart_input_audio_ttl_cleanup_removes_only_expired_safe_regular_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _set_seed_env(tmp_path, monkeypatch)
    monkeypatch.setenv("YIYU_SMART_INPUT_AUDIO_TTL_SECONDS", "60")
    app = create_app()
    state = app.state.app_state
    audio_dir = state.data_dir / "smart-input-audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    expired = audio_dir / f"{'1' * 32}.m4a"
    unexpired = audio_dir / f"{'2' * 32}.m4a"
    unrelated = audio_dir / "do-not-touch.txt"
    outside = tmp_path / "outside-audio.m4a"
    symlink = audio_dir / f"{'3' * 32}.m4a"
    expired.write_bytes(b"expired")
    unexpired.write_bytes(b"fresh")
    unrelated.write_bytes(b"unrelated")
    outside.write_bytes(b"outside")
    symlink.symlink_to(outside)
    now = time.time()
    os.utime(expired, (now - 61, now - 61))
    os.utime(unexpired, (now - 59, now - 59))

    assert cloud_main._cleanup_expired_smart_input_audio(state, now_epoch=now) == 1
    assert not expired.exists()
    assert unexpired.read_bytes() == b"fresh"
    assert unrelated.read_bytes() == b"unrelated"
    assert symlink.is_symlink()
    assert outside.read_bytes() == b"outside"

    client = TestClient(app)
    assert client.get(f"/api/public/smart-input-audio/{symlink.name}").status_code == 404
