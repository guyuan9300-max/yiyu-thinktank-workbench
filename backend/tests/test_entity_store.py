"""实体存储层测试（迭代 2）。

用 in-memory SQLite 验证 entities + entity_mentions 表的 CRUD 行为。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.entity_extractor import ExtractedEntity
from app.services.entity_store import (
    insert_mention,
    list_entities,
    persist_chunk_entities,
    update_chunk_entity_ids,
    upsert_entity,
)


SCHEMA = """
CREATE TABLE clients (id TEXT PRIMARY KEY);
CREATE TABLE v2_documents (id TEXT PRIMARY KEY);
CREATE TABLE v2_chunks (
    id TEXT PRIMARY KEY,
    v2_document_id TEXT,
    entity_ids_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    aliases_json TEXT NOT NULL DEFAULT '[]',
    attributes_json TEXT NOT NULL DEFAULT '{}',
    mention_count INTEGER NOT NULL DEFAULT 0,
    confidence REAL NOT NULL DEFAULT 0.0,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_entities_client_type_name
    ON entities(client_id, entity_type, normalized_name);
CREATE TABLE entity_mentions (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    v2_document_id TEXT NOT NULL,
    v2_chunk_id TEXT,
    mention_text TEXT NOT NULL,
    position_start INTEGER,
    position_end INTEGER,
    confidence REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL
);
INSERT INTO clients (id) VALUES ('client-A');
INSERT INTO v2_documents (id) VALUES ('doc-1');
INSERT INTO v2_chunks (id, v2_document_id) VALUES ('chunk-1', 'doc-1');
INSERT INTO v2_chunks (id, v2_document_id) VALUES ('chunk-2', 'doc-1');
"""


@pytest.fixture()
def conn() -> sqlite3.Connection:
    """In-memory SQLite + 复制最小 schema。"""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    return connection


@pytest.mark.unit
def test_upsert_entity_inserts_new_row(conn: sqlite3.Connection) -> None:
    entity = ExtractedEntity(
        entity_type="person",
        text="张总",
        normalized_name="张总",
        display_name="张总",
        confidence=0.8,
    )
    entity_id = upsert_entity(conn, client_id="client-A", entity=entity, now="2026-05-12T00:00:00+00:00")
    assert entity_id

    row = conn.execute("SELECT * FROM entities WHERE id = ?", (entity_id,)).fetchone()
    assert row["normalized_name"] == "张总"
    assert row["mention_count"] == 1
    assert row["confidence"] == 0.8


@pytest.mark.unit
def test_upsert_entity_dedupes_within_client_type_name(conn: sqlite3.Connection) -> None:
    """同 client + type + normalized_name 二次 upsert → 计数 +1，不新建行。"""
    entity = ExtractedEntity(
        entity_type="person",
        text="张总",
        normalized_name="张总",
        display_name="张总",
        confidence=0.8,
    )
    id1 = upsert_entity(conn, client_id="client-A", entity=entity, now="2026-05-12T00:00:00+00:00")
    id2 = upsert_entity(conn, client_id="client-A", entity=entity, now="2026-05-12T01:00:00+00:00")
    assert id1 == id2

    row = conn.execute("SELECT mention_count, last_seen_at FROM entities WHERE id = ?", (id1,)).fetchone()
    assert row["mention_count"] == 2
    assert row["last_seen_at"] == "2026-05-12T01:00:00+00:00"


@pytest.mark.unit
def test_upsert_entity_isolates_by_client_id(conn: sqlite3.Connection) -> None:
    """跨客户同名实体是两个独立行（客户隔离）。"""
    entity = ExtractedEntity(
        entity_type="company",
        text="日慈科技",
        normalized_name="日慈科技",
        display_name="日慈科技",
        confidence=0.7,
    )
    conn.execute("INSERT INTO clients (id) VALUES ('client-B')")

    id_a = upsert_entity(conn, client_id="client-A", entity=entity)
    id_b = upsert_entity(conn, client_id="client-B", entity=entity)
    assert id_a != id_b


@pytest.mark.unit
def test_upsert_entity_appends_alias_when_display_differs(conn: sqlite3.Connection) -> None:
    """同 normalized_name 但不同 display_name → alias 列表追加。"""
    base = ExtractedEntity(
        entity_type="company",
        text="日慈",
        normalized_name="日慈科技",
        display_name="日慈科技",
        confidence=0.7,
    )
    alias_form = ExtractedEntity(
        entity_type="company",
        text="日慈",
        normalized_name="日慈科技",
        display_name="日慈科技股份",
        confidence=0.7,
    )
    entity_id = upsert_entity(conn, client_id="client-A", entity=base)
    upsert_entity(conn, client_id="client-A", entity=alias_form)
    import json

    row = conn.execute("SELECT aliases_json FROM entities WHERE id = ?", (entity_id,)).fetchone()
    aliases = json.loads(row["aliases_json"])
    assert "日慈科技" in aliases
    assert "日慈科技股份" in aliases


@pytest.mark.unit
def test_insert_mention_records_position(conn: sqlite3.Connection) -> None:
    entity = ExtractedEntity(
        entity_type="amount",
        text="50万元",
        normalized_name="50万元",
        display_name="50万元",
        confidence=0.95,
        position_start=12,
        position_end=16,
    )
    entity_id = upsert_entity(conn, client_id="client-A", entity=entity)
    mention_id = insert_mention(
        conn,
        entity_id=entity_id,
        v2_document_id="doc-1",
        v2_chunk_id="chunk-1",
        entity=entity,
    )
    row = conn.execute(
        "SELECT mention_text, position_start, position_end FROM entity_mentions WHERE id = ?",
        (mention_id,),
    ).fetchone()
    assert row["mention_text"] == "50万元"
    assert row["position_start"] == 12
    assert row["position_end"] == 16


@pytest.mark.unit
def test_persist_chunk_entities_round_trip(conn: sqlite3.Connection) -> None:
    extracted = [
        ExtractedEntity("person", "张总", "张总", "张总", 0.75),
        ExtractedEntity("amount", "50万元", "50万元", "50万元", 0.95),
        ExtractedEntity("date", "2026-06-01", "2026-06-01", "2026-06-01", 0.9),
    ]
    entity_ids = persist_chunk_entities(
        conn,
        client_id="client-A",
        v2_document_id="doc-1",
        v2_chunk_id="chunk-1",
        extracted=extracted,
    )
    assert len(entity_ids) == 3

    chunk_row = conn.execute(
        "SELECT entity_ids_json FROM v2_chunks WHERE id = 'chunk-1'"
    ).fetchone()
    import json

    stored_ids = json.loads(chunk_row["entity_ids_json"])
    assert set(stored_ids) == set(entity_ids)

    mention_count = conn.execute(
        "SELECT COUNT(*) AS n FROM entity_mentions WHERE v2_chunk_id = 'chunk-1'"
    ).fetchone()["n"]
    assert mention_count == 3


@pytest.mark.unit
def test_persist_chunk_entities_increments_count_across_chunks(conn: sqlite3.Connection) -> None:
    """同 entity 出现在两个 chunk 里 → mention_count = 2，只有一个 entity 行。"""
    entity = ExtractedEntity("person", "张总", "张总", "张总", 0.75)

    persist_chunk_entities(
        conn,
        client_id="client-A",
        v2_document_id="doc-1",
        v2_chunk_id="chunk-1",
        extracted=[entity],
    )
    persist_chunk_entities(
        conn,
        client_id="client-A",
        v2_document_id="doc-1",
        v2_chunk_id="chunk-2",
        extracted=[entity],
    )

    rows = conn.execute("SELECT id, mention_count FROM entities").fetchall()
    assert len(rows) == 1
    assert rows[0]["mention_count"] == 2

    mention_rows = conn.execute(
        "SELECT v2_chunk_id FROM entity_mentions ORDER BY v2_chunk_id"
    ).fetchall()
    chunk_ids = {r["v2_chunk_id"] for r in mention_rows}
    assert chunk_ids == {"chunk-1", "chunk-2"}


@pytest.mark.unit
def test_list_entities_filters_by_type_and_query(conn: sqlite3.Connection) -> None:
    entities = [
        ExtractedEntity("person", "张总", "张总", "张总", 0.8),
        ExtractedEntity("person", "李工", "李工", "李工", 0.7),
        ExtractedEntity("company", "日慈科技", "日慈科技", "日慈科技", 0.7),
        ExtractedEntity("amount", "50万元", "50万元", "50万元", 0.95),
    ]
    for ent in entities:
        upsert_entity(conn, client_id="client-A", entity=ent)

    persons, total_persons = list_entities(conn, client_id="client-A", entity_type="person")
    assert total_persons == 2
    assert {p.normalized_name for p in persons} == {"张总", "李工"}

    zhang_only, total_zhang = list_entities(conn, client_id="client-A", name_query="张")
    assert total_zhang == 1
    assert zhang_only[0].normalized_name == "张总"

    all_rows, total_all = list_entities(conn, client_id="client-A")
    assert total_all == 4


@pytest.mark.unit
def test_update_chunk_entity_ids_writes_json(conn: sqlite3.Connection) -> None:
    update_chunk_entity_ids(conn, "chunk-1", ["e1", "e2", "e3"])
    row = conn.execute(
        "SELECT entity_ids_json FROM v2_chunks WHERE id = 'chunk-1'"
    ).fetchone()
    import json

    assert json.loads(row["entity_ids_json"]) == ["e1", "e2", "e3"]
