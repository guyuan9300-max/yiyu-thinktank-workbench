from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def test_external_evidence_accept_reject_flow(tmp_path: Path):
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    now = datetime.now().replace(microsecond=0).isoformat()

    client.get("/api/v1/external-evidence-cards?limit=1")
    db.execute(
        """
        INSERT INTO external_evidence_cards(
            id, source_url, source_domain, source_tier, title, published_at,
            fact_excerpt, summary, tags_json, related_scope_type, related_scope_id,
            confidence, status, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, '[]', 'topic', ?, ?, 'candidate', ?, ?)
        """,
        (
            "evcard_p23_1",
            "https://example.com/article",
            "example.com",
            "trusted_media",
            "外部证据候选",
            None,
            "摘录",
            "摘要",
            "topic_1",
            0.66,
            now,
            now,
        ),
    )

    accept = client.post("/api/v1/external-evidence-cards/evcard_p23_1/accept")
    assert accept.status_code == 200, accept.text
    assert accept.json()["status"] == "accepted"

    accepted_rows = client.get("/api/v1/external-evidence-cards?status=accepted")
    assert accepted_rows.status_code == 200, accepted_rows.text
    assert any(item["id"] == "evcard_p23_1" for item in accepted_rows.json())

    reject = client.post("/api/v1/external-evidence-cards/evcard_p23_1/reject")
    assert reject.status_code == 200, reject.text
    assert reject.json()["status"] == "rejected"

