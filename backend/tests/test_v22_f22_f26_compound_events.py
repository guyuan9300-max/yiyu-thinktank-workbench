"""v2.2 Phase 2 F2.2 + F2.6 · 复合事件容器 + 主线状态变更事件流 schema 测试

服务: V2.2_NORTH_STAR.md
- N2 数据中心理解信息源: atomic_facts 三元组装不下"复合事件" (一次会议产生多决策)
  → key_decisions + org_events 装"哪几件事是一起发生的"
- N2 软件灵魂: event_line_state_changes 记主线状态变化序列, AI 能讲"主线怎么走过来的"
- N3 接入预留: 三张表都带 actor_type/actor_id 字段, 3.0 AI agent 直接复用

3 张新表:
- key_decisions: 客户级关键决策 (会议纪要 / 决议)
- org_events: 组织事件 (人员变动 / 法人变更 / 资金事件 / 战略调整)
- event_line_state_changes: 主线状态变更事件流

跑法:
    cd backend && .venv/bin/python3 -m pytest tests/test_v22_f22_f26_compound_events.py -v
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
    # 建客户依赖
    db.conn.execute(
        """INSERT INTO clients(id, name, alias, domain, type, intro, stage, color,
                               created_at, updated_at)
           VALUES('c_rici','日慈基金会','日慈','项目','项目','','active','#5B7BFE',?,?)""",
        ("2026-05-22T10:00:00", "2026-05-22T10:00:00"),
    )
    # 建事件线依赖
    db.conn.execute(
        """INSERT INTO event_lines(id, name, kind, status, primary_client_id,
                                   created_at, updated_at)
           VALUES('el_rici_brand', '机构介绍升级', 'custom', 'active', 'c_rici', ?, ?)""",
        ("2026-05-22T10:00:00", "2026-05-22T10:00:00"),
    )
    db.conn.commit()
    return db


# ════════════════════════════════════════════════════════════════
# F2.2 · key_decisions: 客户级关键决策
# ════════════════════════════════════════════════════════════════


def test_key_decisions_table_exists(db: Database):
    rows = db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='key_decisions'"
    )
    assert len(rows) == 1


def test_key_decisions_full_metadata_columns(db: Database):
    """key_decisions 必备字段 — 5 维元数据 + 决策类型 + 影响范围"""
    rows = db.fetchall("PRAGMA table_info(key_decisions)")
    col_names = {r["name"] for r in rows}
    required = {
        "id", "client_id",
        "source_v2_document_id", "source_v2_chunk_id", "meeting_id",
        "decision_title", "decision_body", "decision_type",
        "decided_by_person_ids_json", "decided_at",
        "affected_event_line_ids_json", "related_atomic_fact_ids_json",
        "source_type", "actor_type", "actor_id",
        "confidence", "verification_status",
        "execution_status", "superseded_by_id",
        "created_at", "updated_at",
    }
    missing = required - col_names
    assert not missing, f"key_decisions 缺字段: {missing}"


def test_key_decisions_insert_519_meeting_decision(db: Database):
    """实战场景: 5/19 张真会议决议 - 张真接任法人代表"""
    db.conn.execute(
        """
        INSERT INTO key_decisions (
            id, client_id, source_v2_document_id, meeting_id,
            decision_title, decision_body, decision_type,
            decided_by_person_ids_json, decided_at,
            affected_event_line_ids_json,
            source_type, actor_type, actor_id,
            confidence, verification_status, execution_status,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "kd_519_legal", "c_rici", "doc_meeting_519", "meeting_519",
            "张真接任日慈法人代表",
            "5/19 理事会决议: 由张真接任日慈基金会法人代表, 替代原法人。同时强哥任秘书长。",
            "personnel",
            json.dumps(["person_zhangzhen", "person_qiangge"]),
            "2026-05-19",
            json.dumps(["el_rici_brand", "el_rici_strategic"]),
            "client_internal_doc", "human", "user_guyuanyuan",
            0.95, "user_confirmed", "in_progress",
            "2026-05-22T10:00:00", "2026-05-22T10:00:00",
        ),
    )
    db.conn.commit()
    row = db.fetchone("SELECT * FROM key_decisions WHERE id = 'kd_519_legal'")
    assert row is not None
    assert row["decision_type"] == "personnel"
    assert row["execution_status"] == "in_progress"
    decided_by = json.loads(row["decided_by_person_ids_json"])
    assert len(decided_by) == 2
    affected = json.loads(row["affected_event_line_ids_json"])
    assert "el_rici_brand" in affected


def test_key_decisions_can_be_superseded(db: Database):
    """决策可以被后续决策推翻 (复用 atomic_facts 同模式)"""
    db.conn.execute(
        """INSERT INTO key_decisions (id, client_id, decision_title, decision_body,
                                       created_at, updated_at)
           VALUES ('kd_old', 'c_rici', '旧决策', '描述', ?, ?)""",
        ("2026-05-01T10:00:00", "2026-05-01T10:00:00"),
    )
    db.conn.execute(
        """INSERT INTO key_decisions (id, client_id, decision_title, decision_body,
                                       created_at, updated_at)
           VALUES ('kd_new', 'c_rici', '新决策', '描述', ?, ?)""",
        ("2026-05-22T10:00:00", "2026-05-22T10:00:00"),
    )
    db.conn.execute(
        "UPDATE key_decisions SET superseded_by_id = ?, execution_status = 'superseded' WHERE id = ?",
        ("kd_new", "kd_old"),
    )
    db.conn.commit()
    row = db.fetchone("SELECT * FROM key_decisions WHERE id = 'kd_old'")
    assert row["superseded_by_id"] == "kd_new"
    assert row["execution_status"] == "superseded"


def test_key_decisions_indexes_present(db: Database):
    rows = db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='key_decisions'"
    )
    idx_names = {r["name"] for r in rows if not r["name"].startswith("sqlite_")}
    assert "idx_key_decisions_client_time" in idx_names
    assert "idx_key_decisions_execution" in idx_names
    assert "idx_key_decisions_type" in idx_names


# ════════════════════════════════════════════════════════════════
# F2.2 · org_events: 组织事件 (人员变动/法人变更/资金事件/战略)
# ════════════════════════════════════════════════════════════════


def test_org_events_table_exists(db: Database):
    rows = db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='org_events'"
    )
    assert len(rows) == 1


def test_org_events_insert_personnel_change(db: Database):
    """实战场景: 高老师离职 - 人员变动 + high severity + negative impact"""
    db.conn.execute(
        """
        INSERT INTO org_events (
            id, client_id, event_type, event_title, event_body,
            involved_person_ids_json, involved_event_line_ids_json,
            impact_severity, impact_direction,
            occurred_at, observed_at,
            source_v2_document_id, source_type,
            actor_type, actor_id, confidence,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "oe_gaolaoshi", "c_rici",
            "personnel_change",
            "高老师离职",
            "5 月初高老师因健康原因离职, 章方同时辞职, 心盛计划主理交接给王强",
            json.dumps(["person_gaolaoshi", "person_zhangfang", "person_wangqiang"]),
            json.dumps(["el_rici_brand"]),
            "high", "negative",
            "2026-05-01", "2026-05-19",
            "doc_meeting_519",
            "client_internal_doc",
            "human", "user_guyuanyuan", 0.95,
            "2026-05-22T10:00:00", "2026-05-22T10:00:00",
        ),
    )
    db.conn.commit()
    row = db.fetchone("SELECT * FROM org_events WHERE id = 'oe_gaolaoshi'")
    assert row is not None
    assert row["event_type"] == "personnel_change"
    assert row["impact_severity"] == "high"
    assert row["impact_direction"] == "negative"
    involved = json.loads(row["involved_person_ids_json"])
    assert "person_gaolaoshi" in involved


def test_org_events_default_severity_medium(db: Database):
    """默认 severity=medium, direction=neutral"""
    db.conn.execute(
        """INSERT INTO org_events (
            id, client_id, event_type, event_title, event_body,
            observed_at, created_at, updated_at
        ) VALUES ('oe_default', 'c_rici', 'milestone', '里程碑', '描述', ?, ?, ?)""",
        ("2026-05-22", "2026-05-22T10:00:00", "2026-05-22T10:00:00"),
    )
    db.conn.commit()
    row = db.fetchone("SELECT * FROM org_events WHERE id = 'oe_default'")
    assert row["impact_severity"] == "medium"
    assert row["impact_direction"] == "neutral"
    assert row["actor_type"] == "human"


def test_org_events_can_link_to_decisions(db: Database):
    """org_event 可以关联到 key_decisions (复合事件: 决策导致事件)"""
    db.conn.execute(
        """INSERT INTO key_decisions (id, client_id, decision_title, decision_body,
                                       created_at, updated_at)
           VALUES ('kd_rci_layoff', 'c_rici', '裁员决议', '描述', ?, ?)""",
        ("2026-05-22T10:00:00", "2026-05-22T10:00:00"),
    )
    db.conn.execute(
        """INSERT INTO org_events (
            id, client_id, event_type, event_title, event_body,
            related_decision_ids_json, observed_at, created_at, updated_at
        ) VALUES ('oe_layoff', 'c_rici', 'personnel_change', '执行裁员', '描述',
                  ?, ?, ?, ?)""",
        (json.dumps(["kd_rci_layoff"]), "2026-05-22", "2026-05-22T10:00:00", "2026-05-22T10:00:00"),
    )
    db.conn.commit()
    row = db.fetchone("SELECT * FROM org_events WHERE id = 'oe_layoff'")
    related = json.loads(row["related_decision_ids_json"])
    assert "kd_rci_layoff" in related


# ════════════════════════════════════════════════════════════════
# F2.6 · event_line_state_changes: 主线状态变更事件流
# ════════════════════════════════════════════════════════════════


def test_event_line_state_changes_table_exists(db: Database):
    rows = db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='event_line_state_changes'"
    )
    assert len(rows) == 1


def test_event_line_state_changes_can_record_status_transition(db: Database):
    """主线 active → blocked → active 状态序列"""
    # 5/15 因高老师离职从 active 变 blocked
    db.conn.execute(
        """
        INSERT INTO event_line_state_changes (
            event_line_id, change_type, from_status, to_status,
            change_title, change_body,
            trigger_source_type, trigger_source_id,
            triggered_at, observed_at,
            actor_type, actor_id, impact_severity
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "el_rici_brand", "state_change", "active", "blocked",
            "主线阻塞: 责任人离职",
            "高老师离职导致品牌升级主线暂停",
            "org_event", "oe_gaolaoshi",
            "2026-05-15T10:00:00", "2026-05-19T10:00:00",
            "system", "ai_session_001", "high",
        ),
    )
    # 5/20 强哥接手, 重新激活
    db.conn.execute(
        """
        INSERT INTO event_line_state_changes (
            event_line_id, change_type, from_status, to_status,
            change_title, change_body,
            trigger_source_type, trigger_source_id,
            triggered_at, observed_at,
            actor_type, actor_id, impact_severity
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "el_rici_brand", "state_change", "blocked", "active",
            "主线恢复: 强哥接手",
            "强哥接任主理, 主线恢复推进",
            "key_decision", "kd_519_legal",
            "2026-05-20T10:00:00", "2026-05-20T11:00:00",
            "human", "user_guyuanyuan", "medium",
        ),
    )
    db.conn.commit()
    # 按时间顺序读, 就是这条主线的完整故事
    rows = db.fetchall(
        "SELECT * FROM event_line_state_changes WHERE event_line_id = ? "
        "ORDER BY triggered_at",
        ("el_rici_brand",),
    )
    assert len(rows) == 2
    assert rows[0]["from_status"] == "active"
    assert rows[0]["to_status"] == "blocked"
    assert rows[1]["from_status"] == "blocked"
    assert rows[1]["to_status"] == "active"


def test_event_line_state_changes_owner_change(db: Database):
    """change_type=owner_change: 责任人变更 (≠ 状态变更)"""
    db.conn.execute(
        """
        INSERT INTO event_line_state_changes (
            event_line_id, change_type, from_owner_id, to_owner_id,
            change_title, change_body, triggered_at, observed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "el_rici_brand", "owner_change",
            "person_gaolaoshi", "person_wangqiang",
            "责任人变更: 高老师 → 强哥",
            "高老师离职, 强哥接管",
            "2026-05-20T10:00:00", "2026-05-20T10:00:00",
        ),
    )
    db.conn.commit()
    row = db.fetchone(
        "SELECT * FROM event_line_state_changes WHERE change_type = 'owner_change'"
    )
    assert row["from_owner_id"] == "person_gaolaoshi"
    assert row["to_owner_id"] == "person_wangqiang"


def test_event_line_state_changes_can_be_reversed(db: Database):
    """爱马仕'终身保修': 状态变更可以被撤销 (用户发现 AI 推错)"""
    db.conn.execute(
        """
        INSERT INTO event_line_state_changes (
            event_line_id, change_type, from_status, to_status,
            change_title, triggered_at, observed_at,
            actor_type, actor_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "el_rici_brand", "state_change", "active", "blocked",
            "AI 误判: 以为高老师离职导致主线阻塞",
            "2026-05-22T10:00:00", "2026-05-22T10:00:00",
            "ai_agent", "ai_sess_001",
        ),
    )
    change_id = db.fetchone(
        "SELECT id FROM event_line_state_changes WHERE change_title LIKE '%误判%'"
    )["id"]
    db.conn.execute(
        "UPDATE event_line_state_changes SET reversed_at = ?, reversed_reason = ? WHERE id = ?",
        ("2026-05-22T11:00:00", "高老师离职跟这条主线没关系, AI 推理错了", change_id),
    )
    db.conn.commit()
    row = db.fetchone(
        "SELECT * FROM event_line_state_changes WHERE id = ?", (change_id,)
    )
    assert row["reversed_at"] == "2026-05-22T11:00:00"
    assert "AI 推理错" in row["reversed_reason"]


def test_event_line_state_changes_trigger_source_tracking(db: Database):
    """trigger_source 跟踪: 这个状态变化是从哪条信息推出来的"""
    db.conn.execute(
        """
        INSERT INTO event_line_state_changes (
            event_line_id, change_type, change_title,
            trigger_source_type, trigger_source_id,
            triggered_at, observed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "el_rici_brand", "decision_made", "决定签合同",
            "key_decision", "kd_519_legal",
            "2026-05-19T10:00:00", "2026-05-22T10:00:00",
        ),
    )
    db.conn.commit()
    rows = db.fetchall(
        "SELECT * FROM event_line_state_changes WHERE trigger_source_type = 'key_decision'"
    )
    assert len(rows) == 1
    assert rows[0]["trigger_source_id"] == "kd_519_legal"


def test_event_line_state_changes_fk_cascade_delete(db: Database):
    """删 event_line → state_changes 跟着删 (FK CASCADE)"""
    db.conn.execute(
        """INSERT INTO event_line_state_changes (
            event_line_id, change_type, change_title, triggered_at, observed_at
        ) VALUES ('el_rici_brand', 'state_change', 'X', ?, ?)""",
        ("2026-05-22T10:00:00", "2026-05-22T10:00:00"),
    )
    db.conn.commit()
    db.conn.execute("PRAGMA foreign_keys=ON")
    db.conn.execute("DELETE FROM event_lines WHERE id = 'el_rici_brand'")
    db.conn.commit()
    rows = db.fetchall(
        "SELECT * FROM event_line_state_changes WHERE event_line_id = 'el_rici_brand'"
    )
    assert len(rows) == 0


# ════════════════════════════════════════════════════════════════
# 跨表协作场景: AI 端到端理解"日慈品牌升级主线"
# ════════════════════════════════════════════════════════════════


def test_end_to_end_brand_pivot_story(db: Database):
    """完整故事: 高老师离职 → 主线阻塞 → 决策接手 → 主线恢复

    顾源源 5/22 原话: 让 AI 能讲清楚"主线怎么走过来的"
    """
    # 1. 写组织事件: 高老师离职
    db.conn.execute(
        """INSERT INTO org_events (
            id, client_id, event_type, event_title, event_body,
            involved_person_ids_json, involved_event_line_ids_json,
            impact_severity, impact_direction,
            occurred_at, observed_at, created_at, updated_at
        ) VALUES ('oe_gao_leave', 'c_rici', 'personnel_change',
                  '高老师离职', '5/1 高老师因健康原因离职',
                  ?, ?, 'high', 'negative',
                  '2026-05-01', '2026-05-19', ?, ?)""",
        (
            json.dumps(["person_gaolaoshi"]),
            json.dumps(["el_rici_brand"]),
            "2026-05-22T10:00:00", "2026-05-22T10:00:00",
        ),
    )
    # 2. 主线状态变化: active → blocked, 触发源是 org_event
    db.conn.execute(
        """INSERT INTO event_line_state_changes (
            event_line_id, change_type, from_status, to_status,
            change_title, trigger_source_type, trigger_source_id,
            triggered_at, observed_at
        ) VALUES ('el_rici_brand', 'state_change', 'active', 'blocked',
                  '责任人离职导致阻塞', 'org_event', 'oe_gao_leave',
                  '2026-05-01', '2026-05-19T10:00:00')"""
    )
    # 3. 写关键决策: 强哥接手
    db.conn.execute(
        """INSERT INTO key_decisions (
            id, client_id, decision_title, decision_body,
            decision_type, decided_by_person_ids_json,
            affected_event_line_ids_json,
            decided_at, execution_status, created_at, updated_at
        ) VALUES ('kd_qiang_take', 'c_rici',
                  '强哥接任品牌升级主理', '5/19 决议',
                  'personnel', ?, ?,
                  '2026-05-19', 'in_progress', ?, ?)""",
        (
            json.dumps(["person_zhangzhen"]),
            json.dumps(["el_rici_brand"]),
            "2026-05-22T10:00:00", "2026-05-22T10:00:00",
        ),
    )
    # 4. 主线状态再次变化: blocked → active, 触发源是 key_decision
    db.conn.execute(
        """INSERT INTO event_line_state_changes (
            event_line_id, change_type, from_status, to_status,
            change_title, trigger_source_type, trigger_source_id,
            triggered_at, observed_at
        ) VALUES ('el_rici_brand', 'state_change', 'blocked', 'active',
                  '强哥接手主线恢复', 'key_decision', 'kd_qiang_take',
                  '2026-05-20', '2026-05-20T10:00:00')"""
    )
    db.conn.commit()

    # AI 现在能讲完整故事: 按 triggered_at 排序 state_changes
    rows = db.fetchall(
        """SELECT esc.*,
                  CASE esc.trigger_source_type
                       WHEN 'org_event' THEN (SELECT event_title FROM org_events WHERE id = esc.trigger_source_id)
                       WHEN 'key_decision' THEN (SELECT decision_title FROM key_decisions WHERE id = esc.trigger_source_id)
                       ELSE NULL
                  END AS trigger_summary
           FROM event_line_state_changes esc
           WHERE esc.event_line_id = 'el_rici_brand'
           ORDER BY esc.triggered_at"""
    )
    assert len(rows) == 2
    # 第 1 步: blocked, 触发源是高老师离职事件
    assert rows[0]["to_status"] == "blocked"
    assert rows[0]["trigger_summary"] == "高老师离职"
    # 第 2 步: active, 触发源是强哥接手决策
    assert rows[1]["to_status"] == "active"
    assert rows[1]["trigger_summary"] == "强哥接任品牌升级主理"
