from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import main as cloud_main  # noqa: E402
from app.main import DEFAULT_ORG_ID, _department_invite_code, create_app, now_iso  # noqa: E402
from app.models import SmartTaskDraftResponse  # noqa: E402


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(tmp_path / "cloud-data"))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Member123!")
    return TestClient(create_app())


def _headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def _configure_asr(
    client: TestClient,
    headers: dict[str, str],
    *,
    app_id: str,
    token: str,
) -> dict:
    response = client.post(
        "/api/v1/settings/org-asr-config",
        headers=headers,
        json={"provider": "doubao_file", "appId": app_id, "accessToken": token},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _member_headers(client: TestClient) -> dict[str, str]:
    timestamp = now_iso()
    client.app.state.app_state.db.execute(
        """
        INSERT OR REPLACE INTO org_departments(id, organization_id, name, color, active, updated_at)
        VALUES('dept_asr_member', ?, 'ASR测试部', '#14B8A6', 1, ?)
        """,
        (DEFAULT_ORG_ID, timestamp),
    )
    invite = _department_invite_code(
        "dept_asr_member",
        organization_id=DEFAULT_ORG_ID,
        organization_name="益语智库",
        department_name="ASR测试部",
        order=0,
    )
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "asr-member@example.com",
            "fullName": "ASR普通成员",
            "phone": "13900139991",
            "password": "Member123!",
            "inviteCode": invite,
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_org_asr_admin_masked_encrypted_clear_and_member_forbidden(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    admin = _headers(client, "admin@yiyu-system.com", "Admin123!")
    app_id = "org-a-app-id-123456"
    token = "org-a-access-token-abcdef"

    saved = _configure_asr(client, admin, app_id=app_id, token=token)
    assert saved["orgId"] == DEFAULT_ORG_ID
    assert saved["appIdMasked"] == "••••3456"
    assert saved["accessTokenMasked"] == "••••cdef"
    assert app_id not in str(saved)
    assert token not in str(saved)

    row = client.app.state.app_state.db.fetchone(
        "SELECT * FROM org_asr_config WHERE org_id = ?", (DEFAULT_ORG_ID,)
    )
    assert row is not None
    assert app_id not in str(row["app_id_encrypted"])
    assert token not in str(row["access_token_encrypted"])
    assert row["app_id_nonce"] != row["access_token_nonce"]
    runtime = cloud_main._org_asr_runtime_config_or_503(
        client.app.state.app_state, DEFAULT_ORG_ID
    )
    assert runtime.app_id == app_id
    assert runtime.access_token == token

    member = _member_headers(client)
    assert client.get("/api/v1/settings/org-asr-config", headers=member).status_code == 403
    assert client.post(
        "/api/v1/settings/org-asr-config",
        headers=member,
        json={"appId": "stolen", "accessToken": "stolen"},
    ).status_code == 403

    cleared = client.put(
        "/api/v1/settings/org-asr-config",
        headers=admin,
        json={"clearAppId": True},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["hasAppId"] is False
    assert cleared.json()["hasAccessToken"] is True
    assert client.delete("/api/v1/settings/org-asr-config", headers=admin).status_code == 200
    assert client.get("/api/v1/settings/org-asr-config", headers=admin).json()["hasAccessToken"] is False


def test_org_asr_isolated_and_corrupt_config_fails_closed(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    admin_a = _headers(client, "admin@yiyu-system.com", "Admin123!")
    _configure_asr(client, admin_a, app_id="org-a-app-123456", token="org-a-token-123456")

    registered_b = client.post(
        "/api/v1/auth/register",
        json={
            "email": "asr-owner-b@example.com",
            "fullName": "ASR组织B管理员",
            "phone": "13900139992",
            "password": "Password123!",
            "organizationName": "ASR组织B",
        },
    )
    assert registered_b.status_code == 200, registered_b.text
    payload_b = registered_b.json()
    headers_b = {"Authorization": f"Bearer {payload_b['accessToken']}"}
    org_b = payload_b["user"]["organizationId"]
    empty_b = client.get("/api/v1/settings/org-asr-config", headers=headers_b)
    assert empty_b.status_code == 200
    assert empty_b.json()["hasAppId"] is False
    _configure_asr(client, headers_b, app_id="org-b-app-654321", token="org-b-token-654321")

    runtime_a = cloud_main._org_asr_runtime_config_or_503(client.app.state.app_state, DEFAULT_ORG_ID)
    runtime_b = cloud_main._org_asr_runtime_config_or_503(client.app.state.app_state, org_b)
    assert (runtime_a.app_id, runtime_a.access_token) == ("org-a-app-123456", "org-a-token-123456")
    assert (runtime_b.app_id, runtime_b.access_token) == ("org-b-app-654321", "org-b-token-654321")

    client.app.state.app_state.db.execute(
        "UPDATE org_asr_config SET access_token_nonce = ? WHERE org_id = ?",
        ("not-valid-base64", org_b),
    )
    try:
        cloud_main._org_asr_runtime_config_or_503(client.app.state.app_state, org_b)
    except cloud_main.HTTPException as error:
        assert error.status_code == 503
    else:
        raise AssertionError("corrupt organization ASR config must fail closed")


def test_mobile_audio_uses_org_asr_credentials_not_environment(tmp_path, monkeypatch) -> None:
    for name in (
        "DOUBAO_FILE_ASR_APP_ID",
        "YIYU_DOUBAO_FILE_ASR_APP_ID",
        "VOLCENGINE_FILE_ASR_APP_ID",
        "DOUBAO_ASR_APP_ID",
        "DOUBAO_FILE_ASR_ACCESS_TOKEN",
        "YIYU_DOUBAO_FILE_ASR_ACCESS_TOKEN",
        "VOLCENGINE_FILE_ASR_ACCESS_TOKEN",
        "DOUBAO_ASR_ACCESS_TOKEN",
    ):
        monkeypatch.setenv(name, f"poison-{name.lower()}")
    client = _client(tmp_path, monkeypatch)
    admin = _headers(client, "admin@yiyu-system.com", "Admin123!")
    _configure_asr(client, admin, app_id="real-org-app-123456", token="real-org-token-abcdef")
    ai = client.post(
        "/api/v1/settings/org-ai-config",
        headers=admin,
        json={
            "aiProvider": "openai-compatible",
            "aiBaseUrl": "https://models.example.com/v1",
            "aiModel": "test-model",
            "apiKey": "real-org-ai-key",
        },
    )
    assert ai.status_code == 200, ai.text
    observed: dict[str, str] = {}

    def fake_transcribe(audio_bytes: bytes, **kwargs) -> str:  # noqa: ANN003
        assert audio_bytes == b"fake-mobile-audio"
        observed["app_id"] = kwargs["app_id"]
        observed["access_token"] = kwargs["access_token"]
        return "明天下午三点开项目会议"

    monkeypatch.setattr(cloud_main, "transcribe_audio_with_doubao", fake_transcribe)
    monkeypatch.setattr(
        cloud_main,
        "build_smart_task_draft",
        lambda transcript, *_args, **_kwargs: SmartTaskDraftResponse(transcript=transcript),
    )
    response = client.post(
        "/api/v1/mobile/smart-input/task-draft",
        headers=admin,
        files={"audio": ("note.m4a", b"fake-mobile-audio", "audio/mp4")},
    )
    assert response.status_code == 200, response.text
    assert observed == {
        "app_id": "real-org-app-123456",
        "access_token": "real-org-token-abcdef",
    }
