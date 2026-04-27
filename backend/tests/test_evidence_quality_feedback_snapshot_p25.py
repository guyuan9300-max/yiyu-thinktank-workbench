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


def test_evidence_quality_feedback_snapshot_api_p25(tmp_path: Path):
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    now = datetime.now().replace(microsecond=0).isoformat()

    db.execute(
        """
        INSERT INTO evidence_quality_annotations(
            id, source_type, source_id, document_id, path, excerpt_hash, source_kind,
            quality_score, demotion_score, noise_reasons_json, authority_hint,
            human_label, human_note, created_at, updated_at
        )
        VALUES('eqa_snapshot_useful', 'workspace_chat', 'client_x', 'doc_1', '/tmp/doc_1', 'hash_1', 'raw_document',
               0.8, 0.0, '[]', 'raw', 'useful', 'good evidence', ?, ?)
        """,
        (now, now),
    )
    db.execute(
        """
        INSERT INTO evidence_quality_annotations(
            id, source_type, source_id, document_id, path, excerpt_hash, source_kind,
            quality_score, demotion_score, noise_reasons_json, authority_hint,
            human_label, human_note, created_at, updated_at
        )
        VALUES('eqa_snapshot_noise', 'workspace_chat', 'client_x', 'doc_2', '/tmp/doc_2', 'hash_2', 'ppt_master',
               0.2, 0.9, '["ppt_master"]', 'generated', 'noise', 'noise evidence', ?, ?)
        """,
        (now, now),
    )
    db.execute(
        """
        INSERT INTO evidence_quality_annotations(
            id, source_type, source_id, document_id, path, excerpt_hash, source_kind,
            quality_score, demotion_score, noise_reasons_json, authority_hint,
            human_label, human_note, created_at, updated_at
        )
        VALUES('eqa_snapshot_review', 'workspace_chat', 'client_x', 'doc_3', '/tmp/doc_3', 'hash_3', 'unknown',
               0.4, 0.1, '[]', 'unknown', 'needs_review', 'needs review', ?, ?)
        """,
        (now, now),
    )

    created = client.post("/api/v1/data-center/evidence-quality/snapshots", json={"days": 7})
    assert created.status_code == 200, created.text
    payload = created.json()
    assert payload.get("id")
    label_counts = payload.get("labelCounts") or {}
    assert label_counts.get("useful", 0) >= 1
    assert label_counts.get("noise", 0) >= 1
    assert label_counts.get("needs_review", 0) >= 1
    assert isinstance(payload.get("recommendedRules"), list)

    listed = client.get("/api/v1/data-center/evidence-quality/snapshots?limit=10")
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert rows
    assert any(str(item.get("id")) == payload.get("id") for item in rows)
