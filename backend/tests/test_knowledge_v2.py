from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.services.knowledge_v2 import backfill_workspace_import, detect_material_profile, ingest_document_knowledge


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
