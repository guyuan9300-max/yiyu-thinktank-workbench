from __future__ import annotations

import sys
from pathlib import Path

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
        json={"email": "admin@example.org", "password": "Admin123!"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


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
