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


def create_client_record(client: TestClient, name: str = "parse-buckets-client") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "parse failure buckets",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_parse_failure_retry_failure_buckets(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    db = client.app.state.app_state.db

    missing_source_doc = "doc_missing_source"
    missing_file_doc = "doc_missing_file"
    empty_image_doc = "doc_empty_image"
    empty_image_path = tmp_path / "empty_image.jpg"
    empty_image_path.write_bytes(b"not-a-real-image")
    ts = "2026-04-21T12:00:00"
    for doc_id, managed_path in [
        (missing_source_doc, ""),
        (missing_file_doc, str(tmp_path / "no_such_file.txt")),
        (empty_image_doc, str(empty_image_path)),
    ]:
        kind = "jpg" if doc_id == empty_image_doc else "txt"
        db.execute(
            """
            INSERT INTO documents(id, client_id, folder_id, title, path, original_source_path, kind, source, excerpt, tags_json, created_at)
            VALUES(?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc_id,
                client_id,
                f"{doc_id}.txt",
                managed_path or str(tmp_path / f"{doc_id}.txt"),
                managed_path or str(tmp_path / f"{doc_id}.txt"),
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
                preview_text, doc_index_text, content_hash, classification_confidence, imported_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"v2doc_{doc_id}",
                client_id,
                doc_id,
                managed_path,
                managed_path,
                managed_path,
                f"{doc_id}.{kind}",
                kind,
                "evidence",
                "misc",
                "",
                "failed",
                "解析失败",
                "",
                "",
                "hash",
                0.5,
                ts,
                ts,
            ),
        )

    retried = client.post(
        f"/api/v1/clients/{client_id}/knowledge/parse-failures/retry",
        json={"documentIds": [missing_source_doc, missing_file_doc, empty_image_doc], "force": False},
    )
    assert retried.status_code == 200, retried.text
    payload = retried.json()
    assert payload["batchId"].startswith("parse_retry_")
    assert payload["failed"] >= 3
    assert isinstance(payload["failureBuckets"], dict)
    assert "items" in payload
    assert any(item["status"] == "failed" for item in payload["items"])
    assert any(item.get("failureType") in {"managed_path_missing", "file_missing"} for item in payload["items"])
    assert any(item.get("documentId") == empty_image_doc and item.get("failureType") == "empty_text" for item in payload["items"])


def test_parse_failure_retry_recovers_stale_path_from_imports(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "parse-retry-import-recovery")
    db = client.app.state.app_state.db

    doc_id = "doc_import_recovered"
    file_name = "日慈战略核心思想 2_日慈_20260211.txt"
    import_file_name = "日慈战略核心思想.txt"
    stale_path = tmp_path / "missing" / file_name
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    stale_path.write_bytes(b"")
    import_path = tmp_path / "data" / "client_workspace" / client_id / "_imports" / "imp_retry" / import_file_name
    import_path.parent.mkdir(parents=True, exist_ok=True)
    import_path.write_text("日慈战略核心思想：以儿童心理支持为核心，推进项目升级与公益服务。", encoding="utf-8")
    ts = "2026-04-21T12:00:00"
    db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, original_source_path, kind, source, excerpt, tags_json, created_at)
        VALUES(?, ?, NULL, ?, ?, ?, 'txt', 'file', '', ?, ?)
        """,
        (doc_id, client_id, file_name, str(stale_path), str(stale_path), to_json([]), ts),
    )
    db.execute(
        """
        INSERT INTO v2_documents(
            id, client_id, document_id, original_path, managed_path, markdown_path, file_name, kind,
            material_layer, visible_category, secondary_category, parse_status, parse_error,
            preview_text, doc_index_text, content_hash, classification_confidence, imported_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, NULL, ?, 'txt', 'evidence', '组织与战略', '', 'failed', '源文件路径失效', '', '', 'hash', 0.5, ?, ?)
        """,
        (f"v2doc_{doc_id}", client_id, doc_id, str(stale_path), str(stale_path), file_name, ts, ts),
    )

    retried = client.post(
        f"/api/v1/clients/{client_id}/knowledge/parse-failures/retry",
        json={"documentIds": [doc_id], "force": False},
    )
    assert retried.status_code == 200, retried.text
    payload = retried.json()
    assert payload["attempted"] == 1
    assert payload["succeeded"] == 1
    row = db.fetchone("SELECT parse_status, section_count, chunk_count FROM v2_documents WHERE document_id = ?", (doc_id,))
    assert row is not None
    assert row["parse_status"] == "ready"
    assert int(row["section_count"] or 0) >= 1
    assert int(row["chunk_count"] or 0) >= 1


def test_parse_failure_retry_force_reprocesses_placeholder_ready_doc(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "parse-retry-force-placeholder")
    db = client.app.state.app_state.db

    doc_id = "doc_placeholder_ready"
    file_name = "日慈战略结构 2_日慈_20260211.txt"
    import_file_name = "日慈战略结构.txt"
    stale_path = tmp_path / "missing" / file_name
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    stale_path.write_bytes(b"")
    import_path = tmp_path / "data" / "client_workspace" / client_id / "_imports" / "imp_retry" / import_file_name
    import_path.parent.mkdir(parents=True, exist_ok=True)
    import_path.write_text("日慈战略结构：教育实践、路径提炼、生态协作三大飞轮。", encoding="utf-8")
    ts = "2026-04-21T12:00:00"
    db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, original_source_path, kind, source, excerpt, tags_json, created_at)
        VALUES(?, ?, NULL, ?, ?, ?, 'txt', 'file', '解析重试', ?, ?)
        """,
        (doc_id, client_id, file_name, str(stale_path), str(stale_path), to_json([]), ts),
    )
    db.execute(
        """
        INSERT INTO v2_documents(
            id, client_id, document_id, original_path, managed_path, markdown_path, file_name, kind,
            material_layer, visible_category, secondary_category, parse_status, parse_error,
            preview_text, doc_index_text, content_hash, classification_confidence, section_count, chunk_count, imported_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, NULL, ?, 'txt', 'evidence', '组织与战略', '', 'ready', NULL, '解析重试', '解析重试', 'hash', 0.5, 1, 1, ?, ?)
        """,
        (f"v2doc_{doc_id}", client_id, doc_id, str(stale_path), str(stale_path), file_name, ts, ts),
    )

    retried = client.post(
        f"/api/v1/clients/{client_id}/knowledge/parse-failures/retry",
        json={"documentIds": [doc_id], "force": True},
    )
    assert retried.status_code == 200, retried.text
    payload = retried.json()
    assert payload["attempted"] == 1
    assert payload["succeeded"] == 1
    row = db.fetchone("SELECT parse_status, preview_text FROM v2_documents WHERE document_id = ?", (doc_id,))
    assert row is not None
    assert row["parse_status"] == "ready"
    assert "三大飞轮" in row["preview_text"]


def test_parse_failure_retry_accepts_partial_ready_pdf(tmp_path: Path, monkeypatch):
    from app.services import knowledge_v2

    client = make_client(tmp_path)
    client_id = create_client_record(client, "parse-retry-partial-pdf")
    db = client.app.state.app_state.db

    doc_id = "doc_partial_retry_pdf"
    source_path = tmp_path / "长扫描资料.pdf"
    source_path.write_bytes(b"%PDF-1.4\npartial scan")
    ts = "2026-04-21T12:00:00"
    db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, original_source_path, kind, source, excerpt, tags_json, created_at)
        VALUES(?, ?, NULL, ?, ?, ?, 'pdf', 'file', '', ?, ?)
        """,
        (doc_id, client_id, source_path.name, str(source_path), str(source_path), to_json([]), ts),
    )
    db.execute(
        """
        INSERT INTO v2_documents(
            id, client_id, document_id, original_path, managed_path, markdown_path, file_name, kind,
            material_layer, visible_category, secondary_category, parse_status, parse_error,
            preview_text, doc_index_text, content_hash, classification_confidence, imported_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, NULL, ?, 'pdf', 'evidence', '组织与战略', '', 'failed', '未能解析出可用正文', '', '', 'hash', 0.5, ?, ?)
        """,
        (f"v2doc_{doc_id}", client_id, doc_id, str(source_path), str(source_path), source_path.name, ts, ts),
    )

    monkeypatch.setattr(knowledge_v2, "_read_pdf_text", lambda _path: ("", []))
    monkeypatch.setattr(knowledge_v2, "_pdf_page_count", lambda _path: 20)
    monkeypatch.setattr(
        knowledge_v2,
        "_render_pdf_pages_for_ai_ocr",
        lambda _path, *, start_page=1, max_pages=8, **_kwargs: [
            {"pageNumber": page, "mimeType": "image/png", "imageBase64": f"fake-page-{page}"}
            for page in range(start_page, start_page + max_pages)
        ],
    )

    def fake_pdf_page_markdown(*, title: str, page_number: int, image_base64: str, mime_type: str) -> str:
        return f"## 页面 {page_number}\n\n长扫描资料第 {page_number} 页，包含战略、项目和运营材料。" * 4

    def fake_visual_markdown(*, title: str, page_number: int | None, image_base64: str, mime_type: str, source_kind: str) -> str:
        return fake_pdf_page_markdown(
            title=title,
            page_number=int(page_number or 1),
            image_base64=image_base64,
            mime_type=mime_type,
        )

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_visual_markdown", fake_visual_markdown, raising=False)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_pdf_page_markdown", fake_pdf_page_markdown, raising=False)

    retried = client.post(
        f"/api/v1/clients/{client_id}/knowledge/parse-failures/retry",
        json={"documentIds": [doc_id], "force": False, "ocrMaxPages": 16, "ocrBatchSize": 8, "ocrContinueToEnd": False},
    )
    assert retried.status_code == 200, retried.text
    payload = retried.json()
    assert payload["attempted"] == 1
    assert payload["succeeded"] == 1
    row = db.fetchone("SELECT parse_status, section_count, chunk_count, parse_error FROM v2_documents WHERE document_id = ?", (doc_id,))
    assert row is not None
    assert row["parse_status"] == "partial_ready"
    assert int(row["section_count"] or 0) == 16
    assert int(row["chunk_count"] or 0) >= 1
    assert "当前已处理到第 16 页" in row["parse_error"]


def test_parse_failure_retry_can_continue_long_pdf_to_end(tmp_path: Path, monkeypatch):
    from app.services import knowledge_v2

    client = make_client(tmp_path)
    client_id = create_client_record(client, "parse-retry-continue-long-pdf")
    db = client.app.state.app_state.db

    doc_id = "doc_continue_retry_pdf"
    source_path = tmp_path / "超长扫描资料.pdf"
    source_path.write_bytes(b"%PDF-1.4\ncontinue scan")
    ts = "2026-04-21T12:00:00"
    db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, original_source_path, kind, source, excerpt, tags_json, created_at)
        VALUES(?, ?, NULL, ?, ?, ?, 'pdf', 'file', '', ?, ?)
        """,
        (doc_id, client_id, source_path.name, str(source_path), str(source_path), to_json([]), ts),
    )
    db.execute(
        """
        INSERT INTO v2_documents(
            id, client_id, document_id, original_path, managed_path, markdown_path, file_name, kind,
            material_layer, visible_category, secondary_category, parse_status, parse_error,
            preview_text, doc_index_text, content_hash, classification_confidence, imported_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, NULL, ?, 'pdf', 'evidence', '组织与战略', '', 'failed', '未能解析出可用正文', '', '', 'hash', 0.5, ?, ?)
        """,
        (f"v2doc_{doc_id}", client_id, doc_id, str(source_path), str(source_path), source_path.name, ts, ts),
    )

    monkeypatch.setattr(knowledge_v2, "_read_pdf_text", lambda _path: ("", []))
    monkeypatch.setattr(knowledge_v2, "_pdf_page_count", lambda _path: 80)
    monkeypatch.setattr(
        knowledge_v2,
        "_render_pdf_pages_for_ai_ocr",
        lambda _path, *, start_page=1, max_pages=8, **_kwargs: [
            {"pageNumber": page, "mimeType": "image/png", "imageBase64": f"fake-page-{page}"}
            for page in range(start_page, start_page + max_pages)
        ],
    )

    def fake_pdf_page_markdown(*, title: str, page_number: int, image_base64: str, mime_type: str) -> str:
        return f"## 页面 {page_number}\n\n超长扫描资料第 {page_number} 页，包含完整材料。" * 4

    def fake_visual_markdown(*, title: str, page_number: int | None, image_base64: str, mime_type: str, source_kind: str) -> str:
        return fake_pdf_page_markdown(
            title=title,
            page_number=int(page_number or 1),
            image_base64=image_base64,
            mime_type=mime_type,
        )

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_visual_markdown", fake_visual_markdown, raising=False)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_pdf_page_markdown", fake_pdf_page_markdown, raising=False)

    retried = client.post(
        f"/api/v1/clients/{client_id}/knowledge/parse-failures/retry",
        json={"documentIds": [doc_id], "force": False, "ocrMaxPages": 60, "ocrBatchSize": 8, "ocrContinueToEnd": True},
    )
    assert retried.status_code == 200, retried.text
    payload = retried.json()
    assert payload["attempted"] == 1
    assert payload["succeeded"] == 1
    row = db.fetchone("SELECT parse_status, section_count, chunk_count, parse_error FROM v2_documents WHERE document_id = ?", (doc_id,))
    assert row is not None
    assert row["parse_status"] == "ready"
    assert int(row["section_count"] or 0) == 80
    assert int(row["chunk_count"] or 0) >= 1
    assert row["parse_error"] is None
