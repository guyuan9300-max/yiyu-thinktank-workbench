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


def create_client_record(client: TestClient, name: str = "kernel-rollout-rollback-p25") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "kernel rollout rollback p25",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_kernel_primary_rollout_rollback_disables_gate(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)

    started = client.post(
        "/api/v1/data-center/kernel-primary-rollout/start",
        json={"stage": "stage_1_client", "clientIds": [client_id], "note": "start for rollback"},
    )
    assert started.status_code == 200, started.text
    run_id = started.json().get("id")
    assert isinstance(run_id, str) and run_id

    rolled_back = client.post(
        f"/api/v1/data-center/kernel-primary-rollout/{run_id}/rollback",
        json={"reason": "manual rollback"},
    )
    assert rolled_back.status_code == 200, rolled_back.text
    payload = rolled_back.json()
    assert payload.get("status") == "rolled_back"
    assert payload.get("rollbackReason") == "manual rollback"

    retrieval_settings = client.get("/api/v1/retrieval/settings")
    assert retrieval_settings.status_code == 200, retrieval_settings.text
    settings_payload = retrieval_settings.json()
    assert settings_payload.get("chatKernelPrimaryEnabled") is False
    assert settings_payload.get("chatKernelPrimaryClientAllowlist") == []
    assert client.app.state.app_state.db.get_setting("workspace_chat_data_center_primary", "1") == "0"
