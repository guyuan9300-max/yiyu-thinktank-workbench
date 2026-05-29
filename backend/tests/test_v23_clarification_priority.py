"""[A] V2.3 阶段 1 补充 3 · clarification_priority 单测"""
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
    db = _SimpleDb()
    db.execute(
        """CREATE TABLE atomic_facts (
            id TEXT PRIMARY KEY, client_id TEXT, subject_text TEXT, attribute TEXT,
            value_text TEXT, value_normalized TEXT, confidence REAL,
            status TEXT DEFAULT 'active', created_at TEXT,
            update_relation TEXT DEFAULT 'none', derived_from_ids_json TEXT
        )"""
    )
    db.execute(
        """CREATE TABLE tasks (
            id TEXT PRIMARY KEY, client_id TEXT, title TEXT, description TEXT,
            status TEXT DEFAULT 'in_progress', due_date TEXT
        )"""
    )
    db.execute(
        """CREATE TABLE commitments (
            id TEXT PRIMARY KEY, client_id TEXT, committer TEXT, recipient TEXT,
            content TEXT, deadline TEXT, status TEXT DEFAULT 'pending'
        )"""
    )
    db.execute(
        """CREATE TABLE fact_contradictions (
            id TEXT PRIMARY KEY, fact_a_id TEXT, fact_b_id TEXT, contradiction_type TEXT
        )"""
    )
    return db


def test_calculate_priority_high_score():
    """高 priority case: 低置信度 + 跨源冲突 + 当前任务依赖 + 紧急 due"""
    from app.services.clarification_priority import calculate_priority

    db = _fresh_db()
    # 加 100 条 atomic_facts (拉高客户活跃度)
    for i in range(100):
        db.execute(
            "INSERT INTO atomic_facts (id, client_id, subject_text, attribute, confidence, created_at) "
            "VALUES (?, ?, ?, ?, ?, datetime('now'))",
            (f"f_{i}", "client_X", f"sub_{i}", "attr", 0.7),
        )

    # target fact (低置信度 + supersedes)
    db.execute(
        "INSERT INTO atomic_facts (id, client_id, subject_text, attribute, value_text, value_normalized, confidence, update_relation, created_at) "
        "VALUES ('f_target', 'client_X', 'A组织', '法人代表', '负责人甲', '负责人甲', 0.4, 'supersedes', datetime('now'))",
    )
    # 同 (subject,attribute) 第二个值 → 触发 D2 冲突
    db.execute(
        "INSERT INTO atomic_facts (id, client_id, subject_text, attribute, value_text, value_normalized, confidence, status, created_at) "
        "VALUES ('f_target_old', 'client_X', 'A组织', '法人代表', '王晓燕', '王晓燕', 0.7, 'superseded', datetime('now'))",
    )

    # 加 active task 引用 subject → D3 行动依赖
    db.execute(
        "INSERT INTO tasks (id, client_id, title, description, status, due_date) "
        "VALUES ('t1', 'client_X', 'A组织方案', '法人确认', 'in_progress', datetime('now', '+5 days'))",
    )

    result = calculate_priority(
        db, "f_target", "client_X", "A组织", "法人代表"
    )

    assert "score" in result
    assert "breakdown" in result
    assert result["breakdown"]["d2_conflict"] >= 2  # 有冲突 + supersedes
    assert result["breakdown"]["d3_action_dep"] >= 3  # 有 active task
    assert result["breakdown"]["d4_time_urgency"] >= 4  # 7 天内 due
    assert result["breakdown"]["d5_confidence_gap"] == 4  # conf 0.4 → bucket 4
    assert result["score"] >= 30


def test_calculate_priority_low_score():
    """低 priority case: 高置信度 + 无冲突 + 无任务 + 无紧急"""
    from app.services.clarification_priority import calculate_priority

    db = _fresh_db()
    db.execute(
        "INSERT INTO atomic_facts (id, client_id, subject_text, attribute, value_text, confidence, created_at) "
        "VALUES ('f_stable', 'client_Y', 'A组织', '成立年份', '2013', 0.95, datetime('now'))",
    )

    result = calculate_priority(
        db, "f_stable", "client_Y", "A组织", "成立年份"
    )

    assert result["breakdown"]["d5_confidence_gap"] == 1  # conf 0.95
    assert result["score"] <= 30  # 应该是 skip / background
    assert result["suggested_action"] in ("skip", "background")


def test_top_n_clarifications():
    """top_n 拉低置信 + 冲突的 candidates 排序."""
    from app.services.clarification_priority import top_n_clarifications_for_client

    db = _fresh_db()
    db.execute(
        "INSERT INTO atomic_facts (id, client_id, subject_text, attribute, value_text, confidence, update_relation, status, created_at) "
        "VALUES ('low1', 'client_Z', 'A', 'attr1', 'v1', 0.4, 'none', 'active', datetime('now'))",
    )
    db.execute(
        "INSERT INTO atomic_facts (id, client_id, subject_text, attribute, value_text, confidence, update_relation, status, created_at) "
        "VALUES ('conflict1', 'client_Z', 'B', 'attr2', 'v2', 0.8, 'conflict', 'active', datetime('now'))",
    )
    db.execute(
        "INSERT INTO atomic_facts (id, client_id, subject_text, attribute, value_text, confidence, status, created_at) "
        "VALUES ('high', 'client_Z', 'C', 'attr3', 'v3', 0.95, 'active', datetime('now'))",
    )

    results = top_n_clarifications_for_client(db, "client_Z", limit=10)

    assert isinstance(results, list)
    fact_ids = [r["fact_id"] for r in results]
    # low1 (低 conf 0.4) 和 conflict1 (有冲突) 应该在
    assert "low1" in fact_ids
    assert "conflict1" in fact_ids
    # high (0.95 + 无冲突) 应该不在
    assert "high" not in fact_ids
