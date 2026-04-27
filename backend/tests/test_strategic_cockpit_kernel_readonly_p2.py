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


def create_client_record(client: TestClient, name: str = "strategic-kernel-client") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "strategic kernel p2",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_strategic_cockpit_kernel_is_readonly(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)

    db = client.app.state.app_state.db
    before_count = int(db.scalar("SELECT COUNT(1) AS count FROM judgment_versions") or 0)

    response = client.post(
        "/api/v1/data-center/resolve",
        json={
            "scope": {
                "page": "strategic_cockpit",
                "scopeType": "client",
                "scopeId": client_id,
                "clientId": client_id,
            },
            "prompt": "当前战略重点是什么？",
            "mode": "answer",
            "includeRawEvidence": False,
            "includeActionSuggestions": True,
            "shadow": True,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["routeDecision"] is not None
    assert payload["answerPlan"] is not None

    after_count = int(db.scalar("SELECT COUNT(1) AS count FROM judgment_versions") or 0)
    assert after_count == before_count
