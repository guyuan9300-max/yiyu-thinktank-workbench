"""[A] V2.3 阶段 1 P2 · IngestPipeline 集成 source_registry 测试

测:
1. IngestPipeline.__init__(ensure_v23_schema=True) 启动时建表 + 加列
2. ingest() 入口 4 必填强校验 (client_id 缺时 raise ValueError)
3. ingest() 先 register_source 拿 source_registry_id
4. atomic_facts.source_registry_id 字段写入正确
5. atomic_fact_confidence_history initial_extract 写入
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


class _SimpleDb:
    def __init__(self, path: str = ":memory:"):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, params)

    def fetchone(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()


def _fresh_db():
    """全新 db + 建 atomic_facts 表 + IngestPipeline 自动建 V2.3 表."""
    db = _SimpleDb()
    # 建 atomic_facts (最小 schema, 让 IngestPipeline ALTER TABLE 加 source_registry_id)
    db.execute(
        """
        CREATE TABLE atomic_facts (
            id TEXT PRIMARY KEY,
            client_id TEXT,
            subject_entity_id TEXT,
            subject_text TEXT,
            attribute TEXT,
            value_text TEXT,
            value_normalized TEXT,
            confidence REAL,
            source_v2_chunk_id TEXT,
            source_v2_document_id TEXT,
            evidence_text TEXT,
            status TEXT,
            created_at TEXT,
            updated_at TEXT,
            source_type TEXT,
            content_role TEXT,
            actor_type TEXT,
            actor_id TEXT,
            speaker_person_id TEXT,
            time_anchor TEXT,
            verification_status TEXT,
            confidence_source TEXT,
            validity_status TEXT,
            superseded_by_id TEXT,
            reasoning_trace_id TEXT,
            derived_from_ids_json TEXT,
            update_relation TEXT
        )
        """
    )
    # 建依赖表 (event_log + ai_episode_log,IngestPipeline 写日志用)
    db.execute(
        """CREATE TABLE event_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT, actor_type TEXT, actor_id TEXT,
            entity_type TEXT, entity_id TEXT, client_id TEXT, payload_json TEXT,
            occurred_at TEXT
        )"""
    )
    db.execute(
        """CREATE TABLE ai_episode_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ai_session_id TEXT, user_id TEXT, client_id TEXT,
            action_type TEXT, action_summary TEXT, referenced_fact_ids_json TEXT,
            referenced_doc_ids_json TEXT, outcome TEXT, occurred_at TEXT, completed_at TEXT
        )"""
    )
    return db


# ─── Tests ─────────────────────────────────────────


def test_ingest_pipeline_auto_ensures_v23_schema():
    """IngestPipeline(ensure_v23_schema=True) 启动时自动建 V2.3 表."""
    from app.services.ingest_pipeline import IngestPipeline
    db = _fresh_db()
    _ = IngestPipeline(db, ai=None, ensure_v23_schema=True)
    # source_registry 表应该存在
    r = db.fetchone(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='source_registry'"
    )
    assert r is not None
    # atomic_fact_confidence_history 应该存在
    r = db.fetchone(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='atomic_fact_confidence_history'"
    )
    assert r is not None
    # atomic_facts.source_registry_id 列应该加上
    cols = [r["name"] for r in db.execute("PRAGMA table_info(atomic_facts)").fetchall()]
    assert "source_registry_id" in cols


def test_ingest_raises_when_client_id_missing():
    """ingest() 缺 client_id 时 raise ValueError (V2.3 P2 强校验)."""
    from app.services.ingest_pipeline import (
        IngestPipeline, IngestRequest, IngestMetadata,
    )

    db = _fresh_db()
    pipeline = IngestPipeline(db, ai=None)

    import pytest
    with pytest.raises(ValueError, match="V2.3 P2 强校验"):
        pipeline.ingest(IngestRequest(
            path="workbench_file",
            client_id="",  # ← 故意缺
            subject_text="日慈基金会",
            attribute="法人代表",
            value_text="张真",
            metadata=IngestMetadata(
                source_type="client_official_doc",
                content_role="fact",
            ),
        ))


def test_ingest_creates_source_registry_record():
    """ingest() 成功时, source_registry 表应该新增一条, atomic_facts.source_registry_id 应被填."""
    from app.services.ingest_pipeline import (
        IngestPipeline, IngestRequest, IngestMetadata,
    )

    db = _fresh_db()
    pipeline = IngestPipeline(db, ai=None)

    result = pipeline.ingest(IngestRequest(
        path="workbench_file",
        client_id="client_test",
        subject_text="日慈基金会",
        attribute="法人代表",
        value_text="张真",
        metadata=IngestMetadata(
            source_type="client_official_doc",
            content_role="fact",
            actor_type="ai_agent",
            actor_id="document_llm_extractor",
            time_anchor="2026-05-19",
            confidence_score=0.85,
        ),
        source_v2_document_id="v2doc_xxx",
        evidence_text="原文摘录: 张真接任法人代表...",
    ))

    assert result.written is True
    # source_registry 应有一条
    sr_count = db.fetchone("SELECT COUNT(*) c FROM source_registry")["c"]
    assert sr_count == 1
    sr_row = db.fetchone("SELECT * FROM source_registry")
    assert sr_row["client_id"] == "client_test"
    assert sr_row["source_type"] == "client_official_doc"
    assert sr_row["source_channel"] == "workbench_upload"  # _infer_channel 推导
    assert sr_row["source_role"] == "client_official"      # _infer_role_from_source_type 推导

    # atomic_facts.source_registry_id 应被填
    fact_row = db.fetchone(
        "SELECT source_registry_id FROM atomic_facts WHERE id = ?",
        (result.fact_id,),
    )
    assert fact_row["source_registry_id"] == sr_row["source_id"]


def test_ingest_writes_confidence_history_initial_extract():
    """ingest() 成功时, atomic_fact_confidence_history 应有 initial_extract 记录."""
    from app.services.ingest_pipeline import (
        IngestPipeline, IngestRequest, IngestMetadata,
    )

    db = _fresh_db()
    pipeline = IngestPipeline(db, ai=None)

    result = pipeline.ingest(IngestRequest(
        path="task_review",
        client_id="client_test",
        subject_text="顾源源",
        attribute="新增任务",
        value_text="完成日慈方案",
        metadata=IngestMetadata(
            source_type="collaboration_task",
            content_role="plan",
            actor_type="human",
            actor_id="user_xxx",
            confidence_score=0.90,
        ),
    ))

    # confidence_history 应有 1 条 initial_extract
    history = db.fetchall(
        "SELECT * FROM atomic_fact_confidence_history WHERE fact_id = ?",
        (result.fact_id,),
    )
    assert len(history) == 1
    assert history[0]["trigger_event"] == "initial_extract"
    assert history[0]["new_confidence"] == 0.90
    assert history[0]["old_confidence"] is None  # initial_extract 旧值为 null


def test_ingest_pipeline_backward_compat_when_v23_disabled():
    """ensure_v23_schema=False 时 IngestPipeline 跳过 V2.3 表 (向后兼容)."""
    from app.services.ingest_pipeline import IngestPipeline
    db = _fresh_db()
    _ = IngestPipeline(db, ai=None, ensure_v23_schema=False)
    # source_registry 表不应被建
    r = db.fetchone(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='source_registry'"
    )
    assert r is None  # 未建
