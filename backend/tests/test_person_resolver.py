from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.services.ingest_pipeline import IngestMetadata, IngestRequest, IngestPipeline
from app.services.person_resolver import (
    backfill_speaker_entity_ids,
    build_client_roster_hint,
    match_mirror_user,
    resolve_person_name,
)


def _fresh_db() -> Database:
    db = Database(Path(tempfile.mkdtemp()) / "t.db")
    db.conn.execute("PRAGMA foreign_keys=OFF")
    # 用最小可控的 mirror_users 表(去掉只读触发器), 便于测试
    db.conn.execute("DROP TABLE IF EXISTS mirror_users")
    db.conn.execute("CREATE TABLE mirror_users (id TEXT PRIMARY KEY, full_name TEXT)")
    return db


def _person_count(db: Database, client_id: str) -> int:
    return int(
        db.conn.execute(
            "SELECT COUNT(*) FROM entities WHERE client_id = ? AND entity_type = 'person'",
            (client_id,),
        ).fetchone()[0]
    )


def test_resolve_internal_employee_with_title_variant() -> None:
    db = _fresh_db()
    db.conn.execute("INSERT INTO mirror_users(id, full_name) VALUES('u1', '张真')")
    entity_id = resolve_person_name(db.conn, client_id="c1", name="张真老师")
    assert entity_id
    row = db.conn.execute(
        "SELECT resolved_kind, mirror_user_id FROM entities WHERE id = ?", (entity_id,)
    ).fetchone()
    assert row["resolved_kind"] == "internal"
    assert row["mirror_user_id"] == "u1"


def test_match_mirror_user_exact_and_miss() -> None:
    db = _fresh_db()
    db.conn.execute("INSERT INTO mirror_users(id, full_name) VALUES('u1', '王强')")
    assert match_mirror_user(db.conn, "王强") == "u1"
    assert match_mirror_user(db.conn, "完全不认识的人") is None


def test_resolve_idempotent_same_entity_no_inflation() -> None:
    db = _fresh_db()
    first = resolve_person_name(db.conn, client_id="c1", name="李四")
    second = resolve_person_name(db.conn, client_id="c1", name="李四")
    assert first == second
    assert _person_count(db, "c1") == 1
    mention = db.conn.execute(
        "SELECT mention_count FROM entities WHERE id = ?", (first,)
    ).fetchone()[0]
    assert mention == 0  # resolve 不灌 mention_count(抽取侧才计数)


def test_resolve_unknown_person_stays_unknown() -> None:
    db = _fresh_db()
    entity_id = resolve_person_name(db.conn, client_id="c1", name="某陌生客户代表")
    row = db.conn.execute(
        "SELECT resolved_kind, mirror_user_id FROM entities WHERE id = ?", (entity_id,)
    ).fetchone()
    assert row["resolved_kind"] == "unknown"
    assert row["mirror_user_id"] is None


def test_resolve_empty_name_returns_none() -> None:
    db = _fresh_db()
    assert resolve_person_name(db.conn, client_id="c1", name="   ") is None


def test_backfill_sets_speaker_entity_id() -> None:
    db = _fresh_db()
    db.conn.execute("INSERT INTO mirror_users(id, full_name) VALUES('u1', '顾源源')")
    db.conn.execute(
        "INSERT INTO atomic_facts (id, client_id, subject_text, attribute, value_text, "
        "value_normalized, speaker_person_id, created_at, updated_at) "
        "VALUES ('f1', 'c1', 's', 'a', 'v', 'v', '顾源源', 't', 't')"
    )
    n = backfill_speaker_entity_ids(db.conn, client_id="c1")
    assert n == 1
    row = db.conn.execute(
        "SELECT speaker_entity_id FROM atomic_facts WHERE id = 'f1'"
    ).fetchone()
    assert row["speaker_entity_id"]
    ent = db.conn.execute(
        "SELECT resolved_kind, mirror_user_id FROM entities WHERE id = ?",
        (row["speaker_entity_id"],),
    ).fetchone()
    assert ent["resolved_kind"] == "internal"
    assert ent["mirror_user_id"] == "u1"


def test_backfill_idempotent_second_run_zero() -> None:
    db = _fresh_db()
    db.conn.execute(
        "INSERT INTO atomic_facts (id, client_id, subject_text, attribute, value_text, "
        "value_normalized, speaker_person_id, created_at, updated_at) "
        "VALUES ('f1', 'c1', 's', 'a', 'v', 'v', '某人', 't', 't')"
    )
    assert backfill_speaker_entity_ids(db.conn, client_id="c1") == 1
    assert backfill_speaker_entity_ids(db.conn, client_id="c1") == 0


def test_roster_hint_includes_employees_and_known_persons() -> None:
    db = _fresh_db()  # 最小 mirror_users(id, full_name) → 触发 primary_role 缺列回退
    db.conn.execute("INSERT INTO mirror_users(id, full_name) VALUES('u1', '顾源源')")
    db.conn.execute(
        "INSERT INTO entities(id, client_id, entity_type, normalized_name, display_name, "
        "first_seen_at, last_seen_at, created_at, updated_at) "
        "VALUES('e1','c1','person','张真','张真','t','t','t','t')"
    )
    hint = build_client_roster_hint(db.conn, "c1")
    assert "顾源源" in hint and "益语团队" in hint
    assert "张真" in hint and "已知人物" in hint


def test_roster_hint_empty_when_no_data() -> None:
    db = _fresh_db()
    assert build_client_roster_hint(db.conn, "c_none") == ""


def test_ingest_pipeline_resolves_speaker_entity_id() -> None:
    """端到端: 真 IngestPipeline.ingest() 写带 speaker 的事实, 自动解析 speaker_entity_id。"""
    db = _fresh_db()
    db.conn.execute("INSERT INTO mirror_users(id, full_name) VALUES('u1', '张真')")
    pipeline = IngestPipeline(db, ai=None)  # ai=None 跳过 broadcast
    req = IngestRequest(
        path="workbench_file",
        client_id="c1",
        subject_text="张真",
        attribute="表态",
        value_text="同意推进升级方案",
        metadata=IngestMetadata(
            source_type="client_internal_doc",
            content_role="quote",
            speaker_person_id="张真老师",
        ),
    )
    result = pipeline.ingest(req)
    assert result.written and result.fact_id
    row = db.conn.execute(
        "SELECT speaker_entity_id FROM atomic_facts WHERE id = ?", (result.fact_id,)
    ).fetchone()
    assert row["speaker_entity_id"], "speaker_entity_id 应被自动解析回填"
    ent = db.conn.execute(
        "SELECT resolved_kind, mirror_user_id FROM entities WHERE id = ?",
        (row["speaker_entity_id"],),
    ).fetchone()
    assert ent["resolved_kind"] == "internal"
    assert ent["mirror_user_id"] == "u1"
