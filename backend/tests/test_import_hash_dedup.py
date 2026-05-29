"""导入闸门内容 hash 去重 + 版本链测试（迭代 2 F3）。

锁定：
- hash_file_bytes 对真实文件能算出 SHA-256
- Database._init_schema 把 knowledge_documents 加上 lifecycle_status /
  superseded_by_id / version_chain_id / version_number 列
- imports 表加上 duplicate_count / unsupported_count / version_upgrade_count
- 索引建上
- 既有数据的 version_chain_id backfill 不留 NULL
"""
from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.services.knowledge_v2 import hash_file_bytes


@pytest.mark.unit
def test_hash_file_bytes_matches_manual_sha256(tmp_path: Path) -> None:
    payload = b"\x00" * 32 + "客户判断 · 预算 30 万".encode("utf-8")
    file_path = tmp_path / "sample.pdf"
    file_path.write_bytes(payload)

    expected = hashlib.sha256(payload).hexdigest()
    assert hash_file_bytes(file_path) == expected


@pytest.mark.unit
def test_hash_file_bytes_returns_none_for_missing() -> None:
    assert hash_file_bytes(Path("/tmp/__definitely_not_exists__.pdf")) is None


@pytest.mark.unit
def test_schema_migration_creates_version_chain_columns() -> None:
    """Database._init_schema 应当幂等添加 4 个版本链列 + 2 个索引。"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    db = Database(db_path)

    cols = {row["name"] for row in db.conn.execute("PRAGMA table_info(knowledge_documents)").fetchall()}
    assert "lifecycle_status" in cols
    assert "superseded_by_id" in cols
    assert "version_chain_id" in cols
    assert "version_number" in cols

    indexes = {
        row["name"]
        for row in db.conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
    }
    assert "idx_knowledge_docs_lifecycle" in indexes
    assert "idx_knowledge_docs_chain" in indexes


@pytest.mark.unit
def test_schema_migration_adds_import_skip_columns() -> None:
    """imports 表应当有 duplicate_count / unsupported_count / version_upgrade_count。"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)
    db = Database(db_path)

    cols = {row["name"] for row in db.conn.execute("PRAGMA table_info(imports)").fetchall()}
    assert "duplicate_count" in cols
    assert "unsupported_count" in cols
    assert "version_upgrade_count" in cols


@pytest.mark.unit
def test_schema_migration_is_idempotent() -> None:
    """二次构造 Database 不应当报错（CREATE/ALTER IF NOT EXISTS 兜底）。"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)
    Database(db_path)
    # 第二次构造——若有 ALTER 重复抛错，这里会失败
    Database(db_path)


@pytest.mark.unit
def test_version_chain_backfill_for_existing_rows() -> None:
    """既有 knowledge_documents 行应当被 backfill version_chain_id = id。"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)
    db = Database(db_path)

    # 暂时关闭外键，避免触及 clients 表的 NOT NULL 字段
    db.conn.execute("PRAGMA foreign_keys = OFF")
    db.conn.execute(
        """
        INSERT INTO knowledge_documents(
            id, client_id, document_id, doc_uid, original_path,
            kind, primary_category, secondary_category,
            binary_hash, normalized_hash, created_at, updated_at, version_chain_id
        ) VALUES (
            'kd-old-1', 'cli-1', 'doc-1', 'uid-1', '/p/a.pdf',
            'pdf', '其他', '', 'h1', 'h1', '2026-01-01', '2026-01-01', NULL
        )
        """
    )
    db.conn.commit()
    # 二次构造 Database 触发 backfill UPDATE
    db2 = Database(db_path)

    row = db2.conn.execute(
        "SELECT version_chain_id FROM knowledge_documents WHERE id = 'kd-old-1'"
    ).fetchone()
    assert row["version_chain_id"] == "kd-old-1"
