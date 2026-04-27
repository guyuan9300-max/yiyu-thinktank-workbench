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


def create_client_record(client: TestClient, name: str = "meeting-kernel-client") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "meeting kernel p2",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def create_meeting(client: TestClient, client_id: str) -> str:
    response = client.post(
        f"/api/v1/clients/{client_id}/meetings",
        json={"title": "周会", "scheduledAt": "2026-04-21T10:00:00"},
    )
    assert response.status_code == 200, response.text
    return response.json()["meeting"]["id"]


def test_meeting_page_context_and_kernel_prep(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    meeting_id = create_meeting(client, client_id)

    page_context = client.get(
        f"/api/v1/meetings/{meeting_id}/page-context",
        params={"prompt": "总结这次会议", "includeRawEvidence": False},
    )
    assert page_context.status_code == 200, page_context.text
    pack = page_context.json()
    assert pack["page"] == "meeting_detail"
    assert pack["scopeId"] == meeting_id

    prep = client.post(
        "/api/v1/data-center/resolve",
        json={
            "scope": {
                "page": "meeting_detail",
                "scopeType": "meeting",
                "scopeId": meeting_id,
                "meetingId": meeting_id,
                "clientId": client_id,
            },
            "prompt": "请生成会议准备",
            "mode": "prep",
            "includeRawEvidence": False,
            "includeActionSuggestions": True,
            "shadow": True,
        },
    )
    assert prep.status_code == 200, prep.text
    payload = prep.json()
    assert payload["prepResult"] is not None
    assert payload["prepResult"]["prepType"] == "meeting"
