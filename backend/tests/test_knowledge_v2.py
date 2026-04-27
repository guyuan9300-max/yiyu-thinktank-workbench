from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.services import knowledge_base
from app.services.knowledge_v2 import (
    MAIN_KNOWLEDGE_STATUS_JOB_TYPES,
    _is_low_information_system_segment,
    _openable_paths_for_row,
    backfill_workspace_import,
    backfill_client_document_family_metadata,
    compute_knowledge_status,
    detect_material_profile,
    derive_document_family_id,
    extract_document,
    extract_document_with_metadata,
    ingest_document_knowledge,
    is_placeholder_machine_text,
    retrieve_knowledge_bundle,
)


def _insert_client(db: Database, client_id: str) -> None:
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            client_id,
            "检索测试客户",
            "检索测试客户",
            "公益",
            "内部陪伴",
            "用于知识分层测试",
            "推进中",
            "2026-03-15T00:00:00",
            "2026-03-15T00:00:00",
        ),
    )


def _insert_document_stub(
    db: Database,
    *,
    client_id: str,
    document_id: str,
    file_name: str,
    excerpt: str = "",
) -> None:
    db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, kind, source, excerpt, tags_json, created_at)
        VALUES(?, ?, NULL, ?, ?, 'txt', 'import', ?, '[]', '2026-03-15T00:00:00')
        """,
        (
            document_id,
            client_id,
            file_name,
            f"/tmp/{file_name}",
            excerpt,
        ),
    )


def _insert_ready_v2_document(
    db: Database,
    *,
    client_id: str,
    document_id: str,
    knowledge_document_id: str,
    v2_document_id: str,
    file_name: str,
    visible_category: str,
    secondary_category: str,
    preview_text: str,
    doc_index_text: str,
    section_content: str,
    canonical_kind: str = "raw_file",
    origin_type: str = "file_import",
    origin_id: str = "",
    content_hash: str = "",
) -> None:
    _insert_document_stub(
        db,
        client_id=client_id,
        document_id=document_id,
        file_name=file_name,
        excerpt=preview_text,
    )
    db.execute(
        """
        INSERT INTO knowledge_documents(
            id, client_id, import_batch_id, document_id, doc_uid, original_path, import_source_path, current_human_path,
            human_folder_category, reclassified_at, reclass_reason, reclass_confidence, normalized_path, kind,
            primary_category, secondary_category, classification_confidence, needs_review, deep_read, last_hit_question,
            dedup_status, vector_status, version, binary_hash, normalized_hash, created_at, updated_at
        )
        VALUES(
            ?, ?, NULL, ?, ?, ?, ?, ?,
            ?, NULL, NULL, 0.0, ?, 'md',
            ?, ?, 1.0, 0, 0, NULL,
            'unique', 'chunk_indexed', 1, ?, ?, '2026-03-15T00:00:00', '2026-03-15T00:00:00'
        )
        """,
        (
            knowledge_document_id,
            client_id,
            document_id,
            f"{document_id}_uid",
            f"/tmp/{file_name}",
            f"/tmp/{file_name}",
            f"/tmp/{file_name}",
            visible_category,
            f"/tmp/{file_name}",
            visible_category,
            secondary_category,
            f"binary_{document_id}",
            f"normalized_{document_id}",
        ),
    )
    db.execute(
        """
        INSERT INTO document_chunks(
            id, knowledge_document_id, chunk_index, section_label, content, token_count, created_at,
            document_family_id, canonical_kind, origin_type, origin_id, is_searchable
        )
        VALUES(?, ?, 0, '关键片段', ?, 32, '2026-03-15T00:00:00', '', ?, ?, ?, 1)
        """,
        (
            f"chunk_{document_id}",
            knowledge_document_id,
            section_content,
            canonical_kind,
            origin_type,
            origin_id or document_id,
        ),
    )
    db.execute(
        """
        INSERT INTO v2_documents(
            id, client_id, document_id, original_path, managed_path, markdown_path, file_name, kind,
            material_layer, visible_category, secondary_category, parse_status, parse_error, preview_text,
            doc_index_text, content_hash, classification_confidence, section_count, chunk_count, imported_at, updated_at,
            document_family_id, canonical_kind, origin_type, origin_id, is_searchable
        )
        VALUES(
            ?, ?, ?, ?, ?, NULL, ?, 'md',
            'evidence', ?, ?, 'ready', NULL, ?,
            ?, ?, 1.0, 1, 1, '2026-03-15T00:00:00', '2026-03-15T00:00:00',
            '', ?, ?, ?, 1
        )
        """,
        (
            v2_document_id,
            client_id,
            document_id,
            f"/tmp/{file_name}",
            f"/tmp/{file_name}",
            file_name,
            visible_category,
            secondary_category,
            preview_text,
            doc_index_text,
            content_hash or f"hash_{document_id}",
            canonical_kind,
            origin_type,
            origin_id or document_id,
        ),
    )
    db.execute(
        """
        INSERT INTO v2_sections(id, v2_document_id, section_index, title, content, searchable_text, char_count, created_at)
        VALUES(?, ?, 0, ?, ?, ?, ?, '2026-03-15T00:00:00')
        """,
        (
            f"sec_{document_id}",
            v2_document_id,
            visible_category,
            section_content,
            section_content,
            len(section_content),
        ),
    )


def test_detect_material_profile_moves_derived_intro_to_background():
    layer, category, secondary, confidence = detect_material_profile(
        "CFFC核心业务介绍_精简版.pdf",
        "下面这份说明，完全基于你提供的材料。为了便于你后续直接做 PPT 或对外介绍，我用定位—交付—工作模式的结构来写。",
        "项目与业务",
        "核心资料",
        0.74,
    )
    assert layer == "background"
    assert category == "战略陪伴"
    assert secondary == "派生整理稿"
    assert confidence >= 0.86


def test_ingest_document_knowledge_moves_derived_intro_into_background_layer(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    client_id = "client_reclass"
    _insert_client(db, client_id)
    document_id = "doc_intro"
    _insert_document_stub(
        db,
        client_id=client_id,
        document_id=document_id,
        file_name="CFFC核心业务介绍.txt",
        excerpt="派生介绍稿",
    )
    source_path = tmp_path / "CFFC核心业务介绍.txt"
    source_path.write_text(
        "下面这份说明，完全基于你提供的材料。为了便于你后续直接做 PPT 或对外介绍，我用定位—交付—工作模式的结构来写。",
        encoding="utf-8",
    )

    result = ingest_document_knowledge(
        db,
        data_dir=tmp_path / "data",
        client_id=client_id,
        import_id=None,
        document_id=document_id,
        source_path=source_path,
        original_source_path=source_path,
        title="CFFC核心业务介绍.txt",
        kind="txt",
        source="import",
        fallback_excerpt="派生介绍稿",
        created_at="2026-03-15T00:00:00",
        ai_service=None,
    )

    row = db.fetchone("SELECT material_layer, visible_category, secondary_category FROM v2_documents WHERE document_id = ?", (document_id,))
    assert row is not None
    assert str(row["material_layer"]) == "background"
    assert str(row["visible_category"]) == "战略陪伴"
    assert str(row["secondary_category"]) == "派生整理稿"
    assert result["material_layer"] == "background"


def test_ingest_pdf_persists_full_markdown_document(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app.services import knowledge_v2

    db = Database(tmp_path / "app.db")
    client_id = "client_pdf_markdown"
    document_id = "doc_pdf_markdown"
    _insert_client(db, client_id)
    _insert_document_stub(
        db,
        client_id=client_id,
        document_id=document_id,
        file_name="战略手册.pdf",
        excerpt="",
    )
    source_path = tmp_path / "战略手册.pdf"
    source_path.write_bytes(b"%PDF-1.4\n% text pdf placeholder")
    page_one = "第一页正文。" * 500
    page_two = "第二页正文。" * 500
    monkeypatch.setattr(
        knowledge_v2,
        "_read_pdf_text",
        lambda _path: (
            f"第 1 页\n{page_one}\n\n第 2 页\n{page_two}",
            [
                {"title": "第 1 页", "text": page_one},
                {"title": "第 2 页", "text": page_two},
            ],
        ),
    )

    result = ingest_document_knowledge(
        db,
        data_dir=tmp_path / "data",
        client_id=client_id,
        import_id=None,
        document_id=document_id,
        source_path=source_path,
        original_source_path=source_path,
        title="战略手册.pdf",
        kind="pdf",
        source="import",
        fallback_excerpt="",
        created_at="2026-03-15T00:00:00",
        ai_service=None,
    )

    row = db.fetchone(
        "SELECT markdown_path, markdown_content, preview_text, section_count, chunk_count FROM v2_documents WHERE document_id = ?",
        (document_id,),
    )
    assert row is not None
    markdown_content = str(row["markdown_content"] or "")
    assert markdown_content.startswith("# 战略手册.pdf")
    assert "## 第 1 页" in markdown_content
    assert "## 第 2 页" in markdown_content
    assert page_one in markdown_content
    assert page_two in markdown_content
    assert len(markdown_content) > len(str(row["preview_text"] or "")) * 5
    assert Path(str(row["markdown_path"])).read_text(encoding="utf-8") == markdown_content
    assert int(row["section_count"] or 0) == 2
    assert int(row["chunk_count"] or 0) >= 2
    assert result["parse_status"] == "ready"


def test_backfill_workspace_import_registers_existing_workspace_files(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    client_id = "client_backfill"
    _insert_client(db, client_id)

    workspace_root = tmp_path / "data" / "client_workspace" / client_id
    source_dir = workspace_root / "组织与战略"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "机构介绍.txt").write_text("日慈基金会专注于儿童心理健康与教师支持。", encoding="utf-8")

    summary = backfill_workspace_import(
        db,
        data_dir=tmp_path / "data",
        client_id=client_id,
        source_root=workspace_root,
    )

    assert summary["discovered"] == 1
    assert summary["imported"] == 1
    assert int(db.scalar("SELECT COUNT(1) AS count FROM imports WHERE client_id = ?", (client_id,))) == 1
    assert int(db.scalar("SELECT COUNT(1) AS count FROM documents WHERE client_id = ?", (client_id,))) == 1
    assert int(db.scalar("SELECT COUNT(1) AS count FROM knowledge_documents WHERE client_id = ?", (client_id,))) == 1
    assert int(db.scalar("SELECT COUNT(1) AS count FROM v2_documents WHERE client_id = ?", (client_id,))) == 1


def test_compute_knowledge_status_only_counts_main_job_allowlist(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    client_id = "client_status_allowlist"
    _insert_client(db, client_id)

    db.execute(
        """
        INSERT INTO knowledge_jobs(
            id, client_id, job_type, payload_json, total_items, processed_items, status,
            last_error, created_at, started_at, finished_at, updated_at
        )
        VALUES
            ('job_ingest', ?, ?, '{}', 1, 0, 'running', NULL, '2026-04-15T08:00:00', '2026-04-15T08:00:01', NULL, '2026-04-15T08:00:02'),
            ('job_dna', ?, 'generate_client_dna_candidates', '{}', 1, 0, 'running', 'ignored', '2026-04-15T08:00:03', '2026-04-15T08:00:04', NULL, '2026-04-15T08:00:05')
        """,
        (client_id, MAIN_KNOWLEDGE_STATUS_JOB_TYPES[0], client_id),
    )

    status = compute_knowledge_status(db, client_id)

    assert status["runningJobs"] == 1
    assert status["pendingJobs"] == 0
    assert status["lastJobStatus"] == "running"
    assert status["lastJobError"] is None


def test_backfill_client_document_family_metadata_merges_timestamped_and_copy_variants(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    client_id = "client_family_backfill"
    _insert_client(db, client_id)

    titles = [
        "20260403_131702_# 一、CFFC的核心定位与历史价值.docx",
        "20260403_130527_# 一、CFFC的核心定位与历史价值.md",
        "副本CFFC的核心定位与历史价值(1).pdf",
    ]
    document_ids = ["doc_family_a", "doc_family_b", "doc_family_c"]
    for document_id, title in zip(document_ids, titles, strict=True):
        _insert_ready_v2_document(
            db,
            client_id=client_id,
            document_id=document_id,
            knowledge_document_id=f"kd_{document_id}",
            v2_document_id=f"v2_{document_id}",
            file_name=title,
            visible_category="机构介绍",
            secondary_category="原始资料",
            preview_text="CFFC 的核心定位与历史价值。",
            doc_index_text="机构介绍 核心定位 历史价值",
            section_content="CFFC 的核心定位与历史价值，覆盖机构定位、项目逻辑与升级方向。",
        )

    summary = backfill_client_document_family_metadata(db, client_id)

    expected_family = derive_document_family_id(
        title="CFFC的核心定位与历史价值.docx",
        content_hash="hash_doc_family_a",
        origin_type="file_import",
        origin_id="doc_family_a",
    )
    families = {
        str(row["document_family_id"])
        for row in db.fetchall(
            "SELECT document_family_id FROM documents WHERE client_id = ? ORDER BY id ASC",
            (client_id,),
        )
    }
    v2_families = {
        str(row["document_family_id"])
        for row in db.fetchall(
            "SELECT document_family_id FROM v2_documents WHERE client_id = ? ORDER BY id ASC",
            (client_id,),
        )
    }
    chunk_families = {
        str(row["document_family_id"])
        for row in db.fetchall(
            """
            SELECT DISTINCT document_family_id
            FROM document_chunks
            WHERE knowledge_document_id IN (
                SELECT id FROM knowledge_documents WHERE client_id = ?
            )
            """,
            (client_id,),
        )
    }

    assert summary["updatedDocuments"] == 3
    assert summary["updatedV2Documents"] == 3
    assert families == {expected_family}
    assert v2_families == {expected_family}
    assert chunk_families == {expected_family}


def test_retrieve_knowledge_bundle_semantic_recall_can_append_new_doc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = Database(tmp_path / "app.db")
    client_id = "client_semantic_append"
    _insert_client(db, client_id)

    db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, kind, source, excerpt, tags_json, created_at)
        VALUES('doc_semantic_append', ?, NULL, '行动安排纪要', '/tmp/action-note.md', 'md', 'import', '后续安排包括负责人和截止时间。', '[]', '2026-03-15T00:00:00')
        """,
        (client_id,),
    )
    db.execute(
        """
        INSERT INTO knowledge_documents(
            id, client_id, import_batch_id, document_id, doc_uid, original_path, import_source_path, current_human_path,
            human_folder_category, reclassified_at, reclass_reason, reclass_confidence, normalized_path, kind,
            primary_category, secondary_category, classification_confidence, needs_review, deep_read, last_hit_question,
            dedup_status, vector_status, version, binary_hash, normalized_hash, created_at, updated_at
        )
        VALUES(
            'kd_semantic_append', ?, NULL, 'doc_semantic_append', 'doc_semantic_append_uid', '/tmp/action-note.md', '/tmp/action-note.md', '/tmp/action-note.md',
            '项目与业务', NULL, NULL, 0.0, '/tmp/action-note.md', 'md',
            '项目与业务', '会议纪要', 1.0, 0, 0, NULL,
            'unique', 'chunk_indexed', 1, 'binary_semantic_append', 'normalized_semantic_append', '2026-03-15T00:00:00', '2026-03-15T00:00:00'
        )
        """,
        (client_id,),
    )
    db.execute(
        """
        INSERT INTO v2_documents(
            id, client_id, document_id, original_path, managed_path, markdown_path, file_name, kind,
            material_layer, visible_category, secondary_category, parse_status, parse_error, preview_text,
            doc_index_text, content_hash, classification_confidence, section_count, chunk_count, imported_at, updated_at
        )
        VALUES(
            'v2doc_semantic_append', ?, 'doc_semantic_append', '/tmp/action-note.md', '/tmp/action-note.md', NULL, '行动安排纪要.md', 'md',
            'evidence', '项目与业务', '会议纪要', 'ready', NULL, '记录了行动项和后续安排。',
            '记录行动项安排和负责人', 'hash_semantic_append', 1.0, 1, 1, '2026-03-15T00:00:00', '2026-03-15T00:00:00'
        )
        """,
        (client_id,),
    )
    db.execute(
        """
        INSERT INTO v2_sections(id, v2_document_id, section_index, title, content, searchable_text, char_count, created_at)
        VALUES('sec_semantic_append', 'v2doc_semantic_append', 0, '会议行动', '后续安排包括：确认负责人、同步截止时间、更新风险清单。', '后续安排包括负责人和截止时间', 28, '2026-03-15T00:00:00')
        """,
    )
    db.execute(
        """
        INSERT INTO v2_chunks(id, v2_document_id, v2_section_id, chunk_index, section_label, content, searchable_text, char_count, created_at)
        VALUES('chunk_semantic_append', 'v2doc_semantic_append', 'sec_semantic_append', 0, '关键片段', '后续安排包括：确认负责人、同步截止时间、更新风险清单。', '后续安排包括负责人和截止时间', 28, '2026-03-15T00:00:00')
        """,
    )
    db.execute(
        """
        INSERT INTO knowledge_surrogates(
            id, knowledge_document_id, client_id, source_type, title, folder_category, surrogate_md_path,
            overview_summary, retrieval_summary, document_role, core_questions_json, query_hints_json,
            distinct_findings_json, entities_json, time_markers_json, source_links_json, created_at, updated_at
        )
        VALUES(
            'srg_semantic_append', 'kd_semantic_append', ?, 'document', '行动安排纪要', '项目与业务', '/tmp/action-note-surrogate.md',
            '概览', '用于语义召回测试', '原始证据', '[]', '[]', '[]', '[]', '[]', '[]', '2026-03-15T00:00:00', '2026-03-15T00:00:00'
        )
        """,
        (client_id,),
    )
    db.execute(
        """
        INSERT INTO knowledge_master_index(
            id, client_id, surrogate_id, title, folder_category, document_role, retrieval_summary,
            searchable_text, source_path, surrogate_md_path, updated_at
        )
        VALUES(
            'midx_semantic_append', ?, 'srg_semantic_append', '行动安排纪要', '项目与业务', '原始证据', '用于语义召回测试',
            '后续安排包括负责人和截止时间', '/tmp/action-note.md', '/tmp/action-note-surrogate.md', '2026-03-15T00:00:00'
        )
        """,
        (client_id,),
    )

    monkeypatch.setattr(
        knowledge_base,
        "search_master_index_qdrant",
        lambda *_args, **_kwargs: {"midx_semantic_append": 0.92},
    )
    monkeypatch.setattr(
        knowledge_base,
        "search_raw_chunks_qdrant",
        lambda *_args, **_kwargs: {},
    )

    bundle = retrieve_knowledge_bundle(db, tmp_path / "data", client_id, "负责人和截止时间怎么安排？")

    assert bundle.retrieval_summary["docHitCount"] >= 1
    assert bundle.retrieval_summary["rawChunkHitCount"] >= 1
    assert bundle.retrieval_summary["selectedDocumentFamilyCount"] >= 1
    assert "raw_file" in bundle.retrieval_summary["selectedCanonicalKinds"]
    assert any(
        "负责人" in citation.excerpt or "截止时间" in citation.excerpt
        for citation in bundle.citations
    )


def test_openable_paths_prefer_raw_original_over_machine_markdown(tmp_path: Path):
    workspace = tmp_path / "client_workspace"
    workspace.mkdir()
    original_path = workspace / "战略方案.docx"
    markdown_path = workspace / "_v2_meta" / "markdown" / "战略方案.md"
    original_path.write_text("raw", encoding="utf-8")
    markdown_path.parent.mkdir(parents=True)
    markdown_path.write_text("这是一份有效的机读稿，包含战略方案的关键内容和可检索正文。", encoding="utf-8")
    paths = _openable_paths_for_row(
        {
            "canonical_kind": "raw_file",
            "managed_path": str(original_path),
            "original_path": "/tmp/imports/战略方案.docx",
            "document_path": str(original_path),
            "original_source_path": "/Users/example/Desktop/战略方案.docx",
            "markdown_path": str(markdown_path),
        }
    )

    assert paths["path"] == str(original_path)
    assert paths["originalPath"] == str(original_path)
    assert paths["markdownPath"] == str(markdown_path)
    assert paths["openableKind"] == "original_file"
    assert paths["sourceAvailability"] == "original_available"
    assert paths["originalAvailable"] is True


def test_openable_paths_recovers_stale_raw_path_by_same_file_name(tmp_path: Path):
    root = tmp_path / "client_workspace" / "client_a"
    stale_path = root / "组织与战略" / "日慈战略合作 2_日慈_20260211.docx"
    actual_path = root / "_imports" / "imp_1" / "日慈战略合作 2_日慈_20260211.docx"
    actual_path.parent.mkdir(parents=True)
    actual_path.write_text("raw", encoding="utf-8")

    paths = _openable_paths_for_row(
        {
            "canonical_kind": "raw_file",
            "managed_path": str(stale_path),
            "original_path": str(stale_path),
            "document_path": str(stale_path),
            "original_source_path": "",
            "markdown_path": "",
        }
    )

    assert paths["path"] == str(actual_path)
    assert paths["originalPath"] == str(actual_path)
    assert paths["openableKind"] == "original_file"


def test_openable_paths_label_system_docs_as_cards_not_originals(tmp_path: Path):
    system_path = tmp_path / "client_workspace" / "_v2_meta" / "system_docs" / "task_doc" / "task_1.md"
    system_path.parent.mkdir(parents=True)
    system_path.write_text("这是一张系统整理卡片，包含任务背景、下一步动作和可检索正文。", encoding="utf-8")
    paths = _openable_paths_for_row(
        {
            "canonical_kind": "task_doc",
            "managed_path": str(system_path),
            "original_path": str(system_path),
            "document_path": str(system_path),
            "markdown_path": str(system_path),
        }
    )

    assert paths["path"].endswith("task_1.md")
    assert paths["originalPath"] is None
    assert paths["openableKind"] == "system_card"
    assert paths["sourceAvailability"] == "machine_readable_only"


def test_openable_paths_marks_missing_original_with_valid_markdown_as_machine_readable_only(tmp_path: Path):
    markdown_path = tmp_path / "client_workspace" / "_v2_meta" / "markdown" / "战略方案.md"
    markdown_path.parent.mkdir(parents=True)
    markdown_path.write_text("这是一份有效机读稿，保留了战略方案的正文和核心内容。", encoding="utf-8")

    paths = _openable_paths_for_row(
        {
            "canonical_kind": "raw_file",
            "managed_path": str(tmp_path / "missing" / "战略方案.docx"),
            "original_path": str(tmp_path / "missing" / "战略方案.docx"),
            "document_path": str(tmp_path / "missing" / "战略方案.docx"),
            "original_source_path": "",
            "markdown_path": str(markdown_path),
        }
    )

    assert paths["sourceAvailability"] == "machine_readable_only"
    assert paths["originalAvailable"] is False
    assert paths["machineReadableAvailable"] is True
    assert paths["openOriginalDisabledReason"]


def test_openable_paths_marks_zero_byte_original_and_placeholder_markdown_invalid(tmp_path: Path):
    original_path = tmp_path / "client_workspace" / "日慈战略核心思想 2_日慈_20260211.pdf"
    markdown_path = tmp_path / "client_workspace" / "_v2_meta" / "markdown" / "日慈战略核心思想.md"
    original_path.parent.mkdir(parents=True)
    original_path.write_bytes(b"")
    markdown_path.parent.mkdir(parents=True)
    markdown_path.write_text("# 日慈战略核心思想 2_日慈_20260211.pdf\n\n## 正文\n\n解析重试", encoding="utf-8")

    paths = _openable_paths_for_row(
        {
            "canonical_kind": "raw_file",
            "managed_path": str(original_path),
            "original_path": str(original_path),
            "document_path": str(original_path),
            "original_source_path": "",
            "markdown_path": str(markdown_path),
        }
    )

    assert paths["sourceAvailability"] == "invalid_source"
    assert paths["openableKind"] == "unknown"
    assert is_placeholder_machine_text(markdown_path.read_text(encoding="utf-8")) is True


def test_retrieve_knowledge_bundle_filters_placeholder_ready_documents(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    client_id = "client_placeholder_filter"
    _insert_client(db, client_id)

    _insert_ready_v2_document(
        db,
        client_id=client_id,
        document_id="doc_placeholder",
        knowledge_document_id="kd_placeholder",
        v2_document_id="v2_placeholder",
        file_name="日慈战略核心思想 2_日慈_20260211.pdf",
        visible_category="组织与战略",
        secondary_category="原始资料",
        preview_text="# 日慈战略核心思想 2_日慈_20260211.pdf\n\n## 正文\n\n解析重试",
        doc_index_text="解析重试",
        section_content="解析重试",
    )
    _insert_ready_v2_document(
        db,
        client_id=client_id,
        document_id="doc_valid",
        knowledge_document_id="kd_valid",
        v2_document_id="v2_valid",
        file_name="日慈战略真实资料.pdf",
        visible_category="组织与战略",
        secondary_category="原始资料",
        preview_text="日慈战略真实资料，包含组织定位、战略变化和核心资产。",
        doc_index_text="战略 组织定位 核心资产",
        section_content="日慈战略真实资料说明组织定位、战略变化和核心资产，是有效可检索正文。",
    )

    bundle = retrieve_knowledge_bundle(db, tmp_path / "data", client_id, "日慈战略核心资产")

    assert all("解析重试" not in citation.excerpt for citation in bundle.citations)
    assert any(citation.knowledge_document_id == "doc_valid" for citation in bundle.citations)


def test_low_information_task_segments_are_filtered_from_citations():
    assert _is_low_information_system_segment("task_doc", "下一步", "补充录音") is True
    assert _is_low_information_system_segment("task_doc", "下一步", "预期输出：诊断提纲V1+待补资料清单") is True
    assert (
        _is_low_information_system_segment(
            "task_doc",
            "下一步",
            "继续围绕项目传播清晰度推进具体动作，补充访谈对象、会议安排和资料清单。",
        )
        is False
    )


def test_retrieve_knowledge_bundle_intro_prefers_raw_files_in_pass1(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    client_id = "client_intro_bias"
    _insert_client(db, client_id)

    _insert_ready_v2_document(
        db,
        client_id=client_id,
        document_id="doc_intro_inst",
        knowledge_document_id="kd_intro_inst",
        v2_document_id="v2_intro_inst",
        file_name="日慈基金会机构介绍.docx",
        visible_category="机构介绍",
        secondary_category="原始资料",
        preview_text="机构介绍，聚焦儿童青少年心理健康。",
        doc_index_text="机构介绍 核心定位 心理健康",
        section_content="日慈基金会是一家聚焦儿童青少年心理健康与心理教育的公益机构，机构定位清晰。",
    )
    _insert_ready_v2_document(
        db,
        client_id=client_id,
        document_id="doc_intro_project",
        knowledge_document_id="kd_intro_project",
        v2_document_id="v2_intro_project",
        file_name="繁星计划项目介绍.docx",
        visible_category="项目资料",
        secondary_category="原始资料",
        preview_text="项目资料，介绍繁星计划服务路径。",
        doc_index_text="项目资料 项目特点 方法 路径",
        section_content="繁星计划是核心项目之一，说明服务路径、项目特点与交付方式。",
    )
    _insert_ready_v2_document(
        db,
        client_id=client_id,
        document_id="doc_intro_strategy",
        knowledge_document_id="kd_intro_strategy",
        v2_document_id="v2_intro_strategy",
        file_name="日慈战略说明.docx",
        visible_category="战略说明",
        secondary_category="原始资料",
        preview_text="战略说明，覆盖升级方向。",
        doc_index_text="战略说明 升级方向 第二曲线",
        section_content="战略说明聚焦升级方向、业务演进和未来布局。",
    )
    _insert_ready_v2_document(
        db,
        client_id=client_id,
        document_id="doc_intro_source",
        knowledge_document_id="kd_intro_source",
        v2_document_id="v2_intro_source",
        file_name="创始人访谈原件.docx",
        visible_category="访谈原件",
        secondary_category="原始资料",
        preview_text="访谈原件，解释机构为什么这样做。",
        doc_index_text="访谈原件 核心问题 怎么做",
        section_content="访谈原件补充了机构要解决的核心问题、方法论和项目逻辑。",
    )
    _insert_ready_v2_document(
        db,
        client_id=client_id,
        document_id="doc_intro_meeting",
        knowledge_document_id="kd_intro_meeting",
        v2_document_id="v2_intro_meeting",
        file_name="日慈基金会一季度沟通会议纪要.docx",
        visible_category="会议纪要",
        secondary_category="软件沉淀",
        preview_text="会议纪要里也提到了介绍、项目特点和机构定位。",
        doc_index_text="介绍 项目特点 机构定位 会议纪要",
        section_content="会议纪要提到了机构定位和项目特点，但它只是软件文档补充。",
        canonical_kind="meeting_doc",
        origin_type="meeting",
        origin_id="meeting-1",
    )

    bundle = retrieve_knowledge_bundle(db, tmp_path / "data", client_id, "介绍日慈基金会的项目特点")

    trail = bundle.retrieval_summary["backgroundTrail"]
    assert bundle.retrieval_summary["readingPassCount"] == 2
    assert trail[:4]
    assert all(item["canonicalKind"] == "raw_file" for item in trail[:3])
    assert "meeting_doc" in bundle.retrieval_summary["selectedCanonicalKinds"]


def test_extract_pdf_uses_ai_ocr_markdown_when_text_extract_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app.services import knowledge_v2

    source = tmp_path / "扫描战略.pdf"
    source.write_bytes(b"%PDF-1.4\n% image-only placeholder")

    monkeypatch.setattr(knowledge_v2, "_read_pdf_text", lambda _path: ("", []))
    monkeypatch.setattr(knowledge_v2, "_pdf_page_count", lambda _path: 2)
    monkeypatch.setattr(
        knowledge_v2,
        "_render_pdf_pages_for_ai_ocr",
        lambda _path, **_kwargs: [
            {"pageNumber": 1, "mimeType": "image/png", "imageBase64": "fake-page-1"},
            {"pageNumber": 2, "mimeType": "image/png", "imageBase64": "fake-page-2"},
        ],
    )

    class FakeAi:
        def __init__(self) -> None:
            self.calls: list[tuple[int, str]] = []

        def generate_pdf_page_markdown(self, *, title: str, page_number: int, image_base64: str, mime_type: str) -> str:
            self.calls.append((page_number, image_base64))
            return f"## 页面 {page_number}\n\nCFFC 战略价值与能力版图正文内容 {page_number}。" * 8

    ai = FakeAi()

    text, sections = extract_document(source, title="扫描战略.pdf", ai_service=ai)

    assert len(ai.calls) == 2
    assert "CFFC 战略价值与能力版图正文内容 1" in text
    assert "CFFC 战略价值与能力版图正文内容 2" in text
    assert [section["title"] for section in sections] == ["第 1 页", "第 2 页"]


def test_extract_pdf_ai_ocr_reads_batches_beyond_first_12_pages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app.services import knowledge_v2

    source = tmp_path / "长扫描战略.pdf"
    source.write_bytes(b"%PDF-1.4\n% long scan placeholder")

    calls: list[tuple[int, int]] = []

    monkeypatch.setattr(knowledge_v2, "_read_pdf_text", lambda _path: ("", []))
    monkeypatch.setattr(knowledge_v2, "_pdf_page_count", lambda _path: 20)

    def fake_render(_path: Path, *, start_page: int = 1, max_pages: int = 8, **_kwargs):
        calls.append((start_page, max_pages))
        return [
            {"pageNumber": page, "mimeType": "image/png", "imageBase64": f"fake-page-{page}"}
            for page in range(start_page, start_page + max_pages)
        ]

    monkeypatch.setattr(knowledge_v2, "_render_pdf_pages_for_ai_ocr", fake_render)

    class FakeAi:
        def generate_pdf_page_markdown(self, *, title: str, page_number: int, image_base64: str, mime_type: str) -> str:
            return f"## 页面 {page_number}\n\n长扫描战略正文第 {page_number} 页，包含客户战略、项目、运营和能力建设资料。" * 4

    extracted = extract_document_with_metadata(
        source,
        title="长扫描战略.pdf",
        ai_service=FakeAi(),
        ocr_max_pages=20,
        ocr_batch_size=8,
    )

    assert calls == [(1, 8), (9, 8), (17, 4)]
    assert extracted.metadata.parse_status == "ready"
    assert extracted.metadata.attempted_pages == 20
    assert extracted.metadata.succeeded_pages == 20
    assert "长扫描战略正文第 20 页" in extracted.text


def test_extract_pdf_ai_ocr_marks_partial_ready_when_page_limit_truncates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app.services import knowledge_v2

    source = tmp_path / "超长扫描战略.pdf"
    source.write_bytes(b"%PDF-1.4\n% very long scan placeholder")

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

    class FakeAi:
        def generate_pdf_page_markdown(self, *, title: str, page_number: int, image_base64: str, mime_type: str) -> str:
            return f"## 页面 {page_number}\n\n超长扫描战略正文第 {page_number} 页，包含可检索资料。" * 4

    extracted = extract_document_with_metadata(
        source,
        title="超长扫描战略.pdf",
        ai_service=FakeAi(),
        ocr_max_pages=60,
        ocr_batch_size=8,
    )

    assert extracted.metadata.parse_status == "partial_ready"
    assert extracted.metadata.attempted_pages == 60
    assert extracted.metadata.succeeded_pages == 60
    assert extracted.metadata.total_pages == 80
    assert "当前已处理到第 60 页" in str(extracted.metadata.parse_error)


def test_extract_pdf_ai_ocr_can_continue_past_60_pages_to_completion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app.services import knowledge_v2

    source = tmp_path / "超长扫描战略_全文.pdf"
    source.write_bytes(b"%PDF-1.4\n% very long scan placeholder")

    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(knowledge_v2, "_read_pdf_text", lambda _path: ("", []))
    monkeypatch.setattr(knowledge_v2, "_pdf_page_count", lambda _path: 80)

    def fake_render(_path: Path, *, start_page: int = 1, max_pages: int = 8, **_kwargs):
        calls.append((start_page, max_pages))
        return [
            {"pageNumber": page, "mimeType": "image/png", "imageBase64": f"fake-page-{page}"}
            for page in range(start_page, start_page + max_pages)
        ]

    monkeypatch.setattr(knowledge_v2, "_render_pdf_pages_for_ai_ocr", fake_render)

    class FakeAi:
        def generate_pdf_page_markdown(self, *, title: str, page_number: int, image_base64: str, mime_type: str) -> str:
            return f"## 页面 {page_number}\n\n超长扫描战略全文第 {page_number} 页，包含完整战略资料。" * 4

    extracted = extract_document_with_metadata(
        source,
        title="超长扫描战略_全文.pdf",
        ai_service=FakeAi(),
        ocr_max_pages=60,
        ocr_batch_size=8,
        ocr_continue_to_end=True,
    )

    assert extracted.metadata.parse_status == "ready"
    assert extracted.metadata.attempted_pages == 80
    assert extracted.metadata.succeeded_pages == 80
    assert extracted.metadata.parse_error is None
    assert "超长扫描战略全文第 80 页" in extracted.text
    assert calls[-1] == (77, 4)


def test_extract_pdf_keeps_failed_status_when_no_text_or_ai_ocr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app.services import knowledge_v2

    source = tmp_path / "空扫描.pdf"
    source.write_bytes(b"%PDF-1.4\n% image-only placeholder")

    monkeypatch.setattr(knowledge_v2, "_read_pdf_text", lambda _path: ("", []))
    monkeypatch.setattr(knowledge_v2, "_render_pdf_pages_for_ai_ocr", lambda _path, **_kwargs: [])

    text, sections = extract_document(source, title="空扫描.pdf", ai_service=object())

    assert text == ""
    assert sections == []


def test_extract_image_uses_visual_ocr_markdown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app.services import knowledge_v2

    source = tmp_path / "日慈战略.jpg"
    source.write_bytes(b"fake image")

    monkeypatch.setattr(
        knowledge_v2,
        "_render_image_for_ai_ocr",
        lambda _path: [
            {"pageNumber": 1, "mimeType": "image/png", "imageBase64": "fake-image"},
        ],
    )

    class FakeAi:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def generate_visual_markdown(self, *, title: str, page_number: int | None, image_base64: str, mime_type: str, source_kind: str) -> str:
            self.calls.append(source_kind)
            return "# 日慈战略\n\n韧性生态战略与儿童心理支持服务体系。" * 4

    ai = FakeAi()

    text, sections = extract_document(source, title="日慈战略.jpg", ai_service=ai)

    assert ai.calls == ["图片资料"]
    assert "韧性生态战略" in text
    assert [section["title"] for section in sections] == ["图片 1"]


def test_extract_image_keeps_failed_status_when_no_visual_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app.services import knowledge_v2

    source = tmp_path / "空白.jpg"
    source.write_bytes(b"fake image")

    monkeypatch.setattr(
        knowledge_v2,
        "_render_image_for_ai_ocr",
        lambda _path: [
            {"pageNumber": 1, "mimeType": "image/png", "imageBase64": "fake-image"},
        ],
    )

    class FakeAi:
        def generate_visual_markdown(self, *, title: str, page_number: int | None, image_base64: str, mime_type: str, source_kind: str) -> str:
            return ""

    text, sections = extract_document(source, title="空白.jpg", ai_service=FakeAi())

    assert text == ""
    assert sections == []


def test_partial_ready_document_is_indexed_and_retrievable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app.services import knowledge_v2

    db = Database(tmp_path / "app.db")
    client_id = "client_partial_ready"
    document_id = "doc_partial_pdf"
    _insert_client(db, client_id)
    _insert_document_stub(
        db,
        client_id=client_id,
        document_id=document_id,
        file_name="日慈战略超长扫描.pdf",
        excerpt="",
    )
    source = tmp_path / "日慈战略超长扫描.pdf"
    source.write_bytes(b"%PDF-1.4\n% partial ready placeholder")

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

    class FakeAi:
        def generate_pdf_page_markdown(self, *, title: str, page_number: int, image_base64: str, mime_type: str) -> str:
            return f"## 页面 {page_number}\n\n日慈战略资料第 {page_number} 页，说明儿童心理支持、项目升级和生态协作。" * 4

    result = ingest_document_knowledge(
        db,
        data_dir=tmp_path / "data",
        client_id=client_id,
        import_id=None,
        document_id=document_id,
        source_path=source,
        original_source_path=source,
        title="日慈战略超长扫描.pdf",
        kind="pdf",
        source="import",
        fallback_excerpt="",
        created_at="2026-03-15T00:00:00",
        ai_service=FakeAi(),
        ocr_max_pages=60,
        ocr_batch_size=8,
    )

    row = db.fetchone("SELECT parse_status, section_count, chunk_count FROM v2_documents WHERE document_id = ?", (document_id,))
    assert row is not None
    assert row["parse_status"] == "partial_ready"
    assert int(row["section_count"] or 0) > 0
    assert int(row["chunk_count"] or 0) > 0
    assert result["parse_status"] == "partial_ready"

    bundle = retrieve_knowledge_bundle(db, tmp_path / "data", client_id, "日慈战略资料")
    assert any("日慈战略超长扫描" in item.get("title", "") for item in bundle.retrieval_summary["backgroundTrail"])
