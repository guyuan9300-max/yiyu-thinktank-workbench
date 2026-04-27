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


def test_external_evidence_accepted_can_create_proposal_draft(tmp_path: Path):
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    now = datetime.now().replace(microsecond=0).isoformat()

    client.get("/api/v1/external-evidence-cards?limit=1")
    card_id = "evcard_to_proposal_p24"
    db.execute(
        """
        INSERT INTO external_evidence_cards(
            id, source_url, source_domain, source_tier, title, published_at,
            fact_excerpt, summary, tags_json, related_scope_type, related_scope_id,
            confidence, status, created_at, updated_at
        )
        VALUES(?, 'https://example.com/report', 'example.com', 'trusted_media', '外部证据', NULL,
               '摘录', '摘要', '[]', 'topic', 'topic_p24', 0.61, 'candidate', ?, ?)
        """,
        (card_id, now, now),
    )

    rejected = client.post(f"/api/v1/external-evidence-cards/{card_id}/create-proposal-draft")
    assert rejected.status_code == 409, rejected.text

    accepted = client.post(f"/api/v1/external-evidence-cards/{card_id}/accept")
    assert accepted.status_code == 200, accepted.text
    assert accepted.json().get("status") == "accepted"

    created = client.post(f"/api/v1/external-evidence-cards/{card_id}/create-proposal-draft")
    assert created.status_code == 200, created.text
    payload = created.json()
    assert payload.get("kind") == "evidence_request"
    assert payload.get("status") == "draft"

    linked_card = client.get("/api/v1/external-evidence-cards?status=accepted")
    assert linked_card.status_code == 200, linked_card.text
    rows = linked_card.json()
    matched = [item for item in rows if item.get("id") == card_id]
    assert matched
    assert matched[0].get("linkedProposalIds")
