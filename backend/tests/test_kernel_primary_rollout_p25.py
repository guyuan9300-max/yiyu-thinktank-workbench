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


def create_client_record(client: TestClient, name: str = "kernel-rollout-p25") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "kernel rollout p25",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_kernel_primary_rollout_start_and_complete(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)

    missing_clients = client.post(
        "/api/v1/data-center/kernel-primary-rollout/start",
        json={"stage": "stage_1_client", "clientIds": [], "note": "should fail"},
    )
    assert missing_clients.status_code == 400, missing_clients.text

    started = client.post(
        "/api/v1/data-center/kernel-primary-rollout/start",
        json={"stage": "stage_1_client", "clientIds": [client_id], "note": "start rollout"},
    )
    assert started.status_code == 200, started.text
    run = started.json()
    assert run.get("status") == "running"
    run_id = run.get("id")
    assert isinstance(run_id, str) and run_id
    assert run.get("clientIds") == [client_id]

    retrieval_settings = client.get("/api/v1/retrieval/settings")
    assert retrieval_settings.status_code == 200, retrieval_settings.text
    settings_payload = retrieval_settings.json()
    assert settings_payload.get("chatKernelPrimaryEnabled") is True
    assert settings_payload.get("chatKernelPrimaryClientAllowlist") == [client_id]
    assert client.app.state.app_state.db.get_setting("workspace_chat_data_center_primary", "0") == "1"

    completed = client.post(f"/api/v1/data-center/kernel-primary-rollout/{run_id}/complete")
    assert completed.status_code == 200, completed.text
    completed_payload = completed.json()
    assert completed_payload.get("status") in {"completed", "failed"}
    assert isinstance(completed_payload.get("metricsAfter"), dict)
    assert completed_payload.get("recommendedAction") in {"keep", "rollback", None}

    listed = client.get("/api/v1/data-center/kernel-primary-rollout")
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert any(str(item.get("id")) == run_id for item in rows)
