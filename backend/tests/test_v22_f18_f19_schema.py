"""v2.2 Phase 1 F1.8 + F1.9 · atomic_facts 5 维元数据 + event_log 总线 schema 测试

服务: V2.2_NORTH_STAR.md
- N2 数据中心理解信息源: 5 维元数据 schema 字段就位, ExtractionRunner 填这些字段
- N3 接入预留: A1 (actor_type) + A2 (event_log 持久化) + A3 (reasoning_trace) + A4 (verification_status)

跑法:
    cd backend && .venv/bin/python3 -m pytest tests/test_v22_f18_f19_schema.py -v
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import Database  # noqa: E402


@pytest.fixture
def db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "app.db")
    db.conn.execute("PRAGMA foreign_keys=OFF")
    return db


# ────────────────────────────────────────────────────────────────
# 1. atomic_facts 5 维元数据字段完整 (F1.8 + F1.9)
# ────────────────────────────────────────────────────────────────


def test_atomic_facts_source_type_default(db: Database):
    """source_type 默认 'llm_extracted' (LLM 抽取的默认), 14 类细分"""
    rows = db.fetchall("PRAGMA table_info(atomic_facts)")
    by_name = {r["name"]: r for r in rows}
    assert "source_type" in by_name
    assert by_name["source_type"]["dflt_value"] == "'llm_extracted'"


def test_atomic_facts_content_role_default(db: Database):
    """content_role 默认 'fact'"""
    rows = db.fetchall("PRAGMA table_info(atomic_facts)")
    by_name = {r["name"]: r for r in rows}
    assert "content_role" in by_name
    assert by_name["content_role"]["dflt_value"] == "'fact'"


def test_atomic_facts_actor_fields_present(db: Database):
    """N3 A1: actor_type + actor_id 必须就位"""
    rows = db.fetchall("PRAGMA table_info(atomic_facts)")
    col_names = {r["name"] for r in rows}
    assert "actor_type" in col_names
    assert "actor_id" in col_names


def test_atomic_facts_verification_fields_present(db: Database):
    """N3 A4 + N2 5 维 lifecycle: verification_status / confidence_source"""
    rows = db.fetchall("PRAGMA table_info(atomic_facts)")
    col_names = {r["name"] for r in rows}
    assert "verification_status" in col_names
    assert "confidence_source" in col_names
    by_name = {r["name"]: r for r in rows}
    assert by_name["verification_status"]["dflt_value"] == "'unverified'"
    assert by_name["confidence_source"]["dflt_value"] == "'rule'"


def test_atomic_facts_validity_fields_present(db: Database):
    """N2 5 维 lifecycle: validity_status + superseded_by_id (R5 时效失效)"""
    rows = db.fetchall("PRAGMA table_info(atomic_facts)")
    col_names = {r["name"] for r in rows}
    assert "validity_status" in col_names
    assert "superseded_by_id" in col_names


def test_atomic_facts_provenance_fields_present(db: Database):
    """N3 A3: reasoning_trace_id + derived_from_ids_json (3.0 fact graph)"""
    rows = db.fetchall("PRAGMA table_info(atomic_facts)")
    col_names = {r["name"] for r in rows}
    assert "reasoning_trace_id" in col_names
    assert "derived_from_ids_json" in col_names


def test_atomic_facts_speaker_and_time_anchor(db: Database):
    """N2 5 维: speaker_person_id (语录类) + time_anchor (事件发生时间)"""
    rows = db.fetchall("PRAGMA table_info(atomic_facts)")
    col_names = {r["name"] for r in rows}
    assert "speaker_person_id" in col_names
    assert "time_anchor" in col_names


def test_atomic_facts_indexes_present(db: Database):
    """新索引: verification 找待审 + validity 过滤 superseded"""
    rows = db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='atomic_facts'"
    )
    idx_names = {r["name"] for r in rows}
    assert "idx_atomic_facts_verification" in idx_names
    assert "idx_atomic_facts_validity" in idx_names


# ────────────────────────────────────────────────────────────────
# 2. event_log 总线表 (F1.9, N3 A2 预留)
# ────────────────────────────────────────────────────────────────


def test_event_log_table_exists(db: Database):
    rows = db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='event_log'"
    )
    assert len(rows) == 1


def test_event_log_required_columns(db: Database):
    """event_log 必备字段 — 让 3.0 能查 AI 行动历史"""
    rows = db.fetchall("PRAGMA table_info(event_log)")
    col_names = {r["name"] for r in rows}
    required = {
        "id", "event_type", "actor_type", "actor_id",
        "entity_type", "entity_id", "client_id",
        "payload_json", "occurred_at",
        # 爱马仕"终身保修"原则: 可撤销
        "reversed_at", "reversed_by", "reversed_reason",
    }
    missing = required - col_names
    assert not missing, f"event_log 缺字段: {missing}"


def test_event_log_indexes_present(db: Database):
    """event_log 索引 — 让 AI 能高效按 entity/client/time/actor 查"""
    rows = db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='event_log'"
    )
    idx_names = {r["name"] for r in rows}
    expected = {
        "idx_event_log_entity",
        "idx_event_log_client_time",
        "idx_event_log_event_type",
        "idx_event_log_actor",
    }
    missing = expected - idx_names
    assert not missing, f"event_log 缺索引: {missing}"


def test_event_log_insert_and_query(db: Database):
    """event_log 可写可读 (基本 CRUD)"""
    db.conn.execute(
        """
        INSERT INTO event_log (
            event_type, actor_type, actor_id,
            entity_type, entity_id, client_id,
            payload_json, occurred_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "client.fact_created",
            "human",
            "user_example_user",
            "fact",
            "fact_abc123",
            "client_xyz",
            json.dumps({"subject": "A组织", "attribute": "法人代表"}),
            "2026-05-22T10:00:00",
        ),
    )
    db.conn.commit()
    row = db.fetchone(
        "SELECT * FROM event_log WHERE entity_id = ?", ("fact_abc123",)
    )
    assert row is not None
    assert row["event_type"] == "client.fact_created"
    assert row["actor_type"] == "human"


def test_event_log_supports_ai_agent_actor(db: Database):
    """N3 关键: AI agent 作为 actor 可以写入"""
    db.conn.execute(
        """
        INSERT INTO event_log (
            event_type, actor_type, actor_id,
            entity_type, entity_id,
            payload_json, occurred_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "ai.action_taken",
            "ai_agent",
            "ai_session_2026_05_22",
            "task",
            "task_001",
            json.dumps({"action": "create_task", "title": "拟合同初稿"}),
            "2026-05-22T11:00:00",
        ),
    )
    db.conn.commit()
    row = db.fetchone(
        "SELECT * FROM event_log WHERE entity_id = 'task_001'"
    )
    assert row is not None
    assert row["actor_type"] == "ai_agent"


def test_event_log_reversal_support(db: Database):
    """爱马仕'终身保修': 可撤销操作 — 写入 reversed_at"""
    db.conn.execute(
        """
        INSERT INTO event_log (
            event_type, actor_type, actor_id,
            entity_type, entity_id,
            payload_json, occurred_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "ai.action_taken",
            "ai_agent",
            "ai_session",
            "fact",
            "fact_bad",
            "{}",
            "2026-05-22T12:00:00",
        ),
    )
    db.conn.commit()
    # 用户发现 AI 写错了, 撤销
    db.conn.execute(
        "UPDATE event_log SET reversed_at = ?, reversed_by = ?, reversed_reason = ? WHERE entity_id = 'fact_bad'",
        ("2026-05-22T12:30:00", "user_example_user", "AI 抽错了, 不是法人代表"),
    )
    db.conn.commit()
    row = db.fetchone("SELECT * FROM event_log WHERE entity_id = 'fact_bad'")
    assert row["reversed_at"] == "2026-05-22T12:30:00"
    assert row["reversed_by"] == "user_example_user"
    assert "AI 抽错了" in row["reversed_reason"]


# ────────────────────────────────────────────────────────────────
# 3. atomic_facts 写入新字段端到端
# ────────────────────────────────────────────────────────────────


def test_atomic_facts_can_insert_with_new_metadata(db: Database):
    """v2.2 新增 5 维字段后, INSERT 完整事实记录"""
    # 先建客户依赖
    db.conn.execute(
        """INSERT INTO clients(id, name, alias, domain, type, intro, stage, color,
                               created_at, updated_at)
           VALUES('c1','A组织','A组织','项目','项目','','active','#5B7BFE',?,?)""",
        ("2026-05-22T10:00:00", "2026-05-22T10:00:00"),
    )
    # 新建 atomic_fact 含 5 维元数据
    db.conn.execute(
        """
        INSERT INTO atomic_facts (
            id, client_id, subject_text, attribute, value_text, value_normalized,
            confidence, status, created_at, updated_at,
            source_type, content_role, actor_type, actor_id,
            speaker_person_id, time_anchor,
            verification_status, confidence_source, validity_status,
            reasoning_trace_id, derived_from_ids_json
        ) VALUES (
            'fact_1', 'c1', '负责人甲', '角色', '法人代表', '法人代表',
            0.95, 'active', '2026-05-22T10:00:00', '2026-05-22T10:00:00',
            'client_verbal_meeting', 'fact', 'human', 'user_example_user',
            'person_zhangzhen', '2026-05-19',
            'user_confirmed', 'user', 'current',
            'trace_001', '[]'
        )
        """
    )
    db.conn.commit()
    row = db.fetchone("SELECT * FROM atomic_facts WHERE id = 'fact_1'")
    assert row["source_type"] == "client_verbal_meeting"
    assert row["content_role"] == "fact"
    assert row["actor_type"] == "human"
    assert row["speaker_person_id"] == "person_zhangzhen"
    assert row["time_anchor"] == "2026-05-19"
    assert row["verification_status"] == "user_confirmed"
    assert row["validity_status"] == "current"


def test_atomic_facts_default_values_applied(db: Database):
    """v1.0 INSERT 不填新列时, 默认值应正确 (向后兼容)"""
    db.conn.execute(
        """INSERT INTO clients(id, name, alias, domain, type, intro, stage, color,
                               created_at, updated_at)
           VALUES('c2','客户2','c2','项目','项目','','active','#5B7BFE',?,?)""",
        ("2026-05-22T10:00:00", "2026-05-22T10:00:00"),
    )
    db.conn.execute(
        """
        INSERT INTO atomic_facts (
            id, client_id, subject_text, attribute, value_text, value_normalized,
            confidence, status, created_at, updated_at
        ) VALUES (
            'fact_legacy', 'c2', 'X', 'Y', 'Z', 'z',
            0.5, 'active', '2026-05-22T10:00:00', '2026-05-22T10:00:00'
        )
        """
    )
    db.conn.commit()
    row = db.fetchone("SELECT * FROM atomic_facts WHERE id = 'fact_legacy'")
    # 验证默认值
    assert row["source_type"] == "llm_extracted"
    assert row["content_role"] == "fact"
    assert row["actor_type"] == "human"
    assert row["verification_status"] == "unverified"
    assert row["confidence_source"] == "rule"
    assert row["validity_status"] == "current"
    assert row["derived_from_ids_json"] == "[]"


def test_atomic_facts_supports_ai_agent_authored(db: Database):
    """N3 关键: AI agent 自己写的事实, source_type='ai_agent_authored' + actor_type='ai_agent'"""
    db.conn.execute(
        """INSERT INTO clients(id, name, alias, domain, type, intro, stage, color,
                               created_at, updated_at)
           VALUES('c3','客户3','c3','项目','项目','','active','#5B7BFE',?,?)""",
        ("2026-05-22T10:00:00", "2026-05-22T10:00:00"),
    )
    db.conn.execute(
        """
        INSERT INTO atomic_facts (
            id, client_id, subject_text, attribute, value_text, value_normalized,
            confidence, status, created_at, updated_at,
            source_type, actor_type, actor_id, verification_status, confidence_source
        ) VALUES (
            'fact_ai', 'c3', 'A组织', '风险等级', '中', '中',
            0.4, 'active', '2026-05-22T10:00:00', '2026-05-22T10:00:00',
            'ai_agent_authored', 'ai_agent', 'ai_session_2026_05_22',
            'unverified', 'llm'
        )
        """
    )
    db.conn.commit()
    row = db.fetchone("SELECT * FROM atomic_facts WHERE id = 'fact_ai'")
    assert row["source_type"] == "ai_agent_authored"
    assert row["actor_type"] == "ai_agent"
    # AI 写的事实默认未验证 → R3 应该触发主动澄清
    assert row["verification_status"] == "unverified"
