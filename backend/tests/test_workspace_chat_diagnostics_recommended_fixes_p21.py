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


def create_client_record(client: TestClient, name: str = "diagnostics-fixes") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "diagnostics fixes",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_workspace_chat_diagnostics_recommended_fixes(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    db = client.app.state.app_state.db
    ts = "2026-04-21T14:00:00"

    thread_id = "thread_diag"
    msg_id = "msg_diag"
    db.execute(
        """
        INSERT INTO chat_threads(id, client_id, title, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?)
        """,
        (thread_id, client_id, "diag", ts, ts),
    )
    db.execute(
        """
        INSERT INTO chat_messages(
            id, thread_id, role, content, structured_data_json, model_route, llm_invoked, provider_used,
            answer_mode, evidence_status, failure_reason, timing_json, retrieval_summary_json, evidence_json, status, created_at
        ) VALUES(?, ?, 'assistant', ?, '{}', ?, 0, NULL, 'grounded_fallback', 'partial', ?, ?, ?, ?, 'success', ?)
        """,
        (
            msg_id,
            thread_id,
            "fallback",
            "运行策略",
            "llm_read_timeout",
            to_json({"retrievalMs": 120.0, "llmMs": 3200.0, "totalMs": 3600.0}),
            to_json({"answerIntent": "general", "pageContextQuality": "usable", "rawChunkHitCount": 0}),
            to_json([{"title": "目录页", "path": "/tmp/目录.pptx", "sourceType": "draft", "excerpt": "短"}]),
            ts,
        ),
    )

    # Insert a parse-failed doc to trigger parse-related fix.
    db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, original_source_path, kind, source, excerpt, tags_json, created_at)
        VALUES(?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "diag_1",
            client_id,
            "扫描版.pdf",
            "",
            "",
            "pdf",
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
            "v2doc_diag_1",
            client_id,
            "diag_1",
            "",
            "",
            "",
            "扫描版.pdf",
            "pdf",
            "evidence",
            "misc",
            "",
            "failed",
            "扫描版 PDF 需要 OCR",
            "",
            "",
            "hash",
            0.2,
            ts,
            ts,
        ),
    )

    diagnostics = client.get(
        "/api/v1/runtime/workspace-chat-diagnostics",
        params={"clientId": client_id, "recentMessages": 20},
    )
    assert diagnostics.status_code == 200, diagnostics.text
    payload = diagnostics.json()
    assert isinstance(payload.get("rootCauseSummary"), list)
    assert len(payload["rootCauseSummary"]) >= 1
    assert isinstance(payload.get("recommendedFixes"), list)
    assert len(payload["recommendedFixes"]) >= 1
