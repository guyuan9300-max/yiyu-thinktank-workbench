"""实体合并 + 候选检测测试（迭代 3）。"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.entity_merger import (
    _edit_distance,
    _score_pair,
    find_merge_candidates,
    merge_entities,
)


SCHEMA = """
CREATE TABLE clients (id TEXT PRIMARY KEY);
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
    first_seen_at TEXT NOT NULL DEFAULT '',
    last_seen_at TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE entity_mentions (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    v2_document_id TEXT,
    v2_chunk_id TEXT,
    mention_text TEXT,
    confidence REAL,
    created_at TEXT
);
CREATE TABLE relationship_triples (
    id TEXT PRIMARY KEY,
    client_id TEXT,
    subject_entity_id TEXT,
    predicate TEXT,
    object_entity_id TEXT,
    object_text TEXT,
    confidence REAL,
    source_v2_chunk_id TEXT,
    source_v2_document_id TEXT,
    evidence_text TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE atomic_facts (
    id TEXT PRIMARY KEY,
    client_id TEXT,
    subject_entity_id TEXT,
    subject_text TEXT,
    attribute TEXT,
    value_text TEXT,
    value_normalized TEXT,
    status TEXT DEFAULT 'active',
    updated_at TEXT,
    created_at TEXT,
    confidence REAL,
    source_v2_chunk_id TEXT,
    source_v2_document_id TEXT,
    evidence_text TEXT
);
CREATE TABLE entity_merge_log (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    surviving_entity_id TEXT NOT NULL,
    merged_entity_id TEXT NOT NULL,
    mentions_moved INTEGER NOT NULL DEFAULT 0,
    triples_moved INTEGER NOT NULL DEFAULT 0,
    facts_moved INTEGER NOT NULL DEFAULT 0,
    merge_reason TEXT,
    merged_by TEXT,
    created_at TEXT NOT NULL
);
INSERT INTO clients (id) VALUES ('cli-A');
"""


def _seed_entity(conn, *, id_, client_id, type_, name, mentions=0) -> None:
    conn.execute(
        "INSERT INTO entities (id, client_id, entity_type, normalized_name, "
        "display_name, mention_count) VALUES (?, ?, ?, ?, ?, ?)",
        (id_, client_id, type_, name, name, mentions),
    )


@pytest.fixture()
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


# ---- 评分函数 ------------------------------------------------------------


@pytest.mark.unit
def test_score_pair_identical() -> None:
    sim, _ = _score_pair("张总", "张总")
    assert sim == 1.0


@pytest.mark.unit
def test_score_pair_prefix() -> None:
    """张总 是 张总监 的前缀 → 0.85"""
    sim, reason = _score_pair("张总", "张总监")
    assert sim >= 0.85
    assert "前缀" in reason


@pytest.mark.unit
def test_score_pair_substring() -> None:
    """阿里科技 在 阿里科技有限公司 里 → 0.75"""
    sim, _ = _score_pair("阿里科技", "阿里科技有限公司")
    assert sim >= 0.75


@pytest.mark.unit
def test_score_pair_unrelated() -> None:
    sim, _ = _score_pair("张总", "李工")
    assert sim < 0.65


@pytest.mark.unit
def test_score_pair_edit_distance() -> None:
    """A组织科技 / 日兹科技：编辑距离 1，长度 ≥ 3 → 0.65"""
    sim, _ = _score_pair("A组织科技", "日兹科技")
    assert sim >= 0.65


@pytest.mark.unit
def test_edit_distance_basic() -> None:
    assert _edit_distance("abc", "abc") == 0
    assert _edit_distance("abc", "abd") == 1
    assert _edit_distance("kitten", "sitting") == 3


# ---- 候选发现 -------------------------------------------------------------


@pytest.mark.unit
def test_find_merge_candidates_returns_high_similarity(conn) -> None:
    _seed_entity(conn, id_="e1", client_id="cli-A", type_="person", name="张总", mentions=3)
    _seed_entity(conn, id_="e2", client_id="cli-A", type_="person", name="张总监", mentions=1)
    _seed_entity(conn, id_="e3", client_id="cli-A", type_="person", name="李工", mentions=5)

    cands = find_merge_candidates(conn, client_id="cli-A")
    pairs = {(c.name_a, c.name_b) for c in cands}
    assert ("张总", "张总监") in pairs or ("张总监", "张总") in pairs
    # 李工 不该匹配
    assert not any("李工" in (c.name_a, c.name_b) for c in cands)


@pytest.mark.unit
def test_find_merge_candidates_isolates_by_type(conn) -> None:
    """同名但 type 不同 → 不算重复（虽然现实里这种情况罕见）。"""
    _seed_entity(conn, id_="e1", client_id="cli-A", type_="person", name="A组织")
    _seed_entity(conn, id_="e2", client_id="cli-A", type_="company", name="A组织科技")
    cands = find_merge_candidates(conn, client_id="cli-A")
    assert cands == []


@pytest.mark.unit
def test_find_merge_candidates_isolates_by_client(conn) -> None:
    conn.execute("INSERT INTO clients (id) VALUES ('cli-B')")
    _seed_entity(conn, id_="e1", client_id="cli-A", type_="person", name="张总")
    _seed_entity(conn, id_="e2", client_id="cli-B", type_="person", name="张总监")
    cands_a = find_merge_candidates(conn, client_id="cli-A")
    cands_b = find_merge_candidates(conn, client_id="cli-B")
    assert cands_a == []
    assert cands_b == []


# ---- 合并 ----------------------------------------------------------------


@pytest.mark.unit
def test_merge_entities_moves_references(conn) -> None:
    _seed_entity(conn, id_="e_survive", client_id="cli-A", type_="person", name="张总监", mentions=3)
    _seed_entity(conn, id_="e_merged", client_id="cli-A", type_="person", name="张总", mentions=2)
    # 给 e_merged 加 mentions / triple / fact
    conn.execute(
        "INSERT INTO entity_mentions (id, entity_id, mention_text, confidence, created_at) "
        "VALUES ('m1', 'e_merged', '张总', 0.8, '2026-05-12')"
    )
    conn.execute(
        "INSERT INTO relationship_triples (id, client_id, subject_entity_id, predicate, "
        "object_text, confidence, created_at, updated_at) "
        "VALUES ('t1', 'cli-A', 'e_merged', 'works_at', 'A组织科技', 0.8, '2026-05-12', '2026-05-12')"
    )
    conn.execute(
        "INSERT INTO atomic_facts (id, client_id, subject_entity_id, subject_text, attribute, "
        "value_text, value_normalized, status, created_at, updated_at, confidence) "
        "VALUES ('f1', 'cli-A', 'e_merged', '张总', '职位', 'CEO', 'CEO', 'active', "
        "'2026-05-12', '2026-05-12', 0.8)"
    )

    moved = merge_entities(
        conn, client_id="cli-A", surviving_id="e_survive", merged_id="e_merged",
        merge_reason="测试合并",
    )
    assert moved == {"mentions_moved": 1, "triples_moved": 1, "facts_moved": 1}

    # 验证 mention 已迁移
    row = conn.execute("SELECT entity_id FROM entity_mentions WHERE id = 'm1'").fetchone()
    assert row["entity_id"] == "e_survive"

    # 验证 triple subject 已迁移
    row = conn.execute("SELECT subject_entity_id FROM relationship_triples WHERE id = 't1'").fetchone()
    assert row["subject_entity_id"] == "e_survive"

    # 验证 fact 已迁移
    row = conn.execute("SELECT subject_entity_id FROM atomic_facts WHERE id = 'f1'").fetchone()
    assert row["subject_entity_id"] == "e_survive"

    # 验证 surviving 的 mention_count = 3 + 2 = 5
    row = conn.execute("SELECT mention_count, aliases_json FROM entities WHERE id = 'e_survive'").fetchone()
    assert row["mention_count"] == 5
    import json as _json
    aliases = _json.loads(row["aliases_json"])
    assert "张总" in aliases  # merged display_name 加进 aliases

    # 验证 merged 状态变了
    row = conn.execute("SELECT status FROM entities WHERE id = 'e_merged'").fetchone()
    assert row["status"].startswith("merged_into:e_survive")

    # 验证日志
    row = conn.execute("SELECT mentions_moved, merge_reason FROM entity_merge_log").fetchone()
    assert row["mentions_moved"] == 1
    assert row["merge_reason"] == "测试合并"


@pytest.mark.unit
def test_merge_entities_rejects_cross_client(conn) -> None:
    conn.execute("INSERT INTO clients (id) VALUES ('cli-B')")
    _seed_entity(conn, id_="e_a", client_id="cli-A", type_="person", name="张总")
    _seed_entity(conn, id_="e_b", client_id="cli-B", type_="person", name="张总监")
    with pytest.raises(ValueError):
        merge_entities(conn, client_id="cli-A", surviving_id="e_a", merged_id="e_b")


@pytest.mark.unit
def test_merge_entities_rejects_same_id(conn) -> None:
    _seed_entity(conn, id_="e1", client_id="cli-A", type_="person", name="张总")
    with pytest.raises(ValueError):
        merge_entities(conn, client_id="cli-A", surviving_id="e1", merged_id="e1")


@pytest.mark.unit
def test_merge_entities_handles_object_side_of_triple(conn) -> None:
    """object_entity_id 引用 merged 也要迁。"""
    _seed_entity(conn, id_="e_survive", client_id="cli-A", type_="company", name="A组织科技有限公司")
    _seed_entity(conn, id_="e_merged", client_id="cli-A", type_="company", name="A组织科技")
    _seed_entity(conn, id_="e_other", client_id="cli-A", type_="person", name="王经理")
    conn.execute(
        "INSERT INTO relationship_triples (id, client_id, subject_entity_id, predicate, "
        "object_entity_id, object_text, confidence, created_at, updated_at) "
        "VALUES ('t1', 'cli-A', 'e_other', 'works_at', 'e_merged', 'A组织科技', 0.8, "
        "'2026-05-12', '2026-05-12')"
    )
    moved = merge_entities(
        conn, client_id="cli-A", surviving_id="e_survive", merged_id="e_merged",
    )
    assert moved["triples_moved"] == 1
    row = conn.execute("SELECT object_entity_id FROM relationship_triples WHERE id = 't1'").fetchone()
    assert row["object_entity_id"] == "e_survive"
