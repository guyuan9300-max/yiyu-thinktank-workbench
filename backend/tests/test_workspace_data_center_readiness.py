from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import to_json  # noqa: E402
from app.main import create_app  # noqa: E402


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str = "readiness-client") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "workspace readiness",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def seed_document_and_v2_row(
    *,
    client: TestClient,
    client_id: str,
    doc_id: str,
    source_file: Path,
    parse_status: str,
    parse_error: str | None,
    kind: str = "txt",
) -> None:
    db = client.app.state.app_state.db
    ts = "2026-04-21T10:00:00"
    db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, original_source_path, kind, source, excerpt, tags_json, created_at)
        VALUES(?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            doc_id,
            client_id,
            f"资料-{doc_id}",
            str(source_file),
            str(source_file),
            kind,
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
            preview_text, doc_index_text, content_hash, classification_confidence, section_count, chunk_count, imported_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"v2doc_{doc_id}",
            client_id,
            doc_id,
            str(source_file),
            str(source_file),
            str(source_file),
                f"{doc_id}.{kind}",
                kind,
            "evidence",
            "misc",
            "",
            parse_status,
            parse_error,
            "",
            "",
            "hash",
            0.5,
            1,
            1,
            ts,
            ts,
        ),
    )


def test_workspace_data_center_readiness_lists_parse_failed_documents(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    source_file = tmp_path / "failed_doc.txt"
    source_file.write_text("解析失败重试测试", encoding="utf-8")
    seed_document_and_v2_row(
        client=client,
        client_id=client_id,
        doc_id="doc_failed_1",
        source_file=source_file,
        parse_status="failed",
        parse_error="未能解析出可用正文",
    )

    response = client.get(f"/api/v1/clients/{client_id}/workspace/data-center-readiness")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["summary"]["failedDocuments"] >= 1
    assert any(item["documentId"] == "doc_failed_1" for item in payload["documents"])
    assert any(fix["actionType"] == "retry_parse" for fix in payload["recommendedFixes"])


def test_workspace_data_center_readiness_treats_partial_ready_as_readable(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "readiness-partial-ready")
    partial_source = tmp_path / "partial_doc.pdf"
    failed_source = tmp_path / "failed_doc.pdf"
    partial_source.write_bytes(b"%PDF-1.4\npartial")
    failed_source.write_bytes(b"%PDF-1.4\nfailed")
    seed_document_and_v2_row(
        client=client,
        client_id=client_id,
        doc_id="doc_partial_ready",
        source_file=partial_source,
        parse_status="partial_ready",
        parse_error="OCR 部分完成：成功 60/60 页，PDF 共 80 页，当前最多处理 60 页。",
        kind="pdf",
    )
    seed_document_and_v2_row(
        client=client,
        client_id=client_id,
        doc_id="doc_empty_pdf",
        source_file=failed_source,
        parse_status="failed",
        parse_error="未能解析出可用正文",
        kind="pdf",
    )

    response = client.get(f"/api/v1/clients/{client_id}/workspace/data-center-readiness")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["summary"]["partialReadyDocuments"] == 1
    assert payload["summary"]["failedDocuments"] == 1
    assert payload["summary"]["parseFailureBuckets"]["empty_pdf"] == 1
    assert payload["summary"]["ocrRecoverableCount"] == 1
    failed_ids = [item["documentId"] for item in payload["documents"] if item["parseStatus"] not in {"ready", "partial_ready", "queued", "running", "processing", "parsing"}]
    assert "doc_partial_ready" not in failed_ids


def test_workspace_data_center_readiness_detects_missing_card_and_master_index(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "readiness-missing-index")
    source_file = tmp_path / "ready_doc.txt"
    source_file.write_text("ready 文档", encoding="utf-8")
    seed_document_and_v2_row(
        client=client,
        client_id=client_id,
        doc_id="doc_ready_1",
        source_file=source_file,
        parse_status="ready",
        parse_error=None,
    )

    response = client.get(f"/api/v1/clients/{client_id}/workspace/data-center-readiness")
    assert response.status_code == 200, response.text
    payload = response.json()
    target = next(item for item in payload["documents"] if item["documentId"] == "doc_ready_1")

    assert target["hasDocumentCard"] is False
    assert target["hasMasterIndex"] is False
    assert any(fix["actionType"] == "regenerate_document_cards" for fix in payload["recommendedFixes"])
    assert any(fix["actionType"] == "sync_master_index" for fix in payload["recommendedFixes"])


def test_workspace_data_center_readiness_action_rebuild_client_knowledge_queues_job(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "readiness-rebuild")

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/data-center-readiness/actions",
        json={"actionType": "rebuild_client_knowledge"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["actionType"] == "rebuild_client_knowledge"
    assert payload["status"] in {"queued", "completed"}
    assert payload["jobId"]


def test_workspace_data_center_readiness_action_retry_parse_queues_job(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "readiness-retry-parse")
    source_file = tmp_path / "retry_doc.txt"
    source_file.write_text("这是一个可解析文本", encoding="utf-8")
    seed_document_and_v2_row(
        client=client,
        client_id=client_id,
        doc_id="doc_retry_1",
        source_file=source_file,
        parse_status="failed",
        parse_error="初次解析失败",
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/data-center-readiness/actions",
        json={"actionType": "retry_parse", "targetIds": ["doc_retry_1"]},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["actionType"] == "retry_parse"
    assert payload["status"] == "queued"
    assert payload["jobId"]
    assert payload["affectedCount"] >= 1
    db = client.app.state.app_state.db
    job = db.fetchone("SELECT job_type, status, total_items FROM knowledge_jobs WHERE id = ?", (payload["jobId"],))
    assert job is not None
    assert job["job_type"] == "retry_parse"
    assert job["status"] in {"queued", "running", "completed"}
    assert int(job["total_items"] or 0) >= 1


def test_workspace_data_center_readiness_recommends_refresh_when_context_pack_stale(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "readiness-context-stale")
    source_file = tmp_path / "stale_doc.txt"
    source_file.write_text("ready 文档，晚于 context pack", encoding="utf-8")
    seed_document_and_v2_row(
        client=client,
        client_id=client_id,
        doc_id="doc_stale_1",
        source_file=source_file,
        parse_status="ready",
        parse_error=None,
    )
    db = client.app.state.app_state.db
    db.execute(
        """
        INSERT INTO context_packs(
            id, client_id, job_id, target_type, target_id, prompt_version,
            source_count, evidence_count, payload_json, stale_at, created_at, updated_at
        ) VALUES(?, ?, NULL, 'client', ?, 'analysis-center-v1', 1, 1, '{}', NULL, ?, ?)
        """,
        ("cp_stale_1", client_id, client_id, "2026-04-20T08:00:00", "2026-04-20T08:00:00"),
    )
    db.execute(
        "UPDATE v2_documents SET updated_at = ? WHERE document_id = ?",
        ("2026-04-21T12:00:00", "doc_stale_1"),
    )

    response = client.get(f"/api/v1/clients/{client_id}/workspace/data-center-readiness")
    assert response.status_code == 200, response.text
    payload = response.json()

    refresh_fix = next((fix for fix in payload["recommendedFixes"] if fix["actionType"] == "refresh_context_pack"), None)
    assert refresh_fix is not None
    assert "context pack" in str(refresh_fix["reason"])


def test_workspace_data_center_readiness_action_refresh_context_pack_returns_refresh_event(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "readiness-refresh-context")

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/data-center-readiness/actions",
        json={"actionType": "refresh_context_pack"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["actionType"] == "refresh_context_pack"
    assert payload["status"] in {"queued", "running", "completed"}
    assert payload.get("refreshEventId")


def test_workspace_data_center_readiness_action_retry_parse_without_targets_no_crash(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "readiness-retry-empty")

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/data-center-readiness/actions",
        json={"actionType": "retry_parse", "targetIds": []},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["actionType"] == "retry_parse"
    assert payload["status"] == "completed"
    assert payload["affectedCount"] == 0
