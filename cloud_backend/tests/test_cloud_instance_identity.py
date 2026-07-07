from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app  # noqa: E402


def test_cloud_instance_id_is_stable_for_deployment(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(tmp_path / "cloud-data"))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_DEPLOYMENT_NAME", "test-deployment")
    client = TestClient(create_app())

    first = client.get("/api/v1/cloud-instance")
    second = client.get("/api/v1/cloud-instance")

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    first_payload = first.json()
    second_payload = second.json()
    assert first_payload["cloudInstanceId"].startswith("cli_")
    assert second_payload["cloudInstanceId"] == first_payload["cloudInstanceId"]
    assert second_payload["service"]
    assert second_payload["deploymentName"] == "test-deployment"
