"""v2.2 Phase 2 F2.0 · AI Memory 5 表占位 schema 测试

服务: V2.2_NORTH_STAR.md N3 (3.0 接入预留 A5)

设计意图:
- 3.0 是"给 AI 配共享办公室", AI 越用越聪明依赖 4 类长期记忆 + 1 套反馈机制
- v2.2 阶段只建 schema + 单向写入, 不读取
- 上线那天开始记数据, 3.0 启动时已有 N 个月真实样本

5 张表:
- ai_episode_log: AI 每次行动日志
- ai_learned_rules: 用户纠错抽出的规则
- user_ai_preferences: 用户级 AI 协作偏好
- project_procedures: 项目执行套路
- ai_feedback_signals: 用户对 AI 输出评价

跑法:
    cd backend && .venv/bin/python3 -m pytest tests/test_v22_f20_ai_memory.py -v
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
# 5 张表存在性
# ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("table", [
    "ai_episode_log",
    "ai_learned_rules",
    "user_ai_preferences",
    "project_procedures",
    "ai_feedback_signals",
])
def test_ai_memory_table_exists(db: Database, table: str):
    rows = db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    )
    assert len(rows) == 1, f"{table} 表不存在"


# ────────────────────────────────────────────────────────────────
# ai_episode_log: AI 行动日志
# ────────────────────────────────────────────────────────────────


def test_ai_episode_log_required_columns(db: Database):
    """AI 行动日志必备字段"""
    rows = db.fetchall("PRAGMA table_info(ai_episode_log)")
    col_names = {r["name"] for r in rows}
    required = {
        "id", "ai_session_id", "user_id", "client_id",
        "action_type", "action_summary",
        "referenced_fact_ids_json", "referenced_doc_ids_json",
        "outcome", "occurred_at", "completed_at",
    }
    missing = required - col_names
    assert not missing, f"ai_episode_log 缺字段: {missing}"


def test_ai_episode_log_can_record_extraction(db: Database):
    """AI 抽取一条事实 → episode_log 记一行"""
    db.conn.execute(
        """
        INSERT INTO ai_episode_log (
            ai_session_id, user_id, client_id,
            action_type, action_summary,
            referenced_fact_ids_json, referenced_doc_ids_json,
            outcome, occurred_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "ai_sess_2026_05_22_001",
            "user_guyuanyuan",
            "client_rici",
            "extracted_fact",
            "从 5/19 会议纪要抽出: 张真接任法人代表",
            json.dumps(["fact_001"]),
            json.dumps(["doc_meeting_519"]),
            "pending",
            "2026-05-22T11:00:00",
        ),
    )
    db.conn.commit()
    row = db.fetchone(
        "SELECT * FROM ai_episode_log WHERE ai_session_id = 'ai_sess_2026_05_22_001'"
    )
    assert row is not None
    assert row["action_type"] == "extracted_fact"
    assert row["outcome"] == "pending"
    assert json.loads(row["referenced_fact_ids_json"]) == ["fact_001"]


# ────────────────────────────────────────────────────────────────
# ai_learned_rules: 用户纠错抽出的规则
# ────────────────────────────────────────────────────────────────


def test_ai_learned_rules_can_record_correction(db: Database):
    """用户说"不要再用'赋能'这个词" → 抽成一条规则"""
    db.conn.execute(
        """
        INSERT INTO ai_learned_rules (
            rule_name, rule_body, rule_why, rule_how_to_apply,
            confidence, user_id, learned_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "avoid_word_empowerment",
            "写客户档案/战略陪伴 narrative 时禁用'赋能'一词",
            "顾源源说: 这个词在公益界已经被滥用, 显得空洞",
            "narrative/proposal/email 等所有客户面对文档生成时激活",
            0.9,
            "user_guyuanyuan",
            "2026-05-22T11:30:00",
        ),
    )
    db.conn.commit()
    row = db.fetchone(
        "SELECT * FROM ai_learned_rules WHERE rule_name = 'avoid_word_empowerment'"
    )
    assert row is not None
    assert row["confidence"] == 0.9
    assert row["activated_count"] == 0  # 默认 0


def test_ai_learned_rules_unique_per_scope(db: Database):
    """同 user_id + client_id + rule_name 组合应唯一 (防重复学习)"""
    args = ("test_rule", "body", "", "", 0.5, "u1", "c1", "2026-05-22T11:30:00")
    db.conn.execute(
        """INSERT INTO ai_learned_rules (
            rule_name, rule_body, rule_why, rule_how_to_apply,
            confidence, user_id, client_id, learned_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        args,
    )
    db.conn.commit()
    # 同 scope 不能重复
    import sqlite3 as sq3
    with pytest.raises(sq3.IntegrityError):
        db.conn.execute(
            """INSERT INTO ai_learned_rules (
                rule_name, rule_body, rule_why, rule_how_to_apply,
                confidence, user_id, client_id, learned_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            args,
        )


# ────────────────────────────────────────────────────────────────
# user_ai_preferences: 用户协作偏好
# ────────────────────────────────────────────────────────────────


def test_user_ai_preferences_can_record(db: Database):
    """顾源源讨厌 A/B 菜单式提问 → 偏好"""
    db.conn.execute(
        """
        INSERT INTO user_ai_preferences (
            user_id, preference_key, preference_value,
            inferred_from, confidence, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "user_guyuanyuan",
            "proposal_format",
            "禁止 A/B 菜单式提问 — 给判断 + 问题/方式/成本/风险, 再求确认",
            "user_explicit",
            1.0,
            "2026-05-22T12:00:00",
            "2026-05-22T12:00:00",
        ),
    )
    db.conn.commit()
    row = db.fetchone(
        "SELECT * FROM user_ai_preferences WHERE user_id = 'user_guyuanyuan' AND preference_key = 'proposal_format'"
    )
    assert row is not None
    assert "禁止" in row["preference_value"]


def test_user_ai_preferences_unique_per_user_key(db: Database):
    """同 user_id + preference_key 不能重复 (更新走 UPSERT)"""
    args = ("u1", "key1", "v1", "user_explicit", 0.5, "2026-05-22T12:00:00", "2026-05-22T12:00:00")
    db.conn.execute(
        "INSERT INTO user_ai_preferences (user_id, preference_key, preference_value, inferred_from, confidence, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        args,
    )
    db.conn.commit()
    import sqlite3 as sq3
    with pytest.raises(sq3.IntegrityError):
        db.conn.execute(
            "INSERT INTO user_ai_preferences (user_id, preference_key, preference_value, inferred_from, confidence, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            args,
        )


# ────────────────────────────────────────────────────────────────
# project_procedures: 执行套路
# ────────────────────────────────────────────────────────────────


def test_project_procedures_can_record_workshop_sop(db: Database):
    """给日慈做工作坊的 SOP 套路"""
    steps = [
        {"step_name": "调研客户痛点", "expected_output": "3 个候选主题", "ai_can_do": True, "requires_human": False},
        {"step_name": "客户选定主题", "expected_output": "1 个最终主题", "ai_can_do": False, "requires_human": True},
        {"step_name": "深化主题", "expected_output": "方案大纲", "ai_can_do": True, "requires_human": False},
    ]
    db.conn.execute(
        """
        INSERT INTO project_procedures (
            procedure_name, client_id, project_category, steps_json,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "workshop_proposal_for_rici",
            "client_rici",
            "workshop",
            json.dumps(steps, ensure_ascii=False),
            "2026-05-22T12:00:00",
            "2026-05-22T12:00:00",
        ),
    )
    db.conn.commit()
    row = db.fetchone(
        "SELECT * FROM project_procedures WHERE procedure_name = 'workshop_proposal_for_rici'"
    )
    assert row is not None
    saved_steps = json.loads(row["steps_json"])
    assert len(saved_steps) == 3
    assert saved_steps[0]["step_name"] == "调研客户痛点"


# ────────────────────────────────────────────────────────────────
# ai_feedback_signals: 用户对 AI 输出的反馈
# ────────────────────────────────────────────────────────────────


def test_ai_feedback_signal_thumbs_down_with_correction(db: Database):
    """用户对 AI 抽错的事实点 👎 + 修正"""
    db.conn.execute(
        """
        INSERT INTO ai_episode_log (
            ai_session_id, action_type, action_summary,
            outcome, occurred_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        ("ai_sess_001", "extracted_fact", "AI 说: 张真接任理事长", "pending", "2026-05-22T11:00:00"),
    )
    episode_id = db.fetchone(
        "SELECT id FROM ai_episode_log WHERE ai_session_id = 'ai_sess_001'"
    )["id"]
    # 用户反馈: AI 抽错了, 是法人代表不是理事长
    db.conn.execute(
        """
        INSERT INTO ai_feedback_signals (
            episode_id, user_id, signal_type, signal_target,
            user_correction, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            episode_id,
            "user_guyuanyuan",
            "thumbs_down",
            "action_summary",
            "应该是'法人代表'不是'理事长', 你看错了",
            "2026-05-22T11:05:00",
        ),
    )
    db.conn.commit()
    row = db.fetchone(
        "SELECT * FROM ai_feedback_signals WHERE episode_id = ?", (episode_id,)
    )
    assert row is not None
    assert row["signal_type"] == "thumbs_down"
    assert "法人代表" in row["user_correction"]


def test_ai_feedback_cascade_delete_with_episode(db: Database):
    """删 episode → feedback 跟着删 (FK CASCADE)"""
    db.conn.execute(
        """
        INSERT INTO ai_episode_log (
            ai_session_id, action_type, outcome, occurred_at
        ) VALUES (?, ?, ?, ?)
        """,
        ("ai_sess_002", "created_task", "pending", "2026-05-22T11:00:00"),
    )
    episode_id = db.fetchone(
        "SELECT id FROM ai_episode_log WHERE ai_session_id = 'ai_sess_002'"
    )["id"]
    db.conn.execute(
        """
        INSERT INTO ai_feedback_signals (
            episode_id, user_id, signal_type, created_at
        ) VALUES (?, ?, ?, ?)
        """,
        (episode_id, "u1", "thumbs_up", "2026-05-22T11:05:00"),
    )
    db.conn.commit()
    # 删 episode
    db.conn.execute("PRAGMA foreign_keys=ON")
    db.conn.execute("DELETE FROM ai_episode_log WHERE id = ?", (episode_id,))
    db.conn.commit()
    rows = db.fetchall("SELECT * FROM ai_feedback_signals WHERE episode_id = ?", (episode_id,))
    assert len(rows) == 0


# ────────────────────────────────────────────────────────────────
# 索引完整性 (查询性能保障)
# ────────────────────────────────────────────────────────────────


def test_ai_memory_critical_indexes_present(db: Database):
    """5 表的关键索引就位 (3.0 启动时不会全表扫)"""
    rows = db.fetchall(
        "SELECT tbl_name, name FROM sqlite_master WHERE type='index' "
        "AND tbl_name IN ('ai_episode_log','ai_learned_rules','user_ai_preferences','project_procedures','ai_feedback_signals')"
    )
    by_table: dict[str, set[str]] = {}
    for r in rows:
        by_table.setdefault(str(r["tbl_name"]), set()).add(str(r["name"]))

    # 每张表至少 1 个手建索引
    for tbl in [
        "ai_episode_log",
        "ai_learned_rules",
        "user_ai_preferences",
        "project_procedures",
        "ai_feedback_signals",
    ]:
        idxs = by_table.get(tbl, set())
        # 排除 sqlite 自动索引 (sqlite_autoindex_*)
        manual_idxs = {n for n in idxs if not n.startswith("sqlite_autoindex_")}
        assert manual_idxs, f"{tbl} 缺手建索引"
