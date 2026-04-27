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


def create_client_record(client: TestClient, name: str = "evidence-quality-anno-p23") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "evidence quality annotations p23",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_evidence_quality_annotations_list_and_label(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    db = client.app.state.app_state.db
    now = datetime.now().replace(microsecond=0).isoformat()

    initial = client.get("/api/v1/data-center/evidence-quality?sourceType=workspace_chat&sourceId=client_a")
    assert initial.status_code == 200, initial.text

    db.execute(
        """
        INSERT INTO evidence_quality_annotations(
            id, source_type, source_id, document_id, path, excerpt_hash, source_kind,
            quality_score, demotion_score, noise_reasons_json, authority_hint,
            human_label, human_note, created_at, updated_at
        )
        VALUES(?, 'workspace_chat', ?, ?, ?, ?, 'raw_document', 0.82, 0.0, '[]', 'raw', NULL, '', ?, ?)
        """,
        (
            "eqa_p23_1",
            client_id,
            "doc_x",
            "/tmp/doc_x.txt",
            "hash_1",
            now,
            now,
        ),
    )

    listed = client.get(f"/api/v1/data-center/evidence-quality?sourceType=workspace_chat&sourceId={client_id}")
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert any(row["id"] == "eqa_p23_1" for row in rows)

    labeled = client.post(
        "/api/v1/data-center/evidence-quality/eqa_p23_1/label",
        json={"label": "useful", "note": "人工标注高价值"},
    )
    assert labeled.status_code == 200, labeled.text
    labeled_payload = labeled.json()
    assert labeled_payload["humanLabel"] == "useful"
    assert labeled_payload["humanNote"] == "人工标注高价值"

