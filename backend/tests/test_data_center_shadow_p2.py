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


def create_client_record(client: TestClient, name: str = "shadow-client") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "shadow p2",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_data_center_shadow_runs_and_summary(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)

    resolve = client.post(
        "/api/v1/data-center/resolve",
        json={
            "scope": {
                "page": "workspace_chat",
                "scopeType": "client",
                "scopeId": client_id,
                "clientId": client_id,
            },
            "prompt": "请介绍一下这个客户",
            "mode": "answer",
            "shadow": True,
            "includeRawEvidence": False,
            "includeActionSuggestions": True,
        },
    )
    assert resolve.status_code == 200, resolve.text

    runs = client.get(
        "/api/v1/data-center/shadow-runs",
        params={"scopeType": "client", "scopeId": client_id, "limit": 20},
    )
    assert runs.status_code == 200, runs.text
    run_items = runs.json()
    assert len(run_items) >= 1
    assert run_items[0]["scopeId"] == client_id

    summary = client.get(
        "/api/v1/data-center/shadow-summary",
        params={"scopeType": "client", "scopeId": client_id},
    )
    assert summary.status_code == 200, summary.text
    payload = summary.json()
    assert payload["total"] >= 1
    assert "answerQualityPassRate" in payload
