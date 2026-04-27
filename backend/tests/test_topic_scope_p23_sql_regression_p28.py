from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / 'data')
    client = TestClient(app)
    client.__enter__()
    return client


def test_topic_scope_external_evidence_review_does_not_require_client_id(tmp_path: Path):
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    now = datetime.now().replace(microsecond=0).isoformat()
    client.get('/api/v1/external-evidence-cards?limit=1')

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
            'evcard_topic_sql_p28',
            'https://example.com/topic',
            'example.com',
            'trusted_media',
            'topic scope evidence',
            None,
            '外部摘录',
            '外部摘要',
            'topic_candidate_1',
            0.72,
            now,
            now,
        ),
    )

    accepted = client.post('/api/v1/external-evidence-cards/evcard_topic_sql_p28/accept')
    assert accepted.status_code == 200, accepted.text
    payload = accepted.json()
    assert payload['status'] == 'accepted'
    assert payload['relatedScopeType'] == 'topic'
