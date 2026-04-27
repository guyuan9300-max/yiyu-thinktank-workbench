from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.db import to_json


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str = "parse-failure-client") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "parse failure p2",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_parse_failure_list_and_retry(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    db = client.app.state.app_state.db

    source_file = tmp_path / "failed_doc.txt"
    source_file.write_text("这是一个可解析的文本，用于重试。", encoding="utf-8")

    doc_id = "doc_parse_1"
    ts = "2026-04-21T10:00:00"
    db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, original_source_path, kind, source, excerpt, tags_json, created_at)
        VALUES(?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            doc_id,
            client_id,
            "失败文档",
            str(source_file),
            str(source_file),
            "txt",
            "file",
            "",
            to_json([]),
            ts,
        ),
    )
    db.execute(
        """
        INSERT INTO v2_documents(
            id, client_id, document_id, original_path, managed_path, markdown_path, file_name, kind,
            material_layer, visible_category, secondary_category, parse_status, parse_error,
            preview_text, doc_index_text, content_hash, classification_confidence, imported_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"v2doc_{doc_id}",
            client_id,
            doc_id,
            str(source_file),
            str(source_file),
            str(source_file),
            "失败文档.txt",
            "txt",
            "evidence",
            "misc",
            "",
            "failed",
            "未能解析出可用正文",
            "",
            "",
            "hash",
            0.5,
            ts,
            ts,
        ),
    )

    listed = client.get(f"/api/v1/clients/{client_id}/knowledge/parse-failures")
    assert listed.status_code == 200, listed.text
    items = listed.json()
    assert len(items) >= 1
    assert any(item["documentId"] == doc_id for item in items)

    retried = client.post(
        f"/api/v1/clients/{client_id}/knowledge/parse-failures/retry",
        json={"documentIds": [doc_id], "force": False},
    )
    assert retried.status_code == 200, retried.text
    payload = retried.json()
    assert payload["attempted"] >= 1
    assert payload["succeeded"] >= 1
