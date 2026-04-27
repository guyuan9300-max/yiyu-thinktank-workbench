from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str = "rollback-drill-p25") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "rollback drill p25",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_data_center_rollback_drill_api_p25(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)

    client.app.state.app_state.db.set_setting("workspace_chat_data_center_primary", "1")
    setting = client.post(
        "/api/v1/retrieval/settings",
        json={"chatKernelPrimaryEnabled": True, "chatKernelPrimaryClientAllowlist": [client_id]},
    )
    assert setting.status_code == 200, setting.text

    dry_run = client.post(
        "/api/v1/data-center/rollback-drill",
        json={"clientIds": [client_id], "dryRun": True},
    )
    assert dry_run.status_code == 200, dry_run.text
    dry_payload = dry_run.json()
    assert dry_payload.get("dryRun") is True
    assert dry_payload.get("wouldDisableWorkspacePrimary") is True
    assert dry_payload.get("wouldClearAllowlist") is True
    assert dry_payload.get("applied") is False

    applied = client.post(
        "/api/v1/data-center/rollback-drill",
        json={"clientIds": [client_id], "dryRun": False},
    )
    assert applied.status_code == 200, applied.text
    applied_payload = applied.json()
    assert applied_payload.get("dryRun") is False
    assert applied_payload.get("applied") is True

    retrieval_settings = client.get("/api/v1/retrieval/settings")
    assert retrieval_settings.status_code == 200, retrieval_settings.text
    settings_payload = retrieval_settings.json()
    assert settings_payload.get("chatKernelPrimaryEnabled") is False
    assert settings_payload.get("chatKernelPrimaryClientAllowlist") == []
    assert client.app.state.app_state.db.get_setting("workspace_chat_data_center_primary", "1") == "0"
